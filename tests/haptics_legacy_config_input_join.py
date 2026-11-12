#!/usr/bin/env python3
"""Execute original OS2/OS3 probe/configuration, IRQ/input setup and self-test.

Stock DT and firmware bytes feed original ARM64 code in one context. Synthetic
B2 identity, PM/HALO/logger/count registers, all-FF immediate-end sequences,
mailbox ACK, power, allocation, input/IRQ/PM services and ordered work execution
are explicit boundaries. Writes never update the supplied hardware reads.
Original remove executes; its kernel teardown operations are service fixtures.
No running DSP, concurrent kernel, real interrupt, timing or motor is simulated.
"""
import inspect
import json
from pathlib import Path
import struct
import subprocess

from haptics_legacy_probe_upload_join import Joined, SAMPLES, ROOT, CTX, REG
from haptics_firmware_emulation import inventory
from haptics_coefficients_emulation import table, bin_writes
from haptics_driver_emulation import (DEPS, MASK, sha, UC_ARM64_REG_X0,
    UC_ARM64_REG_PC, UC_ARM64_REG_X30, UC_ARM64_REG_SP)

INPUT, FF, EFFECTS = 0x40a8000, 0x40a9000, 0x40aa000
WATCH = ['cs40l26_wseq_populate', 'cs40l26_wseq_write', 'cs40l26_irq_update_mask',
         'cs40l26_gpio_config', 'cs40l26_bst_ctl_config', 'cs40l26_clip_lvl_config',
         'cs40l26_dbc_enable', 'cs40l26_calib_dt_config', 'cs40l26_brwnout_prevention_init',
         'cs40l26_dc_wd_config', 'cs40l26_pm_runtime_setup', 'cs40l26_pm_enter',
         'cs40l26_pm_exit', 'cs40l26_logger_setup', 'cs40l26_logger_src_add',
         'cs40l26_asp_config', 'cs40l26_request_irq', 'cs40l26_upload_effect',
         'cs40l26_playback_effect', 'cs40l26_erase_effect', 'cs40l26_upload_worker',
         'cs40l26_vibe_start_worker', 'cs40l26_erase_worker']
LABELS = ['CALL-RAM-exhausted', 'active-sequence-read-error', 'HALO-invalid',
          'runtime-resume-error', 'IRQ-chip-error', 'IRQ-last-thread-error',
          'input-FF-error', 'input-register-error', 'MFD-error',
          'selftest-ACK-fixture', 'selftest-mailbox-error']


