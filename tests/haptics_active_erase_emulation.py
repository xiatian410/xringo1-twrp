#!/usr/bin/env python3
"""Join production FF bytes to stock OS4 probe/play/IRQ/active erase waits.

Original stock probe, firmware metadata/parser, FF callbacks/workers and the
registered mailbox handler execute. Kernel input, ordered queues, PM, mailbox,
regmap and DSP sequences remain explicit fixtures. Completion counters use a
bounded single-waiter model: complete adds one, complete_all saturates, waits
consume a token or time out. HZ=1000 is a fixture, not device timing evidence.
At a wait boundary CPU context is saved, a synthetic IRQ message is consumed
by the original handler on another stack, then the worker resumes. No concurrent
Linux scheduling, real IRQ delivery, DSP instructions or motor are executed.
"""
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from haptics_irq_completion_emulation import IRQ, ROOT, CTX, sha, inventory, table, bin_writes
from haptics_driver_emulation import capture, SOURCE, MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30, UC_ARM64_REG_SP

INPUT, EFFECT, EFFECTS = 0x40a8000, 0x40b0000, 0x40aa000
WORKERS = {CTX+0x120: 'cs40l26_upload_worker', CTX+0xc0: 'cs40l26_vibe_start_worker', CTX+0x140: 'cs40l26_erase_worker'}


class Active(IRQ):
    def __init__(self, *args):
        self.runtime = False
        self.wait_pause = None
        self.wait_records = []
        self.timeouts = []
        self.irq_at_wait = []
        self.runtime_workers = []
        self.irq_results = []
        self.freed_effects = []
        super().__init__(*args)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        if not self.runtime:
            return super().on_code(uc, address, size, data)
        if name == '__msecs_to_jiffies':
            self.timeouts.append(self.arg(0))
            result = self.arg(0)
        elif name == 'wait_for_completion_timeout':
            assert not self.locked and self.arg(0) == CTX+0x228
            assert self.timeouts and self.arg(1) == self.timeouts[-1]
            self.wait_pause = [self.arg(0), self.arg(1)]
            self.calls.append(name)
            uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
            uc.emu_stop()
            return
        elif name in ['complete', 'complete_all']:
            pointer = self.arg(0)
            assert pointer in [CTX+0x208, CTX+0x228]
            old = self.u32(pointer)
            self.put32(pointer, 0xffffffff if name == 'complete_all' or old == 0xffffffff else old+1)
            return super().on_code(uc, address, size, data)
        elif name == 'devm_kfree':
            self.freed_effects.append(self.arg(1))
            return super().on_code(uc, address, size, data)
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def execute(self, name, args=(), depth=0):
        assert depth < 4 and self.pending_flush is None and self.wait_pause is None
        for i, value in enumerate(args):
            self.uc.reg_write(UC_ARM64_REG_X0+i, value & MASK)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x501fff0-depth*0x4000)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        start = self.symbols[name]
        for _ in range(4):
            self.uc.emu_start(start, self.return_address, timeout=2000000, count=100000)
            if self.pending_flush is None and self.wait_pause is None:
                assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, ('budget', name)
                r = self.arg(0) & 0xffffffff
                return r if r < 0x80000000 else r-0x100000000
            saved = self.uc.context_save()
            if self.pending_flush is not None:
                target = self.pending_flush
                self.pending_flush = None
                self.flush_until(target, depth+1)
                self.uc.context_restore(saved)
            else:
                pointer, timeout = self.wait_pause
                self.wait_pause = None
                before = dict(counter=self.u32(pointer), state=self.u32(CTX+0x1d0), count=self.u32(CTX+0x200))
                if self.irq_at_wait:
                    assert not self.locked
                    self.supply(self.irq_at_wait)
                    self.irq_at_wait = []
                    self.irq_results.append(self.execute('cs40l26_handle_mbox_buffer', (123, CTX), depth+1))
                token = self.u32(pointer)
                if token and token != 0xffffffff:
                    self.put32(pointer, token-1)
                result = 1 if token else 0  # positive remaining jiffies is synthetic
                self.wait_records.append(dict(pointer=pointer, timeout=timeout, before=before,
                    after=dict(counter=self.u32(pointer), state=self.u32(CTX+0x1d0), count=self.u32(CTX+0x200)), result=result))
                self.uc.context_restore(saved)
                self.uc.reg_write(UC_ARM64_REG_X0, result)
            start = self.uc.reg_read(UC_ARM64_REG_PC)
        raise AssertionError(('segment budget', name))

    def flush_until(self, target, depth=0):
        assert target in self.queue
        for _ in range(3):
            work = self.queue.pop(0)
            worker = WORKERS[work]
            previous = self.current_worker
            self.current_worker = worker
            self.runtime_workers.append(worker)
            self.execute(worker, (work,), depth)
            self.current_worker = previous
            if work == target:
                return
        raise AssertionError('ordered queue budget')

    def runtime_call(self, name, *args):
        return self.execute(name, args)


