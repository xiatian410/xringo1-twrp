#!/usr/bin/env python3
"""Execute original OS4 display notifications with pending work at flush.

The original notifier pauses at __flush_workqueue; a bounded sequential host
driver executes previously queued original workers on a separate stack, then
restores the notifier CPU context. This models completion of queued work, not
Linux scheduling, simultaneous notifications, elapsed time or real interrupts.
The existing typed bridge executes original Synaptics display/IC-mode code;
controller responses, input, power and kernel services remain explicit fixtures.
Synthetic coordinates and successful flush do not prove physical touch recovery.
"""
import json
from pathlib import Path
from touch_ic_mode_emulation import IC, Notify, Capture, CTX, CORE, ROOT, DEPS, MASK, sha
from touch_notifier_emulation import DEVICE
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC


class Pending(Notify):
    def __init__(self, *args):
        super().__init__(*args)
        self.flush_pause = False
        self.timeline = []
        self.flushed_workers = []

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        if name != '__flush_workqueue':
            return super().on_code(uc, address, size, data)
        self.flushes.append(self.arg(0))
        self.timeline.append(dict(boundary='flush', pending=self.pending[:], suspended=self.suspended()))
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, 0)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
        self.flush_pause = True
        uc.emu_stop()

    def run(self, name, *args):
        if name != 'xiaomi_drm_panel_notifier_callback':
            return super().run(name, *args)
        assert not self.flush_pause
        for i, value in enumerate(args):
            self.uc.reg_write(UC_ARM64_REG_X0+i, value & MASK)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        start = self.symbols[name]
        for _ in range(2):  # at most one flush in the original notification
            self.uc.emu_start(start, self.return_address, timeout=2000000, count=100000)
            if not self.flush_pause:
                assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, 'notifier budget'
                return  # original void callback: do not interpret residual x0
            self.flush_pause = False
            saved = self.uc.context_save()
            assert len(self.pending) <= 1, 'fixture only permits one pending work item'
            while self.pending:
                work = self.pending.pop(0)
                names = {self.bss+0x10+0x28e8: 'xiaomi_touch_suspend_work',
                         self.bss+0x10+0x2908: 'xiaomi_touch_resume_work'}
                worker = names[work]
                self.uc.reg_write(UC_ARM64_REG_X0, work)
                self.uc.reg_write(UC_ARM64_REG_SP, 0x500fff0)
                self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
                self.uc.emu_start(self.symbols[worker], self.return_address, timeout=2000000, count=100000)
                assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, 'worker budget'
                assert not self.flush_pause and not self.pending
                record = dict(boundary='worker', worker=worker, suspended=self.suspended(),
                              bridge=[a[:] for a in self.bridge], config_length=self.synaptics.u32(CORE+0x18c))
                self.timeline.append(record)
                self.flushed_workers.append(worker)
            self.uc.context_restore(saved)
            start = self.uc.reg_read(UC_ARM64_REG_PC)
        raise AssertionError('flush segment budget')


