#!/usr/bin/env python3
"""Execute original OS4 display suspend/resume, sensing, IRQ and configuration.

No-gesture mode and initial device states are explicit fixtures, not captured
hardware state. Original sleep/dynamic commands run to a typed send-command
response boundary; app/config parsing and report switching execute as well.
Reset/event, thermal, power, pinctrl, IRQ depth and kernel services are fixtures.
Synthetic ISR bytes test parser delivery only, not real controller/IRQ readiness,
display notifier scheduling, physical wake latency or the user's fault cause.
"""
import json
from pathlib import Path
import subprocess

from touch_irq_emulation import IRQ, DESC, CTX, CORE, HW, PLATFORM, FW, INPUT
from touch_configuration_emulation import CONFIG
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30


class Display(IRQ):
    def __init__(self, path):
        super().__init__(path)
        self.sleep_results = []
        self.dynamic_error = 0
        self.dynamics, self.sleep_commands, self.resets, self.thermal = [], [], [], []
        self.pinctrl_results, self.pinctrl_calls = [], []
        self.reset_result = 0
        self.reset_event = 0x10
        self.in_resume = False
        self.drained_events = 0
        callback = 0x300c000
        self.put32(callback-4, 0xe10dda21)
        self.hooks[callback] = 'fixture_drain_message'
        self.put64(CORE+0x330, callback)
        self.intercept('syna_tcm_reset')
        self.intercept('syna_set_thermal_temp')
        self.flag(HW+0x6c, 1)
        self.put32(DESC+0x88, 0)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        if name is None:
            return
        args = [self.arg(i) for i in range(7)]
        if name == 'fixture_drain_message':
            uc.mem_write(args[1], b'\0')
            self.drained_events += 1
            result = -110  # explicit transport timeout during app-info retries
        elif name == 'syna_tcm_get_event_data' and self.in_resume:
            uc.mem_write(args[1], bytes([self.reset_event]))
            self.drained_events += 1
            result = self.read_error
        elif name == 'fixture_send_command' and args[1] in [44, 45, 36]:
            self.commands.append(args)
            uc.mem_write(args[5], b'\1')
            if args[1] == 36:
                assert args[3] == 3
                self.dynamics.append(bytes(uc.mem_read(args[2], args[3])).hex())
                result = self.dynamic_error
            else:
                assert args[3] == 0
                self.sleep_commands.append(args[1])
                result = self.sleep_results.pop(0) if self.sleep_results else 0
        elif name == 'syna_tcm_reset':
            self.resets.append(args[0]); result = self.reset_result
        elif name in ['enable_temperature_detection_func', 'syna_set_thermal_temp']:
            self.thermal.append([name, args[:2]]); result = 0
        elif name == 'xiaomi_get_gesture_type':
            result = 0  # no-gesture mode is a fixture, never a default for unknown APIs
        elif name == 'pinctrl_select_state':
            self.pinctrl_calls.append(args[:2])
            assert self.pinctrl_results
            result = self.pinctrl_results.pop(0)
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def resume(self):
        self.in_resume = True
        try:
            return self.run('syna_dev_resume', PLATFORM)
        finally:
            self.in_resume = False

    def emit(self):
        self.events.clear(); self.slots.clear()
        # Do not acquire/repair config before ISR: use exactly what resume left.
        self.put64(CTX+0x2c0, FW+0x4000)
        self.put32(CTX+0x2cc, 8)
        self.uc.mem_write(FW+0x4000, bytes.fromhex('0001840235060706'))
        assert self.run('syna_dev_isr', 0, CTX) == 1
        return bool(self.events)