def exercise(path, blobs, props, effect):
    expected = inventory(blobs['cs40l26.wmfw'])['writes'][:]
    rows = table(blobs['cs40l26.wmfw'])[1]
    for name in ['cs40l26.bin', 'cs40l26-svc.bin', 'cs40l26-dvl.bin', 'cs40l26-a2h.bin', 'cs40l26-dbc.bin']:
        expected += bin_writes(blobs[name], rows)
    cases = []
    for label in ['no-start-IRQ', 'done-before-erase', 'done-during-wait', 'missing-done',
                  'stop-completion-only', 'unknown-message', 'IRQ-bulk-read-error', 'IRQ-ACK-error',
                  'zero-duration-timeout', 'start-command-error', 'two-completions',
                  'software-state-done', 'software-state-timeout',
                  'late-done-retry-erase', 'completed-then-missing']:
        m = Active(path, blobs, props)
        assert m.run('cs40l26_probe', CTX) == 0 and m.raw == expected
        assert not m.queue and not m.locked and len(m.raw) == 68
        registered = [s for s in m.irq_services if s['name'] == 'devm_request_threaded_irq' and s['args'][3] == m.symbols['cs40l26_handle_mbox_buffer']]
        assert len(registered) == 1 and registered[0]['args'][1] == 123
        m.runtime = True
        m.completed.clear(); m.notifications.clear(); m.selftest_mail.clear(); m.selftest_writes.clear()
        m.put32(CTX+0x200, 0); m.put32(CTX+0x1d0, 0)
        # x20 in the start worker is CTX+0xc0; its +0x114 flag is
        # CTX+0x1d4 (not CTX+0x234). Explicitly select IRQ-driven state.
        probe_start_gate = bytes(m.uc.mem_read(CTX+0x1d4, 1)).hex()
        assert probe_start_gate == '01'
        m.uc.mem_write(CTX+0x1d4, bytes([int(not label.startswith('software-state-'))]))
        payload = bytearray(effect)
        if label == 'zero-duration-timeout':
            struct.pack_into('<H', payload, 10, 0)
        m.uc.mem_write(EFFECT, bytes(payload)); m.uc.mem_write(EFFECTS+7*48, bytes(payload))
        assert m.runtime_call('cs40l26_upload_effect', INPUT, EFFECT, 0) == 0
        assert m.runtime_workers == ['cs40l26_upload_worker'] and m.u64(CTX+0x58) != CTX+0x58
        if label == 'start-command-error':
            m.start_mail_error = -5
        assert m.runtime_call('cs40l26_playback_effect', INPUT, 7, 1) == 0
        m.flush_until(CTX+0xc0)
        assert not m.queue and not m.locked
        before_irq = dict(count=m.u32(CTX+0x200), state=m.u32(CTX+0x1d0))
        assert before_irq == dict(count=int(label.startswith('software-state-')), state=int(label.startswith('software-state-')))
        assert m.u32(CTX+0x228) == 0
        if label not in ['no-start-IRQ', 'start-command-error'] and not label.startswith('software-state-'):
            m.supply([0x01000010])
            assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
        if label == 'done-before-erase':
            m.supply([0x01000000])
            assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
        m.irq_at_wait = {'done-during-wait': [0x01000000], 'stop-completion-only': [0x01000012],
                         'unknown-message': [0x12345678], 'IRQ-bulk-read-error': [0x01000000],
                         'IRQ-ACK-error': [0x01000000], 'two-completions': [0x01000000, 0x01000000],
                         'software-state-done': [0x01000000], 'completed-then-missing': [0x01000000]}.get(label, [])
        if label == 'IRQ-bulk-read-error': m.ring_read_error = -5
        if label == 'IRQ-ACK-error': m.ack_error = -5
        rc = m.runtime_call('cs40l26_erase_effect', INPUT, 7)
        print(label, rc, 'before IRQ', before_irq, 'wait', m.wait_records, 'freed', m.freed_effects, flush=True)
        success = label in ['no-start-IRQ', 'done-before-erase', 'done-during-wait', 'start-command-error', 'two-completions', 'software-state-done', 'completed-then-missing']
        waited = label not in ['no-start-IRQ', 'done-before-erase', 'start-command-error']
        completed = label in ['done-before-erase', 'done-during-wait', 'two-completions', 'software-state-done', 'completed-then-missing']
        assert rc == (0 if success else -62) and not m.locked and not m.queue and not m.irq_at_wait
        assert m.runtime_workers == ['cs40l26_upload_worker', 'cs40l26_vibe_start_worker', 'cs40l26_erase_worker']
        assert len(m.wait_records) == int(waited)
        assert m.timeouts == ([10000 if label == 'zero-duration-timeout' else 580] if waited else [])
        if waited:
            record, = m.wait_records
            assert record['before'] == dict(counter=0, state=1, count=1)
            assert record['result'] == int(success)
        assert m.u32(CTX+0x200) == m.u32(CTX+0x1d0) == int(not success)
        assert m.u32(CTX+0x228) == (0xffffffff if completed else 0)
        assert m.u32(CTX+0x208) == int(label == 'stop-completion-only')
        assert (m.u64(CTX+0x58) == CTX+0x58) == success and len(m.freed_effects) == int(success)
        assert m.irq_results == ([1] if label in ['done-during-wait', 'stop-completion-only', 'unknown-message', 'IRQ-bulk-read-error', 'IRQ-ACK-error', 'two-completions', 'software-state-done', 'completed-then-missing'] else [])
        assert m.selftest_mail == [dict(command=0x1800081, result=-5 if label == 'start-command-error' else 0)]
        assert m.selftest_writes == [dict(worker='cs40l26_upload_worker', address=a, value=v, result=0)
            for a, v in [(0x280701c, 0 if label == 'zero-duration-timeout' else 20), (0x2807014, 125), (0x2807018, 64)]] + [
            dict(worker='cs40l26_vibe_start_worker', address=0x2802134, value=0 if label == 'zero-duration-timeout' else 80, result=0),
            dict(worker='cs40l26_vibe_start_worker', address=0x28059f0, value=0, result=0)]
        retry = None
        if label == 'late-done-retry-erase':
            assert rc == -62
            m.supply([0x01000000])
            assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
            second = m.runtime_call('cs40l26_erase_effect', INPUT, 7)
            assert second == 0 and len(m.wait_records) == 1 and len(m.freed_effects) == 1
            assert m.u64(CTX+0x58) == CTX+0x58 and m.u32(CTX+0x1d0) == 0
            retry = dict(result=second, waits=len(m.wait_records), freed=len(m.freed_effects), counter=m.u32(CTX+0x228))
        elif label == 'completed-then-missing':
            assert m.u32(CTX+0x228) == 0xffffffff
            assert m.runtime_call('cs40l26_upload_effect', INPUT, EFFECT, 0) == 0
            assert m.runtime_call('cs40l26_playback_effect', INPUT, 7, 1) == 0
            m.flush_until(CTX+0xc0)
            # Original successful start clears completion, preventing an old
            # complete_all from satisfying the next effect's erase wait.
            assert m.u32(CTX+0x228) == 0
            m.supply([0x01000010])
            assert m.runtime_call('cs40l26_handle_mbox_buffer', 123, CTX) == 1
            second = m.runtime_call('cs40l26_erase_effect', INPUT, 7)
            assert second == -62 and len(m.wait_records) == 2 and len(m.freed_effects) == 1
            assert m.u64(CTX+0x58) != CTX+0x58 and m.u32(CTX+0x1d0) == 1
            retry = dict(result=second, waits=len(m.wait_records), freed=len(m.freed_effects), counter=m.u32(CTX+0x228))
        cases.append(dict(case=label, status='PASS', erase_result=rc, before_start_IRQ=before_irq,
            retry=retry,
            waits=m.wait_records, probe_start_gate=probe_start_gate, timeout_requests=m.timeouts, runtime_workers=m.runtime_workers,
            completions=m.completed, irq_results=m.irq_results, ack_writes=m.acks,
            state=m.u32(CTX+0x1d0), event_count=m.u32(CTX+0x200), effect_list_empty=m.u64(CTX+0x58)==CTX+0x58,
            freed_effects=m.freed_effects, completion_counter=m.u32(CTX+0x228), stop_counter=m.u32(CTX+0x208),
            writes=m.selftest_writes, mailbox=m.selftest_mail, messages=m.messages))
    return cases