def exercise(wrapper, syna, props, children):
    capture = Capture(syna, props, children)
    capture.run('syna_xiaomi_touch_probe', CTX)
    cases = []
    for label in ['off-on', 'off-on-off-on', 'duplicate-off', 'duplicate-on',
                  'failed-resume-duplicate-on', 'failed-resume-new-cycle',
                  'pending-off-reject-on', 'pending-on-reject-off']:
        s = IC(syna)
        m = Pending(wrapper, capture.panel_bytes, s)
        assert m.panel() == 0
        if label in ['duplicate-on', 'pending-on-reject-off']:
            m.notify(1); m.drain()
        m.timeline.clear()
        events = {'off-on': [1, 2], 'off-on-off-on': [1, 2, 1, 2],
                  'duplicate-off': [1, 1], 'duplicate-on': [2, 2],
                  'failed-resume-duplicate-on': [1, 2, 2],
                  'failed-resume-new-cycle': [1, 2, 3, 2],
                  'pending-off-reject-on': [1, 2], 'pending-on-reject-off': [2, 1]}[label]
        for i, event in enumerate(events):
            if label.startswith('failed-resume'):
                s.config_command_error = 0 if label.endswith('new-cycle') and i == 3 else -110
            if 'reject' in label and i == 1:
                m.queue_result = 0
            m.notify(event)  # intentionally do not drain before the next event
        before_drain = dict(pending=m.pending[:], bridge=[a[:] for a in m.bridge],
                            suspended=m.suspended(), config_length=s.u32(CORE+0x18c))
        m.drain()
        expected = {'off-on': [[0, 0], [1, 0]],
                    'off-on-off-on': [[0, 0], [1, 0], [0, 0], [1, 0]],
                    'duplicate-off': [[0, 0]], 'duplicate-on': [[0, 0], [1, 0]],
                    'failed-resume-duplicate-on': [[0, 0], [1, -110]],
                    'failed-resume-new-cycle': [[0, 0], [1, -110], [0, 0], [1, 0]],
                    'pending-off-reject-on': [[0, 0]],
                    'pending-on-reject-off': [[0, 0], [1, 0]]}[label]
        assert m.bridge == expected, (label, m.bridge)
        assert len(m.flushed_workers) == len(events)-1
        assert len(m.flushes) == len(events)+int(label in ['duplicate-on', 'pending-on-reject-off'])
        assert all(len(r['pending']) == (0 if i == 0 else 1)
                   for i, r in enumerate(x for x in m.timeline if x['boundary'] == 'flush'))
        off = label in ['duplicate-off', 'pending-off-reject-on']
        assert m.suspended() == int(off) and s.u32(CTX+0x450) == int(not off)
        delivered = s.emit()
        expected_touch = label not in ['duplicate-off', 'pending-off-reject-on', 'failed-resume-duplicate-on']
        assert delivered == expected_touch, (label, delivered)
        assert s.u32(CORE+0x18c) == (13 if expected_touch else 0)
        assert not m.pending and not m.flush_pause
        if 'reject' in label:
            assert m.work_requests[-1]['accepted'] == 0 and not before_drain['pending']
        if label == 'failed-resume-duplicate-on':
            assert before_drain['config_length'] == 0 and len(before_drain['bridge']) == 2
        print('PASS', label, m.bridge, 'cfg', s.u32(CORE+0x18c), flush=True)
        cases.append(dict(case=label, status='PASS', events=events, bridge=m.bridge,
                          timeline=m.timeline, flushed_workers=m.flushed_workers,
                          before_drain=before_drain, wrapper_suspended=m.suspended(),
                          active=s.u32(CTX+0x450), config_length=s.u32(CORE+0x18c),
                          coordinates=s.events, delivered=delivered,
                          work_requests=m.work_requests, ic_commands=s.ic_commands))
    return cases


def main():
    # Reuse the already hash-bound dependencies without changing older suites.
    evidence = ROOT/'logs/touch-ic-mode-emulation.json'
    previous = json.loads(evidence.read_text())
    sources = dict(previous['sources'])
    sources[str(evidence.relative_to(ROOT))] = sha(evidence)
    for name, expected in sources.items():
        path = Path(name) if Path(name).is_absolute() else ROOT/name
        assert sha(path) == expected
    dt = json.loads((ROOT/'logs/touch-devicetree-audit.json').read_text())
    cases = []
    for record in dt['cases']:
        sample = record['sample']
        base = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules'
        props = {k: bytes.fromhex(v) if isinstance(v, str) else v for k, v in record['canonical_touch_properties'].items()}
        children = {n: {k: bytes.fromhex(v) for k, v in p.items()} for n, p in record['touch_child_properties'].items()}
        cases.extend(dict(sample=sample, **c) for c in exercise(base/'xiaomi_touch_dijun.ko', base/'synaptics_tcm2.ko', props, children))
    tests = dict(previous['tests'])
    tests[str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__))
    tests['tests/touch_ic_mode_emulation.py'] = sha(ROOT/'tests/touch_ic_mode_emulation.py')
    for field, records in [('tests', tests), ('emulator_files', previous['emulator_files'])]:
        for name, expected in records.items():
            path = Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(path) == expected, (field, name)
    for record in previous['drivers'].values():
        assert sha(ROOT/record['path']) == record['sha256']
    (ROOT/'logs/touch-pending-flush-emulation.json').write_text(json.dumps(dict(
        status='PASS', scope=__doc__.strip(), cases=cases, sources=sources,
        tests=tests, drivers=previous['drivers'], emulator_files=previous['emulator_files']), indent=2)+'\n')
    print('PASS', len(cases), 'cases', flush=True)


if __name__ == '__main__':
    main()
