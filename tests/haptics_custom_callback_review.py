#!/usr/bin/env python3
"""Join stock service CUSTOM bytes to the original post-probe upload callback.

Original callback/allocation checks/user-range checks/worker/start execute.
__arch_copy_from_user is an explicit bounded memory-copy fixture, not privileged
access to a real user process. Task/MMU state, kernel services, PM/registers,
mailbox and stock-derived wave-count readback remain fixtures. No DSP or motor.
"""
import inspect
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from haptics_stock_wave_review import Stock, inventory, service_request
from haptics_a1_joined_review import ROOT, CTX, sha, DEPS
from haptics_active_erase_emulation import INPUT, EFFECT, EFFECTS
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

USER = 0x40f0000


class Callback(Stock):
    def __init__(self, *args):
        self.copy_residual = 0
        self.custom_allocation_failure = False
        self.copies = []
        self.object_checks = []
        self.custom_allocations = []
        self.zero_fills = []
        self.freed_custom_bytes = []
        super().__init__(*args)

    def on_code(self, u, address, size, data):
        name = self.hooks.get(address)
        if self.runtime and name == '__check_object_size':
            assert self.arg(2) == 0
            self.object_checks.append([self.arg(0), self.arg(1)])
            result = 0
        elif self.runtime and name == '__arch_copy_from_user':
            dest, src, length = [self.arg(i) for i in range(3)]
            assert src == USER and length == 4
            assert self.object_checks[-1] == [dest, length]
            assert 0 <= self.copy_residual <= length
            copied = length - self.copy_residual
            if copied:
                u.mem_write(dest, bytes(u.mem_read(src, copied)))
            self.copies.append(dict(source=src, destination=dest, length=length,
                                    residual=self.copy_residual,
                                    bytes=bytes(u.mem_read(dest, copied)).hex()))
            result = self.copy_residual
        elif self.runtime and name == 'memset':
            dest, value, length = [self.arg(i) for i in range(3)]
            assert self.custom_allocations and value == 0
            start = self.custom_allocations[-1]
            assert start <= dest <= start + 4 and length == start + 4 - dest
            u.mem_write(dest, bytes(length))
            self.zero_fills.append(dict(destination=dest, length=length))
            result = dest
        elif self.runtime and name == 'kfree':
            if self.arg(0) in self.custom_allocations and self.arg(0):
                self.freed_custom_bytes.append(bytes(u.mem_read(self.arg(0), 4)).hex())
            return super().on_code(u, address, size, data)
        elif self.runtime and name == '__kmalloc_noprof':
            assert self.arg(0) == 4
            if not self.custom_allocation_failure:
                # Let the existing bounded allocator execute its boundary.
                super().on_code(u, address, size, data)
                self.custom_allocations.append(self.arg(0))
                return
            self.custom_allocations.append(0)
            result = 0
        else:
            return super().on_code(u, address, size, data)
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0, result & MASK)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))


