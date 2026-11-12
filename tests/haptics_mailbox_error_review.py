#!/usr/bin/env python3
"""Execute stock OS4 mailbox retry and stop-worker error branches.

Registers, runtime-PM return values, sleeps, locks, error recovery and PM exit
are explicit fixtures. Original mailbox, pm_enter and stop worker execute;
this does not execute runtime-PM core, DSP acknowledgement, I2C or the motor.
"""
import json
from pathlib import Path
from haptics_driver_emulation import (
    Module, ROOT, DEPS, MASK, sha, UC_ARM64_REG_X0,
    UC_ARM64_REG_PC, UC_ARM64_REG_X30,
)

CTX = 0x4000000
DEVICE = 0x4060000
REGMAP = 0x4070000


class Mailbox(Module):
    def __init__(self, path):
        super().__init__(path)
        self.put64(CTX, DEVICE)
        self.put64(CTX + 8, REGMAP)
        self.write_errors = []
        self.read_results = []
        self.writes = []
        self.reads = []
        self.sleeps = []
        self.logs = []
        self.pm_result = 0
        self.recovery = []
        self.pm_exits = []
        self.intercept('cs40l26_resume_error_handle')
        self.intercept('cs40l26_pm_exit')

    def on_code(self, u, address, size, data):
        name = self.hooks.get(address)
        if name == 'regmap_write':
            assert self.arg(0) == REGMAP and self.arg(1) == 0x13020
            assert self.write_errors, 'unexpected mailbox write'
            result = self.write_errors.pop(0)
            self.writes.append(dict(command=self.arg(2), result=result))
        elif name == 'regmap_read':
            assert self.arg(0) == REGMAP and self.arg(1) == 0x13020
            assert self.read_results, 'unexpected mailbox read'
            result, value = self.read_results.pop(0)
            if result == 0:
                self.put32(self.arg(2), value)
            self.reads.append(dict(result=result, value=value if result == 0 else None))
        elif name == 'usleep_range_state':
            assert [self.arg(i) for i in range(3)] == [1000, 1100, 2]
            self.sleeps.append([1000, 1100])
            result = 0
        elif name in ('_dev_printk', '_dev_err', '_dev_info'):
            fmt = self.string(self.arg(2 if name == '_dev_printk' else 1))
            self.logs.append(dict(function=name, format=fmt,
                                  arguments=[self.arg(i) for i in range(3 if name == '_dev_printk' else 2, 6)]))
            result = 0
        elif name == '__pm_runtime_resume':
            assert self.arg(0) == DEVICE and self.arg(1) == 4
            result = self.pm_result
        elif name == 'cs40l26_resume_error_handle':
            assert self.arg(0) == DEVICE
            self.recovery.append(self.arg(1) & 0xffffffff)
            result = 0
        elif name == 'cs40l26_pm_exit':
            self.pm_exits.append(self.arg(0))
            assert self.arg(0) == DEVICE
            result = 0
        else:
            return super().on_code(u, address, size, data)
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0, result & MASK)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))


def main():
    cases = []
    sources = {}
    # Each list is a finite, exact boundary schedule, not a hardware model.
    schedules = {
        'ack-zero': ([0], [(0, 0)], 0, 0),
        'first-write-NACK': ([-5, 0], [(0, 0)], 0, 1),
        'last-write-succeeds': ([-5] * 19 + [0], [(0, 0)], 0, 19),
        'write-exhausted': ([-5] * 20, [], -62, 20),
        'first-read-error': ([0], [(-5, 0), (0, 0)], 0, 1),
        'read-exhausted': ([0], [(-5, 0)] * 20, -62, 20),
        'busy-19-then-zero': ([0], [(0, 1)] * 19 + [(0, 0)], 0, 19),
        'busy-20-timeout': ([0], [(0, 1)] * 20, -110, 20),
        'busy-resets-read-retries': ([0], [(-5, 0)] * 19 + [(0, 1)] +
                                    [(-5, 0)] * 19 + [(0, 0)], 0, 39),
    }
    for sample in ('os4-current', 'os4-stable'):
        path = ROOT / f'firmware/samples/{sample}/analysis/vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        assert sha(path) == '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        sources[str(path.relative_to(ROOT))] = sha(path)
        for label, (writes, reads, expected, sleeps) in schedules.items():
            m = Mailbox(path)
            m.write_errors = writes[:]
            m.read_results = reads[:]
            rc = m.run('cs40l26_mailbox_write', CTX, 0x5000000)
            assert rc == expected, (sample, label, rc)
            assert not m.write_errors and not m.read_results
            assert len(m.sleeps) == sleeps
            assert [w['result'] for w in m.writes] == writes
            assert [r['result'] for r in m.reads] == [r[0] for r in reads]
            assert all(w['command'] == 0x5000000 for w in m.writes)
            cases.append(dict(sample=sample, case=label, entry='cs40l26_mailbox_write',
                              status='PASS', result=rc, writes=m.writes, reads=m.reads,
                              sleep_count=len(m.sleeps), logs=m.logs))
        for label in ('write-exhausted', 'read-exhausted', 'PM-error'):
            m = Mailbox(path)
            if label == 'PM-error':
                m.pm_result = -5
            else:
                writes, reads, _, _ = schedules[label]
                m.write_errors, m.read_results = writes[:], reads[:]
            m.run('cs40l26_vibe_stop_worker', CTX + 0xe0)  # void worker
            done = [r for r in m.logs if '%s: done' in r['format']]
            assert bool(done) == (label != 'PM-error'), (label, m.logs)
            assert not m.write_errors and not m.read_results
            assert len(m.pm_exits) == int(label != 'PM-error')
            assert bool(m.recovery) == (label == 'PM-error')
            if label != 'PM-error':
                assert any('Failed to stop playback' in r['format'] for r in m.logs), m.logs
            cases.append(dict(sample=sample, case=label, entry='cs40l26_vibe_stop_worker',
                              status='PASS', done_logged=bool(done), writes=m.writes,
                              reads=m.reads, logs=m.logs, pm_exits=m.pm_exits,
                              recovery_arguments=m.recovery))
        for pm_result in (0, 1, -5, -110):
            m = Mailbox(path)
            m.pm_result = pm_result
            rc = m.run('cs40l26_pm_enter', DEVICE)
            assert rc == min(pm_result, 0)
            assert m.recovery == ([pm_result & 0xffffffff] if pm_result < 0 else [])
            cases.append(dict(sample=sample, case=f'pm-return-{pm_result}',
                              entry='cs40l26_pm_enter', status='PASS', result=rc,
                              recovery_arguments=m.recovery))
    dependencies = [Path(__file__).resolve(), ROOT / 'tests/haptics_driver_emulation.py',
                    ROOT / 'scripts/firmware_facts.py', ROOT / 'tests/haptics-emulator-dependencies.json']
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                  (p.suffix in ('.py', '.so') or '.so.' in p.name))
    report = dict(status='PASS', scope=__doc__, cases=cases, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in dependencies},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in deps})
    (ROOT / 'logs/haptics-mailbox-error-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(cases)} original mailbox/PM/stop cases; no hardware recovery claim')


if __name__ == '__main__':
    main()
