#!/usr/bin/env python3
"""Execute original OS4 IRQ switches, PM callbacks and parser/ISR gates.

IRQ descriptors/depth, wake return values, locks and sleep completion are explicit
kernel fixtures, not a running IRQ controller or concurrent kernel. Sleep records
requested durations without waiting. ISR packets/configuration are synthetic;
no hardware latency, physical delivery or current fault root cause is asserted.
Unknown services and execution-budget exhaustion fail, except one named unchanged
IRQ-depth fixture which must exhaust the finite budget before its flag is set.
"""
import json
from pathlib import Path
import struct
import subprocess

from touch_configuration_emulation import Configuration, CTX, CORE, HW, PLATFORM, FW
from touch_startup_emulation import INPUT
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

DESC = 0x40d0000


class IRQ(Configuration):
    def __init__(self, path):
        super().__init__(path)
        self.irq_actions, self.waits, self.wakes, self.completions = [], [], [], []
        self.clear_after = None
        self.decrement = True
        self.wake_result = 0
        self.sensorhub = 0
        self.put32(HW+0x68, 76)  # explicit Linux IRQ number, not DT GPIO pin
        self.put32(DESC+0x88, 1)
        self.put64(HW+0x138, self.symbols['syna_spi_enable_irq'])
        self.put64(PLATFORM+0x98, CTX)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        handled = ['irq_to_desc', 'enable_irq', 'disable_irq_nosync',
                   'irq_set_irq_wake', 'msleep', 'complete', 'xiaomi_get_sensorhub_status']
        if name not in handled:
            return super().on_code(uc, address, size, data)
        args = [self.arg(i) for i in range(3)]
        if name == 'irq_to_desc':
            assert args[0] == 76
            result = DESC
        elif name == 'enable_irq':
            depth = self.u32(DESC+0x88)
            self.irq_actions.append([name, args[0], depth])
            if self.decrement and depth:
                self.put32(DESC+0x88, depth-1)
            result = 0
        elif name == 'disable_irq_nosync':
            depth = self.u32(DESC+0x88)
            self.irq_actions.append([name, args[0], depth])
            self.put32(DESC+0x88, depth+1)
            result = 0
        elif name == 'irq_set_irq_wake':
            self.wakes.append(args[:2])
            result = self.wake_result
        elif name == 'msleep':
            self.waits.append(args[0])
            if self.clear_after == len(self.waits):
                self.put32(CORE+0x1d0, 0)
            result = 0
        elif name == 'complete':
            self.completions.append(args[0])
            result = 0
        else:
            result = self.sensorhub
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def byte(self, address):
        return bytes(self.uc.mem_read(address, 1))[0]

    def flag(self, address, value):
        self.uc.mem_write(address, bytes([value]))

    def packet(self):
        assert self.acquire() == 0
        self.put64(CTX+0x2c0, FW+0x4000)
        self.put32(CTX+0x2cc, 8)
        self.uc.mem_write(FW+0x4000, struct.pack('<BBHHBB', 0, 1, 644, 1589, 7, 6))