def exercise(path):
    cases = []

    def passed(label, m, result, **details):
        cases.append(dict(case=label, status='PASS', result=result,
            state=m.u32(CTX+0x450), config_length=m.u32(CORE+0x18c),
            irq_flag=m.byte(HW+0x6c), irq_depth=m.u32(DESC+0x88),
            sleep_commands=m.sleep_commands, requested_sleeps_ms=m.waits,
            commands=[a[1] for a in m.commands], dynamics=m.dynamics,
            reports=m.reports, resets=len(m.resets), drained_events=m.drained_events,
            irq_actions=m.irq_actions, events=m.events, power=m.power,
            pinctrl_calls=m.pinctrl_calls, **details))

    # Sequential real callbacks, repeat a fast off/on without real-time waiting.
    m = Display(path)
    for _ in range(2):
        assert m.run('syna_dev_suspend', PLATFORM) == 0
        assert m.u32(CTX+0x450) == 0 and m.byte(HW+0x6c) == 0
        assert m.resume() == 0 and m.u32(CORE+0x18c) == len(CONFIG)
        assert m.emit() and [INPUT, 3, 53, 64400] in m.events
    assert m.waits == [100, 100] and m.sleep_commands == [44, 44]
    assert m.reports == [[CORE, 192, 0], [CORE, 17, 1]]*2
    passed('two-display-roundtrips', m, 0)

    m = Display(path)
    assert m.run('syna_dev_suspend', PLATFORM) == 0
    m.config_command_error = -110
    assert m.resume() == -110 and not m.emit()
    m.config_command_error = 0
    before = len(m.commands)
    assert m.resume() == 0 and len(m.commands) == before and not m.emit()
    assert m.run('syna_dev_suspend', PLATFORM) == 0
    assert m.resume() == 0 and m.u32(CORE+0x18c) == 13
    assert m.emit() and [INPUT, 3, 53, 64400] in m.events
    passed('config-failure-next-display-cycle-recovers', m, 0,
           direct_resume_repaired_config=False, next_cycle_repaired_config=True)

    for label in ['config-timeout', 'config-empty', 'app-timeout', 'bootloader',
                  'read-timeout', 'unexpected-reset-report', 'software-reset-fails',
                  'report-first-error', 'report-second-error', 'report-both-errors',
                  'raw-mode-retained', 'power-fails', 'pinctrl-error-ignored']:
        m = Display(path)
        assert m.run('syna_dev_suspend', PLATFORM) == 0
        if label == 'config-timeout': m.config_command_error = -110
        if label == 'config-empty': m.config = b''
        if label == 'app-timeout': m.command_error = -110
        if label == 'bootloader': m.flag(CORE+1, 11)
        if label == 'read-timeout': m.read_error = -110
        if label == 'unexpected-reset-report': m.reset_event = 0x11
        if label == 'software-reset-fails': m.read_error = -110; m.reset_result = -110
        if label == 'report-first-error': m.report_results = [-5, 0]
        if label == 'report-second-error': m.report_results = [0, -110]
        if label == 'report-both-errors': m.report_results = [-5, -110]
        if label == 'raw-mode-retained': m.flag(CTX+0x6ac, 1)
        if label in ['power-fails', 'pinctrl-error-ignored']:
            m.flag(CTX+0x6f1, 1)
            m.put64(HW+0xf0, FW+0x8000); m.put64(HW+0xf8, FW+0x8100)
            m.pinctrl_results = [-5]
            if label == 'power-fails': m.results['fixture_power'] = -5
        rc = m.resume()
        failures = {'config-timeout':-110, 'config-empty':-22, 'app-timeout':-110,
            'bootloader':-22, 'read-timeout':-5, 'unexpected-reset-report':-5,
            'software-reset-fails':-5, 'power-fails':-19}
        assert rc == failures.get(label, 0), (label, rc)
        if label == 'power-fails':
            assert m.u32(CTX+0x450) == 0 and [a[1] for a in m.commands] == [44]
            assert m.byte(HW+0x6c) == 0
        else:
            assert m.u32(CTX+0x450) == 1 and m.byte(HW+0x6c) == 1
            before = (len(m.commands), len(m.calls), len(m.irq_actions))
            assert m.resume() == 0
            assert before == (len(m.commands), len(m.calls), len(m.irq_actions))
            no_config = label in failures or label == 'config-empty'
            assert m.u32(CORE+0x18c) == (0 if no_config else 13)
            assert m.emit() == (not no_config)
            if not no_config:
                assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
            if label.startswith('report-'):
                assert m.reports == [[CORE, 192, 0], [CORE, 17, 1]]
            if label == 'raw-mode-retained': assert not m.reports
        passed(label, m, rc, second_resume_skips_recovery=label!='power-fails')

    for label in ['suspend-sleep-error', 'suspend-pending', 'suspend-sleep-skipped',
                  'already-active-resume', 'already-suspended-suspend']:
        m = Display(path)
        if label == 'already-active-resume':
            assert m.resume() == 0 and not m.calls
            passed(label, m, 0); continue
        if label == 'already-suspended-suspend':
            m.put32(CTX+0x450, 0)
            assert m.run('syna_dev_suspend', PLATFORM) == 0 and not m.calls
            passed(label, m, 0); continue
        if label == 'suspend-sleep-error': m.sleep_results = [-110]
        if label == 'suspend-pending': m.put32(CORE+0x1d0, 1)
        if label == 'suspend-sleep-skipped': m.flag(CTX+0x454, 1)
        rc = m.run('syna_dev_suspend', PLATFORM)
        assert rc == (-110 if label == 'suspend-sleep-error' else 0)
        assert m.u32(CTX+0x450) == 0
        assert len(m.irq_actions) == (0 if label == 'suspend-sleep-error' else 1)
        assert m.waits == ([20]*3 if label == 'suspend-pending' else [])
        assert m.sleep_commands == ([] if label == 'suspend-sleep-skipped' else [44])
        passed(label, m, rc)

    for label in ['normal-sensing', 'normal-retry', 'normal-exhausted', 'dynamic-exhausted']:
        m = Display(path); m.put32(CTX+0x450, 0); m.flag(CTX+0x690, 1)
        if label == 'normal-retry': m.sleep_results = [-110, 0]
        if label == 'normal-exhausted': m.sleep_results = [-110]*4
        if label == 'dynamic-exhausted': m.dynamic_error = -5
        rc = m.resume()
        assert rc == ({'normal-exhausted':-110, 'dynamic-exhausted':-5}.get(label, 0)), (label, rc)
        count = 4 if label.endswith('exhausted') else (2 if label == 'normal-retry' else 1)
        assert m.sleep_commands == [45]*count
        assert m.dynamics == ([] if label == 'normal-exhausted' else ['090000']*(4 if label=='dynamic-exhausted' else 1))
        assert m.drained_events == int(label.endswith('exhausted'))
        assert m.u32(CTX+0x450) == 1
        assert m.u32(CORE+0x18c) == (13 if rc == 0 else 0)
        assert m.emit() == (rc == 0)
        assert m.resume() == 0  # active short-circuit even after exhausted recovery
        passed(label, m, rc)
    return cases


def main():
    cases, drivers, sources = [], {}, {}
    tool = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    symbols = 'syna_dev_suspend,syna_dev_resume,syna_dev_enter_normal_sensing,syna_dev_enter_lowpwr_sensing,syna_dev_set_up_app_fw,syna_tcm_sleep,syna_tcm_set_dynamic_config'
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        disasm = ROOT/'logs'/f'{sample}-touch-display-resume-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool, '-dr', '--disassemble-symbols='+symbols, str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        results = exercise(path)
        cases.extend(dict(sample=sample, **c) for c in results)
        print('PASS', sample, len(results), 'display scenarios', flush=True)
    tests = [Path(__file__).resolve()] + [ROOT/'tests'/name for name in
        ['touch_irq_emulation.py', 'touch_configuration_emulation.py', 'touch_startup_emulation.py',
         'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                          (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases, drivers=drivers,
        sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in dependencies})
    (ROOT/'logs/touch-display-resume-emulation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS', len(cases), 'scenarios', flush=True)


if __name__ == '__main__':
    main()
