#!/usr/bin/env python3
"""Join original OS4 SINE upload to the actual firmware coefficient resolver.

Production FF bytes are captured with ioctl/write fixtures. Original WMFW
parser, coefficient initialization/get_reg and SINE upload execute together.
The file-decoded algorithm table, allocation, PM and regmap are explicit
boundaries; register writes are recorded and never execute DSP or hardware.
No calibration, real evdev/input core, boot or physical vibration is tested.
"""
import json
from pathlib import Path
import struct
import subprocess
import tempfile

from haptics_calibration_coefficients_emulation import Calibration, ROOT
from haptics_coefficients_emulation import table
from haptics_driver_emulation import DEPS, SOURCE, sha, capture

CTX, EFFECT, RECORD = 0x4000000, 0x4080000, 0x4081000


def main():
    cases, sources, observations = [], {}, {}
    with tempfile.TemporaryDirectory(prefix='sine-coefficients-') as temp:
        captured = capture(Path(temp))
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        driver = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        firmware = base / 'odm/firmware/cs40l26.wmfw'
        assert sha(driver) == '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        m = Calibration(driver, firmware.read_bytes())
        coefficients = {r['name']: r for r in m.records()}
        row, = [r for r in table(firmware.read_bytes())[1] if r[0] == 0x4f202]
        # Independent address calculation from packed firmware X-base and
        # known BUZZ2 offsets; compare with original parser output.
        for name, offset in [('FREQ', 3), ('LEVEL', 4), ('DURATION', 5)]:
            record = coefficients['BUZZ_EFFECTS2_BUZZ_' + name]
            assert record['offset'] == offset and record['type'] == 5
            assert record['register'] == 0x2800000 + 4 * (row[2] + offset)
        slots = next(m.bases[i] for i, s in enumerate(m.sections) if s.name == '.data') + 0x3960
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in [driver, firmware]})
        disasm = ROOT / 'logs' / (sample + '-haptics-sine-coefficients-core.disasm')
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=cs40l26_sine_upload,cl_dsp_get_reg,cl_dsp_get_coeff', str(driver)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)

        def execute(effect, label, duration, frequency, magnitude, error=0):
            m.write_error = error
            m.stores.clear()
            m.uc.mem_write(EFFECT, bytes(effect))
            m.uc.mem_write(RECORD, b'\xa5' * 16)
            rc = m.run('cs40l26_sine_upload', CTX, EFFECT, RECORD)
            expected_names = ['BUZZ_EFFECTS2_BUZZ_DURATION', 'BUZZ_EFFECTS2_BUZZ_FREQ', 'BUZZ_EFFECTS2_BUZZ_LEVEL']
            # The parsed metadata uses RAM algorithm0x4f202, while the original
            # caller passes0x1f202. Original resolver handles this alias; no
            # cl_dsp_get_reg/get_coeff interception is installed here.
            assert all(coefficients[n]['algorithm'] == 0x4f202 for n in expected_names)
            expected = [dict(address=coefficients[n]['register'], value=v, result=error)
                        for n, v in zip(expected_names, [(duration + 3) // 4, frequency, magnitude])]
            assert rc == error and m.stores == (expected[:1] if error else expected), (label, rc, m.stores)
            if error:
                assert bytes(m.uc.mem_read(RECORD, 16)) == b'\xa5' * 16
            else:
                assert m.u32(RECORD) == 7 and m.u32(RECORD + 4) == 0x1800081
                assert bytes(m.uc.mem_read(RECORD + 8, 2)) == b'\3\0'
            cases.append(dict(sample=sample, case=label, status='PASS', result=rc,
                              effect=bytes(effect).hex(), writes=m.stores[:],
                              coefficient_names=expected_names, slot_id=m.u32(slots + 24)))

        for requested, effect, event in captured:
            execute(effect, 'production-' + str(requested), min(requested, 10000), 125, 64)
        base_effect = bytearray(captured[2][1])
        for period, expected in [(0, 250), (3, 250), (4, 250), (8, 125), (10, 100), (11, 100), (65535, 100)]:
            effect = base_effect[:]
            struct.pack_into('<H', effect, 18, period)
            execute(effect, 'period-' + str(period), 80, expected, 64)
        for magnitude, expected in [(-1, 0), (0, 0), (45, 45), (64, 64), (255, 255), (32767, 255)]:
            effect = base_effect[:]
            struct.pack_into('<h', effect, 20, magnitude)
            execute(effect, 'magnitude-' + str(magnitude), 80, 125, expected)
        for slot in range(5): m.put32(slots + slot * 32 + 24, 0xffffffff)
        execute(base_effect, 'first-write-error', 80, 125, 64, -5)
        assert m.u32(slots + 24) == 7  # reservation precedes the failed write
        execute(base_effect, 'same-id-retry-after-error', 80, 125, 64)
        observations[sample] = dict(parsed_coefficients=len(coefficients),
                                    caller_algorithm='0x1f202', metadata_algorithm='0x4f202',
                                    actual_buzz2={n: coefficients[n] for n in coefficients if n.startswith('BUZZ_EFFECTS2_')},
                                    production_period_ms=8, production_frequency_hz=125,
                                    production_magnitude=64,
                                    hardware_readback=False)
    tests = [Path(__file__).resolve()] + [ROOT / 'tests' / name for name in [
        'haptics_calibration_coefficients_emulation.py', 'haptics_firmware_emulation.py',
        'haptics_coefficients_emulation.py', 'haptics_upload_emulation.py',
        'haptics_driver_emulation.py', 'haptics_driver_capture.cpp', 'haptics-emulator-dependencies.json']]
    tests.append(ROOT / 'scripts/firmware_facts.py')
    sources.update({str(p): sha(p) for p in [SOURCE, SOURCE.with_suffix('.h')]})
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases, observations=observations,
                  sources=sources, tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-sine-coefficients-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original SINE/parser/resolver cases; no DSP or motor execution')


if __name__ == '__main__': main()