def exercise(path):
    cases = []

    def passed(label, m, result=None, **details):
        cases.append(dict(case=label, status='PASS', result=result,
            irq_actions=m.irq_actions, requested_sleeps_ms=m.waits,
            wake_requests=m.wakes, completions=m.completions,
            irq_depth=m.u32(DESC+0x88), irq_flag=m.byte(HW+0x6c),
            wake_flag=m.byte(CTX+0x30c), pm_flag=m.byte(CTX+0x6c8),
            events=m.events, **details))

    for depth in [0, 1, 3]:
        m = IRQ(path); m.put32(DESC+0x88, depth)
        assert m.run('syna_spi_enable_irq', HW, 1) == 0
        assert m.irq_actions == [['enable_irq', 76, n] for n in range(depth, 0, -1)] or (
            depth == 0 and m.irq_actions == [['enable_irq', 76, 0]])
        assert m.byte(HW+0x6c) == 1 and m.u32(DESC+0x88) == 0
        passed('enable-depth-'+str(depth), m, 0)
    m = IRQ(path); m.flag(HW+0x6c, 1); m.put32(DESC+0x88, 3)
    assert m.run('syna_spi_enable_irq', HW, 1) == 0 and not m.irq_actions
    assert m.u32(DESC+0x88) == 3
    passed('enable-stale-flag-skips-depth', m, 0)
    for enabled in [0, 1]:
        m = IRQ(path); m.flag(HW+0x6c, enabled)
        assert m.run('syna_spi_enable_irq', HW, 0) == 0
        assert len(m.irq_actions) == enabled and m.byte(HW+0x6c) == 0
        assert m.u32(DESC+0x88) == 1+enabled
        passed('disable-flag-'+str(enabled), m, 0)
    m = IRQ(path); m.put32(HW+0x68, 0)
    assert m.run('syna_spi_enable_irq', HW, 1) == 0 and not m.irq_actions
    assert m.byte(HW+0x6c) == 0
    passed('zero-IRQ-success-without-enabling', m, 0)
    m = IRQ(path); m.put32(DESC+0x88, 2); m.decrement = False
    try:
        m.run('syna_spi_enable_irq', HW, 1)
    except AssertionError as exc:
        assert exc.args[0] == ('emulation budget', 'syna_spi_enable_irq'), exc
    else:
        raise AssertionError('unchanged depth unexpectedly completed')
    assert len(m.irq_actions) > 100 and m.byte(HW+0x6c) == 0
    assert all(a == ['enable_irq', 76, 2] for a in m.irq_actions)
    passed('unchanged-depth-budget', m, execution='finite budget exhausted as expected')

    for wake_result in [0, -5]:
        m = IRQ(path); m.wake_result = wake_result
        m.run('syna_tcm_enable_irq', 1)  # void: do not treat x0 as a result
        assert m.byte(HW+0x6c) == m.byte(CTX+0x30c) == 1
        assert m.wakes == [[76, 1]]
        m.run('syna_tcm_enable_irq', 1)
        assert len(m.irq_actions) == len(m.wakes) == 1
        passed('wake-enable-result-'+str(wake_result), m, wake_result=wake_result)
    for clear_after, expected_waits in [(None, 150), (1, 1), (3, 3)]:
        m = IRQ(path); m.flag(HW+0x6c, 1); m.flag(CTX+0x30c, 1)
        m.put32(DESC+0x88, 0); m.put32(CORE+0x1d0, 1)
        m.clear_after = clear_after; m.wake_result = -5
        m.run('syna_tcm_enable_irq', 0)
        assert m.waits == [20]*expected_waits
        assert m.irq_actions == [['disable_irq_nosync', 76, 0]]
        assert m.wakes == [[76, 0]] and m.byte(CTX+0x30c) == m.byte(HW+0x6c) == 0
        passed('disable-pending-'+str(clear_after), m, wake_result=-5)
    for label in ['no-context', 'no-callback']:
        m = IRQ(path)
        if label == 'no-context':
            bss = next(m.bases[i] for i, s in enumerate(m.sections) if s.name == '.bss')
            m.put64(bss+0x1868, 0)
        else:
            m.put64(HW+0x138, 0)
        m.run('syna_tcm_enable_irq', 1)
        assert not m.irq_actions and not m.wakes
        passed(label, m)

    for name in ['syna_pm_suspend', 'syna_pm_resume']:
        m = IRQ(path); m.put64(PLATFORM+0x98, 0)
        assert m.run(name, PLATFORM) == -1
        assert not m.completions
        passed(name+'-missing-context', m, -1)
    m = IRQ(path); m.put32(CTX+0x6d0, 9)
    assert m.run('syna_pm_suspend', PLATFORM) == 0
    assert m.byte(CTX+0x6c8) == 1 and m.u32(CTX+0x6d0) == 0
    assert not m.irq_actions and not m.wakes and not m.commands
    assert m.run('syna_pm_resume', PLATFORM) == 0
    assert m.byte(CTX+0x6c8) == 0 and m.completions == [CTX+0x6d0]
    assert not m.irq_actions and not m.wakes and not m.commands
    passed('PM-roundtrip-only-flags-and-completion', m, 0)
    for sensorhub in [0, 1]:
        m = IRQ(path); m.packet(); m.sensorhub = sensorhub
        assert m.run('syna_pm_suspend', PLATFORM) == 0
        assert m.run('syna_dev_isr', 0, CTX) == 1
        assert m.byte(CTX+0x6c8) == 1
        assert 'syna_tcm_get_event_data' in m.calls
        assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
        assert [INPUT, 1, 330, 1] in m.events
        passed('ISR-PM-flag-sensorhub-'+str(sensorhub), m, 1,
               synthetic_packet=True, sensorhub=sensorhub)
    return cases


def main():
    cases, drivers, sources = [], {}, {}
    tool = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        disasm = ROOT/'logs'/f'{sample}-touch-IRQ-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool, '-dr', '--disassemble-symbols=syna_spi_enable_irq,syna_tcm_enable_irq,syna_pm_suspend,syna_pm_resume,syna_dev_isr', str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        results = exercise(path)
        cases.extend(dict(sample=sample, **c) for c in results)
        print('PASS', sample, len(results), 'IRQ/PM scenarios', flush=True)
    tests = [Path(__file__).resolve()] + [ROOT/'tests'/name for name in
        ['touch_configuration_emulation.py', 'touch_startup_emulation.py',
         'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                          (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases, drivers=drivers,
        sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in dependencies})
    (ROOT/'logs/touch-irq-emulation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS', len(cases), 'scenarios', flush=True)


if __name__ == '__main__':
    main()
