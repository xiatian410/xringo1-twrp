#!/usr/bin/env python3
"""Inspect stock calibration defaults and execute original OS4 sysfs stores.

Original firmware parser/metadata resolution and calibration store instructions
execute. Packed algorithm table is supplied at an explicit regmap boundary;
kernel conversion, mutex, runtime PM and register writes are fixtures. No DSP,
real calibration files, sysfs writes or motor executes. A store accepting a
value does not establish a requirement for calibration or physical readiness.
"""
import json
import struct
import subprocess
from pathlib import Path

from haptics_firmware_emulation import Firmware, FW, ROOT, DEPS, sha
from haptics_coefficients_emulation import table
from haptics_driver_emulation import (
    MASK, UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC,
)

CTX = 0x4000000
DEV = 0x4060000
NAMES = {'f0': 'F0_OTP_STORED', 'redc': 'REDC_OTP_STORED', 'q': 'Q_STORED'}


def history(blobs, address):
    """Independently decode the supplied memory image, not DSP execution."""
    assert address >= 0x2800000 and address % 4 == 0
    result = []
    blob = blobs['cs40l26.wmfw']
    pos = 40
    while pos < len(blob):
        tag, size = struct.unpack_from('<II', blob, pos)
        payload = blob[pos + 8:pos + 8 + size]
        assert len(payload) == size
        kind, word = tag >> 24, tag & 0xffffff
        value = None
        if kind == 17:
            assert size % 4 == 0
            stream = b''.join(payload[i:i + 4][::-1] for i in range(0, size, 4))
            assert len(stream) % 3 == 0
            index = (address - 0x2800000) // 4 - word
            if 0 <= index < len(stream) // 3:
                value = int.from_bytes(stream[3 * index:3 * index + 3], 'little')
        elif kind == 5:
            index = address - (0x2800000 + 4 * word)
            if 0 <= index <= size - 4:
                value = int.from_bytes(payload[index:index + 4], 'big')
        if value is not None:
            result.append(dict(file='cs40l26.wmfw', region_offset=pos, value=value))
        pos += 8 + ((size + 3) & ~3)
    assert pos == len(blob)
    rows = table(blob)[1]
    for name in ['cs40l26.bin', 'cs40l26-svc.bin', 'cs40l26-dvl.bin',
                 'cs40l26-a2h.bin', 'cs40l26-dbc.bin']:
        blob = blobs[name]
        assert blob[:4] == b'WMDR'
        pos = 16
        while pos < len(blob):
            delta, kind, algorithm, rev, rate, size = struct.unpack_from('<HHIIII', blob, pos)
            if kind == 5:
                row = next(r for r in rows if r[0] & 0xffff == algorithm & 0xffff)
                assert row[1] == rev >> 8
                index = address - (0x2800000 + row[2] * 4 + delta)
                if 0 <= index <= size - 4:
                    value = int.from_bytes(blob[pos + 20 + index:pos + 24 + index], 'big')
                    result.append(dict(file=name, region_offset=pos, value=value))
            pos += 20 + ((size + 3) & ~3)
        assert pos == len(blob)
    return result


class Calibration(Firmware):
    def __init__(self, path, blob):
        self.pm_error = 0
        self.pm_calls = []
        self.stores = []
        self.write_error = 0
        super().__init__(path, blob)
        self.hardware.update(table(blob)[0])
        self.read_error = 0
        # Original parser resolving all algorithms requires a larger finite
        # budget than the malformed/short-table cases in the shared suite.
        for i, value in enumerate([self.dsp, FW, 1]):
            self.uc.reg_write(UC_ARM64_REG_X0 + i, value)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x501fff0)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        self.uc.emu_start(self.symbols['cl_dsp_firmware_parse'], self.return_address,
                          count=1000000, timeout=10000000)
        assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, 'parser budget exhausted'
        assert self.arg(0) == 0 and len(self.records()) == 525
        self.put64(DEV + 0x98, CTX)
        self.put64(CTX, DEV)
        self.put64(CTX + 8, 0x4070000)
        self.put64(CTX + 0x50, self.dsp)
        self.uc.mem_write(CTX + 0x13, b'\xb2')
        # Boundaries: firmware parser/get_reg remain original.
        self.intercept('cs40l26_pm_enter')
        self.intercept('cs40l26_pm_exit')

    def on_code(self, u, address, size, data):
        name = self.hooks.get(address)
        if name == 'kstrtouint':
            assert self.arg(1) == 16
            text = self.string(self.arg(0)).strip()
            try:
                value = int(text, 16)
            except ValueError:
                result = -22
            else:
                result = -34 if value < 0 or value > 0xffffffff else 0
                if result == 0:
                    self.put32(self.arg(2), value)
        elif name in ['cs40l26_pm_enter', 'cs40l26_pm_exit']:
            result = self.pm_error if name.endswith('enter') else 0
            self.pm_calls.append(dict(name=name, result=result))
        elif name == 'regmap_write':
            assert self.arg(0) == 0x4070000
            self.stores.append(dict(address=self.arg(1), value=self.arg(2), result=self.write_error))
            result = self.write_error
        else:
            return super().on_code(u, address, size, data)
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0, result & MASK)
        u.reg_write(UC_ARM64_REG_PC, u.reg_read(UC_ARM64_REG_X30))


