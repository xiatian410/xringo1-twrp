#!/usr/bin/env python3
"""Stock ARM64 input registration and synchronous FF upload/erase lifecycles.

Original callbacks and workers execute. Kernel input core, work scheduling,
runtime PM, DSP symbol lookup and completion events use explicit fixtures.
Probe, start/stop workers, IRQs, physical timing and motor output are excluded.
"""
import hashlib
import json
from pathlib import Path
import struct
import tempfile

from haptics_driver_emulation import (
    Module, ROOT, DEPS, SOURCE, LAYOUTS, MASK, capture, sha,
    UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC,
)
from firmware_facts import haptics_module

CTX, EFFECT, INPUT, FF, EFFECTS = 0x4000000, 0x4010000, 0x4030000, 0x4040000, 0x4050000


class Lifecycle(Module):
    def __init__(self, path):
        super().__init__(path)
        assert sha(path) in LAYOUTS
        self.modern = LAYOUTS[sha(path)] == 'modern'
        self.failures = {}
        self.pm_error = 0
        self.completion = 1
        self.waits = []
        self.queued = []
        self.pending_flush = None
        self.capabilities = []
        self.registered = False
        self.freed = []
        self.intercept('cs40l26_pm_enter')
        self.intercept('cs40l26_num_waves')
        self.intercept('cl_dsp_get_reg' if self.modern else 'cl_dsp_get_coeff')
        self.put64(CTX, 0x4060000)
        self.head = CTX + (0x58 if self.modern else 0x60)
        self.put64(self.head, self.head)
        self.put64(self.head+8, self.head)
        self.put64(INPUT+(0x2c0 if self.modern else 0x2d8), CTX)
        self.put64(INPUT+0xf8, FF)
        self.put64(FF+(0x78 if self.modern else 0x80), EFFECTS)
        self.upload_work = CTX+(0x120 if self.modern else 0x158)
        self.erase_work = CTX+(0x140 if self.modern else 0x188)
        self.upload_result = CTX+(0x1f8 if self.modern else 0x250)
        self.erase_result = CTX+(0x1fc if self.modern else 0x254)
        self.state_address = CTX+(0x1d0 if self.modern else 0x228)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(5)]
        result = None
        if name in self.failures:
            self.calls.append(name)
            result = self.failures[name]
        elif name == 'cs40l26_pm_enter':
            self.calls.append(name)
            result = self.pm_error
        elif name == 'cs40l26_num_waves':
            self.calls.append(name)
            result = 5  # Hardware-dependent diagnostic query, outside this test.
        elif name == 'queue_work_on':
            self.calls.append(name)
            self.queued.append(args[2])
            self.queue = args
            result = 1
        elif name == 'flush_work':
            self.calls.append(name)
            assert args[0] in self.queued, ('flush without queue', args)
            self.pending_flush = args[0]
            result = 1
        elif name == '__msecs_to_jiffies':
            self.calls.append(name)
            self.waits.append(args[0])
            result = args[0]  # Fixture HZ=1000; no wall-clock sleep.
        elif name == 'wait_for_completion_timeout':
            self.calls.append(name)
            assert self.waits and args[1] == self.waits[-1]
            if self.completion: self.put32(self.state_address, 0)
            result = self.completion
        elif name == 'devm_input_allocate_device':
            self.calls.append(name)
            result = INPUT
        elif name == 'input_set_capability':
            self.calls.append(name)
            self.capabilities.append((args[1], args[2]))
            result = 0
        elif name == 'input_ff_create':
            self.calls.append(name)
            assert args[1] == 96
            self.put64(INPUT+0xf8, FF)
            self.put64(INPUT+0xc0, 1 << 16)  # input core emulated rumble flag.
            result = 0
        elif name == 'input_register_device':
            self.calls.append(name)
            self.registered = True
            result = 0
        elif name == 'sysfs_create_groups':
            self.calls.append(name)
            result = 0
        elif name in ('_dev_info', '_printk'):
            self.calls.append(name)
            result = 0
        elif name == 'devm_kfree':
            self.freed.append(args[1])
        if result is None:
            return super().on_code(uc, address, size, data)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
        if name == 'flush_work': uc.emu_stop()

    def run(self, name, *args):
        for i, value in enumerate(args): self.uc.reg_write(UC_ARM64_REG_X0+i, value & MASK)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        start = self.symbols[name]
        for _ in range(4):
            self.uc.emu_start(start, self.return_address, timeout=2000000, count=100000)
            if self.pending_flush is None:
                assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, ('budget', name)
                result = self.arg(0) & 0xffffffff
                return result if result < (1 << 31) else result - (1 << 32)
            work = self.pending_flush
            self.pending_flush = None
            saved = self.uc.context_save()
            worker = {self.upload_work: 'cs40l26_upload_worker', self.erase_work: 'cs40l26_erase_worker'}[work]
            self.uc.reg_write(UC_ARM64_REG_X0, work)
            self.uc.reg_write(UC_ARM64_REG_SP, 0x500fff0)
            self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
            self.uc.emu_start(self.symbols[worker], self.return_address, timeout=2000000, count=100000)
            assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, ('worker budget', worker)
            assert self.pending_flush is None
            self.uc.context_restore(saved)
            start = self.uc.reg_read(UC_ARM64_REG_PC)
        raise AssertionError(('flush budget', name))

    def upload_effect(self, effect):
        self.uc.mem_write(EFFECT, effect)
        self.uc.mem_write(EFFECTS+7*48, effect)
        return self.run('cs40l26_upload_effect', INPUT, EFFECT, 0)

    def erase_effect(self):
        return self.run('cs40l26_erase_effect', INPUT, 7)

    def slots(self):
        data = next(self.bases[i] for i,s in enumerate(self.sections) if s.name == '.data')
        base = data+(0x3960 if self.modern else 0xbe8)
        return [self.u32(base+32*i+24) for i in range(5)]


