#!/usr/bin/env python3
"""Trace the field A1 revision's calibration difference using original OS4 code.

Original probe parses original DT properties and chip ID, then firmware upload
is deliberately failed. Its parsed calibration fields are transferred to a
separate original firmware-parser/calibration context. This is an explicit
context boundary, not a joined full A1 probe or DSP boot. Regmap/PM/kernel
services are fixtures; values are synthetic and must never be used on a phone.
"""
import json
from pathlib import Path
import subprocess

from haptics_calibration_coefficients_emulation import Calibration, DEV, CTX, ROOT, sha
from haptics_probe_upload_emulation import ProbeUpload
from haptics_driver_emulation import DEPS, UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC


class ParsedFields(ProbeUpload):
    def __init__(self, path, blobs, properties):
        super().__init__(path, blobs, properties)
        self.hardware.update({0: 0x40a260, 4: 0xa1})
        self.intercept('cs40l26_fw_upload')
        self.upload_boundary = []

    def on_code(self, u, address, size, data):
        if self.hooks.get(address) == 'cs40l26_fw_upload':
            assert self.arg(0) == CTX
            self.upload_boundary.append(dict(revision=bytes(u.mem_read(CTX + 0x13, 1)).hex(),
                fields={name: self.u32(CTX + offset) for name, offset in
                        [('f0', 0x1bbc), ('redc', 0x1bc0), ('q', 0x1bc4)]}))
            u.reg_write(UC_ARM64_REG_X0, 0xfffffffb)
            u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))
            return
        return super().on_code(u, address, size, data)


class AddressFailure(Calibration):
    def __init__(self, *args):
        self.fail_address = None
        super().__init__(*args)

    def on_code(self, u, address, size, data):
        if self.hooks.get(address) == 'regmap_write':
            self.write_error = -5 if self.arg(1) == self.fail_address else 0
        return super().on_code(u, address, size, data)


def main():
    dt_path = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dt_path.read_text())
    cases, parsed, sources = [], {}, {str(dt_path.relative_to(ROOT)): sha(dt_path)}
    for field in ['sources', 'libfdt_sources']:
        for filename, expected in dt[field].items():
            p = Path(filename) if Path(filename).is_absolute() else ROOT / filename
            assert sha(p) == expected, filename
            sources[str(p)] = expected
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        path = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        properties = next(c for c in dt['cases'] if c['sample'] == sample and
                          c['case'] == 'overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        assert properties['cirrus,f0-default'] == [130 << 14]
        assert 'cirrus,q-default' not in properties and 'cirrus,redc-default' not in properties
        probe = ParsedFields(path, blobs, properties)
        assert probe.run('cs40l26_probe', CTX) == -5 and probe.removed == [CTX]
        assert len(probe.upload_boundary) == 1
        fields = probe.upload_boundary[0]
        assert fields == dict(revision='a1', fields=dict(f0=130 << 14, redc=0, q=0))
        assert not probe.raw and 'cs40l26_input_init' not in probe.entries
        parsed[sample] = dict(boundary=fields, property_reads=probe.property_reads,
                              remove_calls=probe.removed, result=-5)
        m = AddressFailure(path, blobs['cs40l26.wmfw'])
        records = {r['name']: r['register'] for r in m.records() if r['name'] in
                   ['F0_OTP_STORED', 'REDC_OTP_STORED', 'Q_STORED']}
        assert records == dict(F0_OTP_STORED=0x2802128, REDC_OTP_STORED=0x280212c, Q_STORED=0x2802150)
        for label in ['stock-A1', 'stock-B2', 'positive-q-A1', 'out-of-range-q-A1',
                      'f0-write-error-A1', 'q-write-error-A1', 'restore-q-A1', 'restore-q-PM-error-A1']:
            m.uc.mem_write(CTX + 0x13, b'\xb2' if label == 'stock-B2' else b'\xa1')
            for name, offset in [('f0', 0x1bbc), ('redc', 0x1bc0), ('q', 0x1bc4)]:
                m.put32(CTX + offset, fields['fields'][name])
            q = 0xa000 if label == 'positive-q-A1' else 0x800000 if label == 'out-of-range-q-A1' else 0
            m.put32(CTX + 0x1bc4, q)
            m.stores.clear(); m.pm_calls.clear()
            m.pm_error = -5 if label == 'restore-q-PM-error-A1' else 0
            m.fail_address = 0x2802128 if label == 'f0-write-error-A1' else 0x2802150 if label == 'q-write-error-A1' else None
            restore = label.startswith('restore-')
            if restore:
                text = b'a000\n'
                m.uc.mem_write(0x4088000, text + b'\0')
                rc = m.run('q_stored_store', DEV, 0, 0x4088000, len(text))
                expected_rc = -5 if m.pm_error else len(text)
                expected = [] if m.pm_error else [dict(address=0x2802150, value=0xa000, result=0)]
            else:
                rc = m.run('cs40l26_calib_dt_config', CTX)
                expected_rc = -5 if 'write-error' in label else 0
                expected = [dict(address=0x2802128, value=130 << 14,
                                 result=-5 if label == 'f0-write-error-A1' else 0)]
                if label not in ['stock-B2', 'out-of-range-q-A1', 'f0-write-error-A1']:
                    expected.append(dict(address=0x2802150, value=q,
                                         result=-5 if label == 'q-write-error-A1' else 0))
            assert rc == expected_rc and m.stores == expected, (sample, label, rc, m.stores)
            assert len(m.pm_calls) == (1 if m.pm_error else 2 if restore else 0)
            cases.append(dict(sample=sample, case=label, status='PASS', result=rc,
                              register_write_requests=list(m.stores), pm_calls=list(m.pm_calls),
                              synthetic_q=q, observed_hardware_readback=False))
        disasm = ROOT / 'logs' / f'{sample}-haptics-A1-calibration-review.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump',
            '-dr', '--disassemble-symbols=cs40l26_probe,cs40l26_calib_dt_config,q_stored_store', str(path)]))
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in files + [path, disasm]})
    # Include the exact field ID evidence, without interpreting it as register readback.
    field_log = ROOT / 'imgs/built/1/touch-dmesg-before.txt'
    field_text = field_log.read_bytes().decode('utf-16')
    identity = [line for line in field_text.splitlines() if 'Cirrus Logic CS40L26 ID:' in line]
    assert len(identity) == 1 and '0x40A260, Revision: 0xA1' in identity[0]
    sources[str(field_log.relative_to(ROOT))] = sha(field_log)
    for name in ['haptics_a1_calibration_review.py', 'haptics_calibration_coefficients_emulation.py',
                 'haptics_probe_upload_emulation.py', 'haptics_config_emulation.py',
                 'haptics_coefficients_emulation.py', 'haptics_upload_emulation.py',
                 'haptics_firmware_emulation.py', 'haptics_driver_emulation.py',
                 'haptics-emulator-dependencies.json']:
        p = ROOT / 'tests' / name; sources[str(p.relative_to(ROOT))] = sha(p)
    report = dict(status='PASS', scope=__doc__, count=len(cases), cases=cases,
                  field_identity=identity[0], parsed_probe_fields=parsed, sources=sources,
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)},
                  conclusion='Original A1 DT configuration attempts F0=130Hz and Q_STORED=0 when q-default is absent; B2 skips Q. Original A1 q_stored accepts a positive synthetic restore value. No actual device Q, DSP behavior, persist restore or physical root cause established.')
    (ROOT / 'logs/haptics-A1-calibration-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'cases; A1 default Q write is zero, field Q readback unknown')


if __name__ == '__main__':
    main()
