#!/usr/bin/env python3
"""Execute original ARM64 start/stop workers and early firmware/I2C wrappers.

Upload and playback callbacks use the existing lifecycle fixture. Runtime PM,
DSP symbol lookup, mailbox, state update and sleep are explicit boundaries.
Firmware tests stop at request/parse failures; I2C wrapper substitutes core probe.
No full probe, DSP boot, IRQ, kernel workqueue or motor is simulated.
"""
import json
from pathlib import Path
import struct
import tempfile

from haptics_lifecycle_emulation import Lifecycle, CTX, INPUT
from haptics_driver_emulation import ROOT, DEPS, SOURCE, MASK, LAYOUTS, sha, capture
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30
from firmware_facts import haptics_module


class Playback(Lifecycle):
    def __init__(self, path):
        super().__init__(path)
        self.start_work = CTX+(0xc0 if self.modern else 0xc8)
        self.stop_work = CTX+(0xe0 if self.modern else 0xf8)
        self.mailbox = []
        self.mailbox_error = 0
        self.states = []
        self.sleeps = []
        self.lookup_error = 0
        self.lookup_count = 0
        for name in ['cs40l26_get_ram_ext_algo_id','cs40l26_mailbox_write',
                     'cs40l26_vibe_state_update','cs40l26_pm_exit']:
            if name in self.symbols: self.intercept(name)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(5)]
        result = None
        if name == 'cs40l26_get_ram_ext_algo_id':
            self.put32(args[1], 0x1f206)
            result = 0
        elif name == 'cs40l26_mailbox_write':
            self.mailbox.append(args[1])
            result = self.mailbox_error
        elif name == 'cs40l26_vibe_state_update':
            self.states.append(args[1])
            result = 0  # Does not inject IRQ/completion or change vibe_state.
        elif name == 'cs40l26_pm_exit': result = 0
        elif name == 'usleep_range_state':
            self.sleeps.append(args[:3])
            result = 0
        elif name in ('cl_dsp_get_coeff','cl_dsp_get_reg'):
            self.lookup_count += 1
            if self.lookup_count == self.lookup_error:
                result = -5
        if result is None: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def prepare(self, effect):
        assert self.upload_effect(effect) == 0
        assert self.run('cs40l26_playback_effect',INPUT,7,1) == 0
        assert self.queued[-1] == self.start_work
        self.registers.clear()
        self.lookup_count = 0

    def start(self): self.run('cs40l26_vibe_start_worker',self.start_work)
    def stop(self):
        assert self.run('cs40l26_playback_effect',INPUT,7,0) == 0
        assert self.queued[-1] == self.stop_work
        self.run('cs40l26_vibe_stop_worker',self.stop_work)