class ConfigInput(Joined):
    def __init__(self, path, properties, blobs, label):
        super().__init__(path, properties, blobs, label)
        self.hardware.update({0x2800370: 3, 0x2800378: 2, 0x2800fa8: 2,
                              0x10110: 0xffffffff, 0x381c: 0xffffffff, 0x3804: 0,
                              0x7068: 0, 0x201c: 0, 0x6408: 0, 0x6404: 0,
                              0x10114: 0xffffffff, 0x2805a34: 0, 0x2805a44: 0,
                              0x2802140: 43, 0x2805368: 0})
        if label == 'HALO-invalid':
            self.hardware[0x2800fa8] = 0
        self.rawreads, self.bulk, self.pm, self.multi, self.debugfs = [], [], [], [], []
        self.irq_services, self.input_services, self.capabilities = [], [], []
        self.virqs = self.threads = 0
        self.queue, self.workers, self.work_results, self.effects = [], [], [], []
        self.pending_flush = None
        self.current_worker = None
        self.workqueue_spec, self.worker_writes, self.worker_mailbox = [], [], []
        self.locked = set()
        self.watch += [name for name in WATCH if name not in self.watch]
        self.intercept('cs40l26_debugfs_init')

    def finish(self, uc, name, result):
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def on_code(self, uc, address, size, data):
        if address == self.symbols['cs40l26_upload_effect']:
            self.effects.append(bytes(uc.mem_read(self.arg(1), 48)).hex())
        name = self.hooks.get(address)
        if name is None:
            return super().on_code(uc, address, size, data)
        a = [self.arg(i) for i in range(7)]
        if name == 'alloc_workqueue':
            assert a[1:3] == [0xa0012, 1]
            self.workqueue_spec.append(dict(name=self.string(a[0]), flags=a[1], max_active=a[2]))
            result = 0x4080000
        elif name == 'regmap_update_bits_base':
            assert a[0] == REG
            assert a[1] in [0x2c04, 0x7404, 0x2900, 0x28059ec], hex(a[1])
            self.updates.append(dict(address=a[1], mask=a[2], value=a[3], result=0))
            result = 0
        elif name == 'regmap_write' and (self.current_worker or
                self.label == 'CALL-RAM-exhausted' and a[1] == 0x2800ff8):
            assert a[0] == REG
            result = -5 if not self.current_worker else 0
            record = dict(address=a[1], value=a[2], result=result)
            self.writes.append(record)
            if self.current_worker:
                self.worker_writes.append(dict(worker=self.current_worker, **record))
        elif name == 'cs40l26_debugfs_init':
            self.debugfs.append(a[0])
            result = 0
        elif name == 'regmap_raw_read':
            assert a[0] == REG and a[3] in [132, 516]
            result = -5 if self.label == 'active-sequence-read-error' else 0
            self.rawreads.append(dict(address=a[1], length=a[3], result=result,
                                     fixture='all-FF-immediate-terminator'))
            if not result:
                uc.mem_write(a[2], b'\xff' * a[3])
        elif name == 'regmap_bulk_write':
            assert a[0] == REG and 0 < a[3] <= 32
            raw = bytes(uc.mem_read(a[2], a[3] * 4))
            self.bulk.append(dict(address=a[1], words=a[3], bytes=raw.hex(), result=0))
            result = 0
        elif name in ['__pm_runtime_use_autosuspend', 'pm_runtime_set_autosuspend_delay',
                      'pm_runtime_enable', 'mod_timer', 'ktime_get_with_offset',
                      'ktime_get_mono_fast_ns', '__pm_runtime_resume',
                      '__pm_runtime_suspend', '__pm_runtime_set_status']:
            result = -5 if name == '__pm_runtime_resume' and self.label == 'runtime-resume-error' else 0
            self.pm.append(dict(name=name, args=a[:4], result=result))
        elif name == 'regmap_multi_reg_write':
            assert a[0] == REG and a[2] == 2
            raw = bytes(uc.mem_read(a[1], 24))
            values = [list(struct.unpack_from('<III', raw, offset)) for offset in [0, 12]]
            assert values == [[0x4c40, 8, 0], [0x4c50, 9, 0]]
            self.multi.append(dict(values=values, result=0))
            result = 0
        elif name == 'devm_regmap_add_irq_chip':
            assert a[:5] == [0x4060000, REG, 0, 0x2088, 0xffffffff]
            assert a[6] == CTX + 0x1c60
            result = -5 if self.label == 'IRQ-chip-error' else 0
            if not result:
                self.put64(a[6], 0x4090000)
        elif name == 'regmap_irq_get_virq':
            assert a[0] == 0x4090000
            self.virqs += 1
            result = 100 + self.virqs
        elif name == 'devm_request_threaded_irq':
            self.threads += 1
            assert a[:3] == [0x4060000, 100 + self.threads, 0]
            assert a[4] == 0x2088 and a[6] == CTX
            result = -5 if self.label == 'IRQ-last-thread-error' and self.threads == 27 else 0
        elif name == 'devm_input_allocate_device':
            assert a[0] == 0x4060000
            result = INPUT
        elif name == 'input_set_capability':
            assert a[0] == INPUT
            self.capabilities.append(a[1:3])
            result = 0
        elif name == 'input_ff_create':
            assert a[:2] == [INPUT, 96]
            result = -12 if self.label == 'input-FF-error' else 0
            if not result:
                self.put64(INPUT + 0xf8, FF)
                self.put64(INPUT + 0xc0, 1 << 16)
                self.put64(FF + 0x80, EFFECTS)
        elif name in ['input_register_device', 'sysfs_create_groups',
                      'sysfs_remove_groups', 'input_unregister_device']:
            assert a[0] == (INPUT + 0x240 if name.startswith('sysfs_') else INPUT)
            result = -5 if name == 'input_register_device' and self.label == 'input-register-error' else 0
        elif name == 'devm_mfd_add_devices':
            assert a[0] == 0x4060000 and a[3] == 1
            result = -5 if self.label == 'MFD-error' else 0
        elif name in ['mutex_lock', 'mutex_unlock']:
            if name == 'mutex_lock':
                assert a[0] not in self.locked
                self.locked.add(a[0])
            else:
                assert a[0] in self.locked
                self.locked.remove(a[0])
            result = 0
        elif name == 'queue_work_on':
            assert a[1] == 0x4080000 and a[2] in [CTX + 0x158, CTX + 0xc8, CTX + 0x188]
            assert a[2] not in self.queue
            self.queue.append(a[2])
            result = 1
        elif name == 'flush_work':
            assert a[0] in self.queue
            self.pending_flush = a[0]
            result = 1
        elif name == 'cs40l26_mailbox_write' and self.current_worker:
            assert self.current_worker == 'cs40l26_vibe_start_worker'
            result = -5 if self.label == 'selftest-mailbox-error' else 0
            self.mailbox.append(dict(command=a[1], result=result))
            self.worker_mailbox.append(dict(command=a[1], result=result))
        elif name == '_dev_alert':
            self.messages.append(self.string(a[1]))
            result = 0
        elif name == 'sysfs_notify':
            result = 0
        elif name == 'devm_kfree':
            assert a[0] == 0x4060000
            assert a[1] in [record['address'] for record in self.allocations]
            self.frees.append(a[1])
            result = 0
        else:
            return super().on_code(uc, address, size, data)
        if name in ['devm_regmap_add_irq_chip', 'regmap_irq_get_virq', 'devm_request_threaded_irq']:
            self.irq_services.append(dict(name=name, args=a, result=result))
        if name in ['devm_input_allocate_device', 'input_ff_create', 'input_register_device',
                    'sysfs_create_groups', 'sysfs_remove_groups', 'input_unregister_device',
                    'devm_mfd_add_devices']:
            self.input_services.append(dict(name=name, args=a[:4], result=result))
        self.finish(uc, name, result)
        if name == 'flush_work':
            uc.emu_stop()

    def run_probe(self):
        self.prepare()
        self.uc.reg_write(UC_ARM64_REG_X0, CTX)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        start = self.symbols['cs40l26_probe']
        for _ in range(4):
            self.uc.emu_start(start, self.return_address, timeout=10000000, count=1000000)
            if self.pending_flush is None:
                assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, 'legacy config/probe budget'
                value = self.arg(0) & 0xffffffff
                return value if value < 0x80000000 else value - 0x100000000
            target = self.pending_flush
            self.pending_flush = None
            saved = self.uc.context_save()
            while self.queue:
                work = self.queue.pop(0)
                worker = {CTX + 0x158: 'cs40l26_upload_worker',
                          CTX + 0xc8: 'cs40l26_vibe_start_worker',
                          CTX + 0x188: 'cs40l26_erase_worker'}[work]
                self.workers.append(worker)
                self.current_worker = worker
                self.uc.reg_write(UC_ARM64_REG_X0, work)
                self.uc.reg_write(UC_ARM64_REG_SP, 0x500fff0)
                self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
                self.uc.emu_start(self.symbols[worker], self.return_address,
                                  timeout=2000000, count=100000)
                assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, worker
                assert self.pending_flush is None
                self.work_results.append(dict(worker=worker, upload_status=self.u32(CTX + 0x250),
                                              erase_status=self.u32(CTX + 0x254)))
                self.current_worker = None
                if work == target:
                    break
            else:
                raise AssertionError('missing flush target')
            self.uc.context_restore(saved)
            start = self.uc.reg_read(UC_ARM64_REG_PC)
        raise AssertionError('legacy flush budget')