def exercise(path, effect):
    cases = []
    def passed(name, **details): cases.append(dict(case=name, status='PASS', **details))
    m = Lifecycle(path)
    assert m.run('cs40l26_input_init', CTX) == 0
    input_name = m.string(m.u64(INPUT))
    assert input_name == 'cs40l26_input'
    assert m.capabilities == [(21,81),(21,93),(21,90),(21,96)]
    assert m.u64(INPUT+0xc0) & (1 << 16) == 0
    assert m.registered
    for offset, symbol in [(0,'cs40l26_upload_effect'),(16,'cs40l26_playback_effect'),(24,'cs40l26_set_gain'),(8,'cs40l26_erase_effect')]:
        assert m.u64(FF+offset) == m.symbols[symbol], (offset, symbol)
    input_contract = dict(name=input_name, capabilities=m.capabilities, ff_max_effects=96,
                          rumble_flag_enabled=bool(m.u64(INPUT+0xc0) & (1 << 16)),
                          callbacks={symbol:hex(m.u64(FF+offset))
                                     for offset,symbol in [(0,'cs40l26_upload_effect'),
                                                           (8,'cs40l26_erase_effect'),
                                                           (16,'cs40l26_playback_effect'),
                                                           (24,'cs40l26_set_gain')]})
    passed('input-register-capabilities-callbacks', contract=input_contract)
    for name,error in [('devm_input_allocate_device',0),('input_ff_create',-12),('input_register_device',-5),('sysfs_create_groups',-5)]:
        m = Lifecycle(path)
        m.failures[name] = error
        assert m.run('cs40l26_input_init', CTX) == (-12 if error == 0 else error)
        assert m.registered == (name == 'sysfs_create_groups')
        passed('input-failure-'+name)
    m = Lifecycle(path)
    for repetition in range(12):
        assert m.upload_effect(effect) == 0
        assert m.slots() == [7,0xffffffff,0xffffffff,0xffffffff,0xffffffff]
        assert m.u64(m.head) != m.head
        assert m.run('cs40l26_playback_effect', INPUT, 7, 1) == 0
        # State updated by the unexecuted hardware start worker/IRQ is injected.
        m.put32(m.state_address, 0)
        assert m.erase_effect() == 0
        assert m.slots() == [0xffffffff]*5
        assert m.u64(m.head) == m.head and m.u64(m.head+8) == m.head
    assert len(m.freed) == 12
    passed('twelve-upload-play-erase-roundtrips', repetitions=12)
    for completed in (0,1):
        m = Lifecycle(path)
        assert m.upload_effect(effect) == 0
        m.put32(m.state_address, 1)
        m.completion = completed
        rc = m.erase_effect()
        assert rc == (0 if completed else -62), (rc,m.calls)
        assert m.waits == [580]  # Captured 80 ms + 500 ms original driver grace.
        assert m.slots()[0] == (0xffffffff if completed else 7)
        passed('active-erase-'+('completion' if completed else 'timeout'), wait_ms=m.waits[0], result=rc)
    for failure in (1,2,3):
        m = Lifecycle(path)
        m.fail_register = failure
        assert m.upload_effect(effect) == -5
        assert m.u64(m.head) == m.head
        assert len(m.freed) == 1
        passed('upload-worker-register-failure-'+str(failure))
    m = Lifecycle(path)
    m.pm_error = -5
    assert m.upload_effect(effect) == 0 and not m.registers
    assert m.u64(m.head) == m.head
    passed('PM-upload-error-leaves-zero-status', observed_result=0, pm_result=-5)
    m = Lifecycle(path)
    assert m.upload_effect(effect) == 0
    m.pm_error = -5
    assert m.erase_effect() == 0 and m.slots()[0] == 7
    assert m.u64(m.head) != m.head
    passed('PM-erase-error-leaves-effect-and-zero-status', observed_result=0, pm_result=-5)
    return cases