def main():
    dtpath = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dtpath.read_text())
    sources = {str(dtpath.relative_to(ROOT)): sha(dtpath)}
    cases = []
    labels = ['stock-long31', 'copy-residual1', 'copy-residual4',
              'allocation-failure', 'user-range-rejected', 'outside43']
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        module = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        service = base / 'odm/bin/hw/vendor.xring.hardware.vibratorfeature.service'
        disasm = ROOT / 'logs' / f'{sample}-vibrator-service.disasm'
        xml = base / 'odm/etc/waveform_conf.xml'
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        for p in files + [module, service, disasm, xml]:
            sources[str(p.relative_to(ROOT))] = sha(p)
        long_id = int(ET.fromstring(xml.read_bytes()).findtext('long_vib_id/data'))
        assert long_id == 31
        operations, _ = service_request(service, disasm.read_text(), long_id, 80)
        effect = bytearray.fromhex(operations[1]['effect'])
        assert bytes.fromhex(operations[1]['custom']) == struct.pack('<HH', 0, 31)
        props = next(c for c in dt['cases'] if c['sample'] == sample and
                     c['case'] == 'overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        for label in labels:
            m = Callback(module, blobs, props, 'A1')
            assert m.run('cs40l26_probe', CTX) == 0
            wt = m.u64(m.u64(CTX + 0x50) + 0x358)
            count = m.u32(wt + 0x1850)
            assert count == len(inventory(blobs['cs40l26.bin'])['records']) == 43
            m.hardware[0x2802140] = count  # explicit DSP-count read boundary
            request = bytearray(effect)
            struct.pack_into('<h', request, 2, 7)  # synthetic input-core ID
            struct.pack_into('<Q', request, 40, (1 << 39) - 2 if label == 'user-range-rejected' else USER)
            m.uc.mem_write(USER, struct.pack('<HH', 0, 43 if label == 'outside43' else 31))
            m.uc.mem_write(EFFECT, bytes(request))
            m.uc.mem_write(EFFECTS + 7 * 48, bytes(request))
            if label.startswith('copy-residual'):
                m.copy_residual = int(label[-1])
            m.custom_allocation_failure = label == 'allocation-failure'
            m.runtime = True
            m.selftest_mail.clear()
            m.selftest_writes.clear()
            free_start = len(m.frees)
            rc = m.runtime_call('cs40l26_upload_effect', INPUT, EFFECT, 0)
            expected = (0 if label == 'stock-long31' else -12 if label == 'allocation-failure'
                        else -22 if label == 'outside43' else -14)
            assert rc == expected, (sample, label, rc, m.messages)
            assert m.u64(CTX + 0xb0) == 0
            assert bytes(m.uc.mem_read(CTX + 0x78, 48)) == bytes(48)
            frees = m.frees[free_start:]
            assert len(m.custom_allocations) == 1
            assert frees == m.custom_allocations
            assert len(m.copies) == int(label not in ['allocation-failure', 'user-range-rejected'])
            if label in ['copy-residual1', 'copy-residual4', 'user-range-rejected']:
                assert len(m.zero_fills) == 1
                assert m.zero_fills[0]['length'] == (1 if label == 'copy-residual1' else 4)
                assert m.freed_custom_bytes == ['00001f00' if label == 'copy-residual1' else '00000000']
            else:
                assert not m.zero_fills
            assert m.runtime_workers == (['cs40l26_upload_worker'] if label in ['stock-long31', 'outside43'] else [])
            if label == 'stock-long31':
                assert m.runtime_call('cs40l26_playback_effect', INPUT, 7, 1) == 0
                m.flush_until(CTX + 0xc0)
                assert m.selftest_mail == [dict(command=0x100001f, result=0)]
                assert [w['value'] for w in m.selftest_writes] == [0, 0]
            else:
                assert not m.selftest_mail and not m.selftest_writes
            cases.append(dict(sample=sample, case=label, status='PASS', result=rc,
                              service_effect=bytes(request).hex(), copies=m.copies,
                              allocations=m.custom_allocations, frees=frees,
                              zero_fills=m.zero_fills,
                              freed_custom_bytes=m.freed_custom_bytes,
                              workers=m.runtime_workers, mailbox=m.selftest_mail,
                              writes=m.selftest_writes, stock_wave_count=count))
            print(sample, label, rc, flush=True)
    tests = {str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__))}
    for cls in Callback.mro():
        if cls is not object:
            p = Path(inspect.getfile(cls)).resolve()
            tests[str(p.relative_to(ROOT))] = sha(p)
    for name in ['haptics_service_request_emulation.py', 'haptics_coefficients_emulation.py']:
        p = ROOT / 'tests' / name
        tests[str(p.relative_to(ROOT))] = sha(p)
    report = dict(status='PASS', scope=__doc__, cases=cases, sources=sources, tests=tests,
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-custom-callback-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS', len(cases), 'stock callback/custom-copy joins; no DSP or motor evidence')


if __name__ == '__main__':
    main()