def main():
    cases, sources, defaults = [], {}, {}
    dtpath = ROOT / 'logs/haptics-devicetree-audit.json'
    dt = json.loads(dtpath.read_text())
    sources[str(dtpath.relative_to(ROOT))] = sha(dtpath)
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        path = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in files + [path]})
        m = Calibration(path, blobs['cs40l26.wmfw'])
        records = {r['name']: r for r in m.records() if r['name'] in NAMES.values()}
        assert set(records) == set(NAMES.values())
        defaults[sample] = {}
        for name in NAMES.values():
            supplied = history(blobs, records[name]['register'])
            assert not supplied, (sample, name, supplied)
            defaults[sample][name] = dict(coefficient=records[name], history=supplied,
                                         initial_value=supplied[-1]['value'] if supplied else None,
                                         file_initialization_found=bool(supplied))
        for key, name in NAMES.items():
            for label in ['valid-B2', 'valid-A1', 'invalid-text', 'PM-error', 'write-error']:
                m.uc.mem_write(CTX + 0x13, b'\xa1' if label == 'valid-A1' else b'\xb2')
                m.pm_error = -5 if label == 'PM-error' else 0
                m.write_error = -5 if label == 'write-error' else 0
                m.pm_calls.clear()
                m.stores.clear()
                value = {'f0': '208000\n', 'redc': '28000\n', 'q': 'a000\n'}[key]
                text = 'invalid\n' if label == 'invalid-text' else value
                m.uc.mem_write(0x4088000, text.encode() + b'\0')
                result = m.run(key + '_stored_store', DEV, 0, 0x4088000, len(text))
                rejected_b2 = key == 'q' and label != 'valid-A1'
                expected = -1 if rejected_b2 else -22 if label == 'invalid-text' else -5 if label in ['PM-error', 'write-error'] else len(text)
                assert result == expected, (sample, key, label, result, expected)
                attempted_write = not rejected_b2 and label not in ['invalid-text', 'PM-error']
                assert m.stores == ([dict(address=records[name]['register'], value=int(value, 16), result=m.write_error)] if attempted_write else [])
                if rejected_b2 or label == 'invalid-text':
                    assert not m.pm_calls
                else:
                    assert [c['name'] for c in m.pm_calls] == (['cs40l26_pm_enter'] if label == 'PM-error' else ['cs40l26_pm_enter', 'cs40l26_pm_exit'])
                cases.append(dict(sample=sample, case=key + '-' + label, status='PASS',
                                  result=result, stores=m.stores[:], pm=m.pm_calls[:]))
        properties = next(c for c in dt['cases'] if c['sample'] == sample and
                          c['case'] == 'overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        default_f0 = properties['cirrus,f0-default'][0]
        assert default_f0 == 130 << 14
        # Explicit post-DT-parser field fixture; the DT parser-to-field mapping
        # is separately exercised by the existing original probe/upload suite.
        for label in ['DT-default-B2', 'DT-default-write-error', 'no-DT-default-B2']:
            m.uc.mem_write(CTX + 0x13, b'\xb2')
            m.put32(CTX + 0x1bbc, 0 if label == 'no-DT-default-B2' else default_f0)
            m.put32(CTX + 0x1bc0, 0)
            m.put32(CTX + 0x1bc4, 0)
            m.pm_calls.clear()
            m.stores.clear()
            m.write_error = -5 if label == 'DT-default-write-error' else 0
            result = m.run('cs40l26_calib_dt_config', CTX)
            assert result == m.write_error
            assert not m.pm_calls
            assert m.stores == ([] if label == 'no-DT-default-B2' else [dict(
                address=records[NAMES['f0']]['register'], value=default_f0, result=m.write_error)])
            cases.append(dict(sample=sample, case=label, status='PASS', result=result,
                              stores=m.stores[:], pm=m.pm_calls[:], dt_f0=default_f0))
        disasm = ROOT / 'logs' / (sample + '-haptics-calibration-coefficients-core.disasm')
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=f0_stored_store,q_stored_store,redc_stored_store,cs40l26_calib_dt_config',
            str(path.relative_to(ROOT))], cwd=ROOT))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
    tests = [Path(__file__).resolve()] + [ROOT / 'tests' / name for name in [
        'haptics_firmware_emulation.py', 'haptics_coefficients_emulation.py',
        'haptics_upload_emulation.py', 'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    tests.append(ROOT / 'scripts/firmware_facts.py')
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                  (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    report = dict(status='PASS', scope=__doc__.strip(), defaults=defaults, cases=cases,
                  sources=sources, tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in deps})
    (ROOT / 'logs/haptics-calibration-coefficients-emulation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original calibration stores; DSP/motor unverified')
    print(json.dumps(defaults, indent=2))


if __name__ == '__main__':
    main()