def main():
    prior_path = ROOT/'logs/haptics-irq-completion-emulation.json'
    prior = json.loads(prior_path.read_text())
    sources = dict(prior['sources']); sources[str(prior_path.relative_to(ROOT))] = sha(prior_path)
    tests = dict(prior['tests'])
    for name in ['haptics_irq_completion_emulation.py', 'haptics_driver_capture.cpp']:
        tests['tests/'+name] = sha(ROOT/'tests'/name)
    tests[str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__))
    for path in [SOURCE, SOURCE.with_suffix('.h')]: sources[str(path)] = sha(path)
    for name, snippets in [('completion.c', ['x->done = UINT_MAX;', 'if (x->done != UINT_MAX)', 'x->done--;']),
                           ('completion.h', ['reinit_completion', 'x->done = 0;'])]:
        path = ROOT/'logs'/('upstream-linux-v6.18-'+name)
        text = path.read_text()
        assert all(s in text for s in snippets)
        sources[str(path.relative_to(ROOT))] = sha(path)
    for mapping in [sources, tests, prior['emulator_files']]:
        for name, expected in mapping.items():
            path = Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(path) == expected
    dt = json.loads((ROOT/'logs/haptics-devicetree-audit.json').read_text())
    cases = []
    with tempfile.TemporaryDirectory(prefix='dijun-active-erase-') as temp:
        fixtures = capture(Path(temp))
        effect = next(e for n, e, event in fixtures if n == 80)
        assert int.from_bytes(effect[2:4], 'little') == 7
        for sample, record in prior['drivers'].items():
            path = ROOT/record['path']; assert sha(path) == record['sha256']
            node = next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']
            blobs = {p.name: p.read_bytes() for p in (ROOT/'firmware/samples'/sample/'analysis/odm/firmware').glob('cs40l26*')}
            disasm = ROOT/'logs'/f'{sample}-haptics-active-erase-core.disasm'
            tool = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
            disasm.write_bytes(subprocess.check_output([tool, '-dr', '--disassemble-symbols=cs40l26_upload_effect,cs40l26_playback_effect,cs40l26_vibe_start_worker,cs40l26_erase_effect,cs40l26_erase_worker,cs40l26_handle_mbox_buffer', str(path)]))
            sources[str(disasm.relative_to(ROOT))] = sha(disasm)
            cases.extend(dict(sample=sample, **c) for c in exercise(path, blobs, node['properties'], effect))
    (ROOT/'logs/haptics-active-erase-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, production_effect=effect.hex(), drivers=prior['drivers'], sources=sources,
        tests=tests, emulator_files=prior['emulator_files']), indent=2)+'\n')
    print('PASS', len(cases), 'cases', flush=True)


if __name__ == '__main__': main()