class Initialization(Playback):
    def __init__(self,path):
        super().__init__(path)
        self.request_error = -2
        self.parse_error = -22
        self.requests = []
        self.released = []
        self.parses = []
        self.regmap_result = 0x4070000
        self.probe_result = 0
        self.probed_context = None
        for name in ['cl_dsp_create','cl_dsp_destroy','cl_dsp_firmware_parse','cl_dsp_wavetable_create',
                     'cs40l26_probe']:
            if name in self.symbols: self.intercept(name)

    def on_code(self,uc,address,size,data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(5)]
        result = None
        if name == '__devm_regmap_init_i2c': result = self.regmap_result
        elif name == 'cs40l26_probe':
            self.probed_context = args[0]
            result = self.probe_result
        elif name == 'cl_dsp_create': result = 0x4080000
        elif name in ['cl_dsp_destroy','cl_dsp_wavetable_create']: result = 0
        elif name == 'request_firmware':
            self.requests.append(self.string(args[1]))
            self.put64(args[0],0 if self.request_error else 0x4090000)
            result = self.request_error
        elif name == 'release_firmware':
            self.released.append(args[0])
            result = 0
        elif name == 'cl_dsp_firmware_parse':
            self.parses.append(args[:3])
            result = self.parse_error
        if result is None: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path,effect):
    cases=[]
    def passed(name,**details): cases.append(dict(case=name,status='PASS',**details))
    m=Playback(path);m.prepare(effect);m.start()
    assert [r['value'] for r in m.registers] == [80,0],m.registers
    assert m.mailbox == [0x1800081],m.mailbox
    assert m.states == [0]
    passed('upload-callback-start-worker',registers=list(m.registers),mailbox=list(m.mailbox))
    m.stop()
    assert m.mailbox == [0x1800081,0x5000000]
    passed('stop-callback-worker',mailbox=m.mailbox[-1:])
    for failure in [1,2]:
        m=Playback(path);m.prepare(effect);m.fail_register=failure;m.start()
        assert len(m.registers)==failure and not m.mailbox and not m.states
        passed(f'start-register-error-{failure}')
    for failure in [1,2]:
        m=Playback(path);m.prepare(effect);m.lookup_error=failure;m.start()
        assert len(m.registers)==failure-1 and not m.mailbox and not m.states
        passed(f'start-symbol-error-{failure}')
    m=Playback(path);m.prepare(effect);m.mailbox_error=-5;m.start()
    assert len(m.registers)==2 and m.mailbox == [0x1800081] and not m.states
    passed('start-mailbox-error-no-state-update')
    m=Playback(path);m.prepare(effect);m.pm_error=-5;m.start()
    assert not m.registers and not m.mailbox and not m.states
    passed('start-PM-error-no-send')
    m=Playback(path);m.prepare(effect)
    m.put64(m.head,m.head);m.put64(m.head+8,m.head)
    m.start();assert not m.registers and not m.mailbox
    passed('start-missing-upload-record-no-send')
    m=Playback(path);m.prepare(effect)
    # Delay is a driver microsecond field, not a host wall-clock sleep.
    m.put32(CTX+(0x1f4 if m.modern else 0x24c),1200)
    m.stop();assert m.sleeps == [[1200,1300,2]] and m.mailbox == [0x5000000]
    passed('stop-configured-delay',sleep_request=m.sleeps)
    m=Playback(path);m.prepare(effect);m.pm_error=-5;m.stop()
    assert not m.mailbox
    passed('stop-PM-error-no-send')
    m=Playback(path);m.prepare(effect);m.mailbox_error=-5;m.stop()
    assert m.mailbox == [0x5000000] and not m.states
    passed('stop-mailbox-error')
    for alternate,filename in [(0,'cs40l26.wmfw'),(1,'cs40l26-calib.wmfw')]:
        m=Initialization(path)
        m.uc.mem_write(CTX+(0x1cb if m.modern else 0x223),bytes([alternate]))
        assert m.run('cs40l26_fw_upload',CTX)==-2
        assert m.requests==[filename],m.requests
        assert m.released==[0] and not m.parses and not m.registers
        passed('firmware-request-missing-'+str(alternate),filename=filename,result=-2)
    m=Initialization(path);m.request_error=0
    # Explicit flag bypasses hardware DSP preconfigure, ending at parse failure.
    m.uc.mem_write(CTX+(0x1c9 if m.modern else 0x221),b'\1')
    assert m.run('cs40l26_fw_upload',CTX)==-22
    assert m.requests==['cs40l26.wmfw'] and m.released==[0x4090000]
    assert len(m.parses)==1 and not m.registers
    passed('firmware-parse-failure-release',result=-22)
    for name,alloc,regmap,core,expected in [
        ('allocate',0,0x4070000,0,-12),('regmap',None,-5,0,-5),
        ('core-defer',None,0x4070000,-517,-517),('core-failure',None,0x4070000,-5,-5),
        ('core-success',None,0x4070000,0,0)]:
        m=Initialization(path);m.regmap_result=regmap;m.probe_result=core
        if alloc==0:m.failures['devm_kmalloc']=0
        client=0x40a0000
        m.put32(client+(0x3c4 if m.modern else 0x3cc),23)
        assert m.run('cs40l26_i2c_probe',client)==expected
        if name.startswith('core-'):
            ctx=m.probed_context
            assert ctx and m.u64(client+0xb8)==ctx
            assert m.u64(ctx)==client+0x20 and m.u64(ctx+8)==regmap
            assert m.u32(ctx+(0x168 if m.modern else 0x1c0))==23
        else:assert m.probed_context is None
        passed('I2C-wrapper-'+name,result=expected)
    return cases


def main():
    cases,drivers=[],{}
    with tempfile.TemporaryDirectory(prefix='dijun-play-workers-') as temp:
        effect=next(e for n,e,_ in capture(Path(temp)) if n==80)
        for profile in sorted((ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')):
            sample=profile.parent.name;analysis=ROOT/'firmware/samples'/sample/'analysis'
            path=analysis/haptics_module(json.loads((analysis/'facts.json').read_text()))[0]
            assert sha(path) in LAYOUTS
            current=exercise(path,effect)
            cases.extend(dict(sample=sample,**c) for c in current)
            drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
            print('PASS',sample,len(current),'cases',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/haptics_lifecycle_emulation.py',
           ROOT/'tests/haptics_driver_emulation.py',ROOT/'tests/haptics_driver_capture.cpp',
           ROOT/'scripts/firmware_facts.py',ROOT/'tests/haptics-emulator-dependencies.json']
    report=dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,
                sources={str(p):sha(p) for p in [SOURCE,SOURCE.with_suffix('.h')]},
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in sorted(DEPS.rglob('*'))
                                if p.is_file() and p.suffix in ('.py','.so')})
    (ROOT/'logs/haptics-playback-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)

if __name__=='__main__':main()