def exercise(sample, dt):
    base = ROOT / 'firmware/samples' / sample / 'analysis'
    driver = base / 'vendor_dlkm/lib/modules/xring_smartpa.ko'
    paths = sorted((base / 'odm/firmware').glob('cs40l26*'))
    blobs = {path.name: path.read_bytes() for path in paths}
    properties = next(c for c in dt['cases'] if c['sample'] == sample and c['case'] == 'overlay-5')[
        'haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
    expected = inventory(blobs['cs40l26.wmfw'])['writes'][:]
    for name in ['cs40l26.bin', 'cs40l26-svc.bin', 'cs40l26-dvl.bin', 'cs40l26-a2h.bin', 'cs40l26-dbc.bin']:
        expected += bin_writes(blobs[name], table(blobs['cs40l26.wmfw'])[1])
    cases = []
    for label in LABELS:
        m = ConfigInput(driver, properties, blobs, label)
        result = m.run_probe()
        print(sample, label, result, 'loaded', bytes(m.uc.mem_read(CTX + 0x222, 1)).hex(),
              'IRQ', m.threads, 'workers', m.workers, flush=True)
        assert m.raw == expected and len(m.raw) == 68
        assert m.releases == [m.fwmap[name] for name in m.firmware_requests]
        success = label.startswith('selftest-')
        assert result == (0 if success else -62 if label == 'CALL-RAM-exhausted' else
                          -22 if label == 'HALO-invalid' else -12 if label == 'input-FF-error' else -5)
        assert m.entries.count('cs40l26_remove') == int(not success)
        assert m.symbols['cs40l26_remove'] not in m.hooks
        loaded = bytes(m.uc.mem_read(CTX + 0x222, 1))[0]
        assert loaded == int(label != 'CALL-RAM-exhausted')
        assert not m.locked and not m.queue
        assert m.workqueue_spec == [dict(name='vibe_workqueue', flags=0xa0012, max_active=1)]
        assert not any('wait_for_completion' in name or name.startswith('complete') for name in m.calls)
        expected_bulk = (0 if label in ['CALL-RAM-exhausted', 'active-sequence-read-error'] else
                         2 if label == 'HALO-invalid' else 23 if label == 'runtime-resume-error' else 25)
        assert len(m.bulk) == expected_bulk
        if label == 'CALL-RAM-exhausted':
            assert len([w for w in m.writes if w['address'] == 0x2800ff8]) == 20
            assert len(m.sleeps) == 22 and not m.debugfs and not m.rawreads
        else:
            assert m.debugfs == [CTX]
            assert len(m.rawreads) == (1 if label == 'active-sequence-read-error' else 2)
        input_case = label in ['input-FF-error', 'input-register-error', 'MFD-error'] or success
        assert ('cs40l26_input_init' in m.entries) == input_case
        assert m.threads == (27 if input_case or label == 'IRQ-last-thread-error' else 0)
        assert m.virqs == m.threads
        if input_case:
            assert m.capabilities == [[21, 81], [21, 93], [21, 90], [21, 96]]
            assert m.string(m.u64(INPUT)) == 'cs40l26_input'
            assert m.u64(INPUT + 0x2d8) == CTX
        if input_case and label != 'input-FF-error':
            assert m.u64(INPUT + 0xc0) & (1 << 16) == 0
            for offset, name in [(0, 'cs40l26_upload_effect'), (8, 'cs40l26_erase_effect'),
                                 (16, 'cs40l26_playback_effect'), (24, 'cs40l26_set_gain')]:
                assert m.u64(FF + offset) == m.symbols[name]
        if label == 'MFD-error':
            assert [s['name'] for s in m.input_services][-2:] == ['sysfs_remove_groups', 'input_unregister_device']
        if success:
            assert m.workers == ['cs40l26_upload_worker', 'cs40l26_vibe_start_worker', 'cs40l26_erase_worker']
            assert len(m.effects) == 1
            effect = bytes.fromhex(m.effects[0])
            assert len(effect) == 48 and effect[:4] == bytes.fromhex('51000000')
            assert int.from_bytes(effect[10:12], 'little') == 100
            assert effect[16:22] == bytes.fromhex('5a0008002d00')
            assert m.worker_writes == [dict(worker=worker, address=address, value=value, result=0)
                for worker, address, value in [
                    ('cs40l26_upload_worker', 0x280701c, 25),
                    ('cs40l26_upload_worker', 0x2807014, 125),
                    ('cs40l26_upload_worker', 0x2807018, 45),
                    ('cs40l26_vibe_start_worker', 0x2802134, 100),
                    ('cs40l26_vibe_start_worker', 0x28059f0, 0)]]
            assert m.worker_mailbox == [dict(command=0x1800081,
                result=-5 if label == 'selftest-mailbox-error' else 0)]
            assert m.u32(CTX + 0x250) == m.u32(CTX + 0x254) == 0
            assert m.u64(CTX + 0x60) == CTX + 0x60 == m.u64(CTX + 0x68)
        else:
            assert not m.effects and not m.workers and not m.worker_mailbox
        cases.append(dict(sample=sample, case=label, status='PASS', result=result,
                          fw_loaded=loaded, entries=m.entries, raw_writes=m.raw,
                          raw_reads=m.rawreads, bulk_writes=m.bulk, reads=m.reads,
                          writes=m.writes, updates=m.updates, mailbox=m.mailbox,
                          sleeps=m.sleeps, requests=m.firmware_requests, releases=m.releases,
                          debugfs=m.debugfs, multi=m.multi, pm_services=m.pm,
                          irq_services=m.irq_services, virqs=m.virqs, threads=m.threads,
                          input_services=m.input_services, capabilities=m.capabilities,
                          input_registered_flag=bytes(m.uc.mem_read(CTX + 0x1c4, 1))[0],
                          effects=m.effects, workers=m.workers, work_results=m.work_results,
                          worker_writes=m.worker_writes, worker_mailbox=m.worker_mailbox,
                          workqueue_spec=m.workqueue_spec, messages=m.messages,
                          completion_services_called=[],
                          remove_body='original instructions; kernel teardown services are fixtures'))
    objdump = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    disasm = ROOT / 'logs' / f'{sample}-haptics-legacy-config-input.disasm'
    names = m.watch + ['cs40l26_debugfs_init', 'cs40l26_vibe_state_update']
    body = subprocess.check_output([objdump, '-dr', '--disassemble-symbols=' + ','.join(names), str(driver)])
    # Include the input function's out-of-symbol-size tail and LL/SC fallback.
    start = m.symbols['cs40l26_input_init'] - m.bases[m.elf.get_section_index('.text')]
    end = m.symbols['cs40l26_upload_effect'] - m.bases[m.elf.get_section_index('.text')]
    body += subprocess.check_output([objdump, '-dr', f'--start-address={start}',
                                    f'--stop-address={end}', str(driver)])
    disasm.write_bytes(body)
    return cases, {str(path.relative_to(ROOT)): sha(path) for path in paths + [driver, disasm]}


def main():
    dt_path = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dt_path.read_text())
    cases, sources = [], {str(dt_path.relative_to(ROOT)): sha(dt_path)}
    for sample in SAMPLES:
        current, fingerprints = exercise(sample, dt)
        cases.extend(current)
        sources.update(fingerprints)
    tests = {}
    for cls in ConfigInput.mro():
        if cls is object:
            continue
        path = Path(inspect.getfile(cls)).resolve()
        tests[str(path.relative_to(ROOT))] = sha(path)
    for name in ['tests/haptics_coefficients_emulation.py', 'tests/haptics_upload_emulation.py',
                 'scripts/firmware_facts.py', 'tests/haptics-emulator-dependencies.json']:
        tests[name] = sha(ROOT / name)
    report = dict(status='PASS', scope=__doc__, count=len(cases), cases=cases,
                  sources=sources, tests=tests, hardware_result='unverified',
                  emulator_files={str(path.relative_to(ROOT)): sha(path) for path in
                                  DEPS.rglob('*') if path.is_file() and
                                  (path.suffix in ['.py', '.so'] or '.so.' in path.name)})
    (ROOT / 'logs/haptics-legacy-config-input-join.json').write_text(
        json.dumps(report, indent=2) + '\n')
    print('PASS', len(cases), 'legacy config/input/selftest paths; no hardware output result')


if __name__ == '__main__':
    main()