def wrapper_exercise(path):
    """OS4 composite module success does not imply a bound Cirrus device."""
    cases = []
    for init_error in (0,-5):
        m = Lifecycle(path)
        for name in ['xring_smartpa_i2c_init','xring_haptic_i2c_init','codec_init','fm_init']:
            m.intercept(name)
            m.failures[name] = init_error
        assert m.run('init_module') == 0
        cases.append(dict(case=f'OS4-module-init-child-result-{init_error}',status='PASS',
                          observed_module_result=0, child_result=init_error))
    m = Lifecycle(path)
    for name,result in [('i2c_client_get_device_id',0x4070000),('of_device_get_match_data',1),
                        ('cs40l26_i2c_probe',-5),('snd_soc_register_component',0)]:
        if name in m.symbols: m.intercept(name)
        m.failures[name] = result
    for attempt,expected in enumerate([-517,-517,-517,0],1):
        assert m.run('xring_haptic_i2c_probe',0x4080000) == expected
        cases.append(dict(case=f'OS4-wrapper-failed-probe-attempt-{attempt}',status='PASS',
                          cirrus_probe_result=-5, wrapper_result=expected))
    assert m.calls.count('snd_soc_register_component') == 1
    assert not m.registered
    return cases


def main():
    cases, drivers = [], {}
    with tempfile.TemporaryDirectory(prefix='dijun-ff-lifecycle-') as temporary:
        fixtures = capture(Path(temporary))
        effect = next(e for n,e,v in fixtures if n == 80)
        for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
            sample = profile.parent.name
            analysis = ROOT/'firmware/samples'/sample/'analysis'
            module,_ = haptics_module(json.loads((analysis/'facts.json').read_text()))
            path = analysis/module
            current = exercise(path,effect)
            if LAYOUTS[sha(path)] == 'modern': current += wrapper_exercise(path)
            cases += [dict(sample=sample,**c) for c in current]
            drivers[sample] = dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
            print('PASS',sample,len(current),'cases',flush=True)
    sources = [SOURCE,SOURCE.with_suffix('.h')]
    tests = [Path(__file__),ROOT/'tests/haptics_driver_emulation.py',ROOT/'tests/haptics_driver_capture.cpp',ROOT/'scripts/firmware_facts.py',ROOT/'tests/haptics-emulator-dependencies.json']
    report = dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,
                  sources={str(p):sha(p) for p in sources},tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)):sha(p) for p in sorted(DEPS.rglob('*')) if p.is_file() and p.suffix in ('.py','.so')})
    (ROOT/'logs/haptics-lifecycle-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__ == '__main__': main()
