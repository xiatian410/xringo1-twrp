#!/usr/bin/env python3
"""Review the missing audio-initialization hypothesis using original OS4 bytes.

Decode stock WMFW/WMDR initial values and run original ALSA get callbacks.
The algorithm table and coefficient values are supplied at the regmap boundary;
ALSA objects, PM and register reads are fixtures. No audio core, DSP or motor
executes. A file default is not a readback from the user's controller.
"""
import io
import json
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

from haptics_calibration_coefficients_emulation import Calibration, history, ROOT
from haptics_driver_emulation import ELFFile, sha, DEPS


class Controls(Calibration):
    failing_register = None

    def on_code(self, u, address, size, data):
        failing = (self.hooks.get(address) == 'regmap_read' and
                   self.arg(1) == self.failing_register)
        self.read_error = -5 if failing else 0
        return super().on_code(u, address, size, data)


def main():
    cases, sources, observations = [], {}, {}
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis'
        driver = base / 'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        assert sha(driver) == '969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        files = sorted((base / 'odm/firmware').glob('cs40l26*'))
        blobs = {p.name: p.read_bytes() for p in files}
        waveform = base / 'odm/etc/waveform_conf.xml'
        audio = base / 'odm/etc/audio/sku_xring/audio_route_config.xml'
        service = base / 'odm/bin/hw/vendor.xring.hardware.vibratorfeature.service'
        assert sha(service) == '0eacb88e11a3402b1551b79cc85e3cfcbbd518c7da44684fc5354829e27be2e7'
        sources.update({str(p.relative_to(ROOT)): sha(p) for p in files + [driver, waveform, audio, service]})
        wave = ET.fromstring(waveform.read_bytes())
        long_id = int(wave.findtext('long_vib_id/data'))
        lists = {name: [int(v) for v in wave.findtext(name + '/data').split(',')]
                 for name in ['no_svc', 'no_dvl']}
        audio_tree = ET.fromstring(audio.read_bytes())
        controls = [dict(c.attrib) for c in audio_tree.iter('ctl')
                    if c.get('name') in ['Haptics Source', 'SVC Algo Enable', 'DVL Algo Enable']]
        assert long_id == 31 and long_id in lists['no_svc'] and long_id not in lists['no_dvl']
        assert {'name': 'SVC Algo Enable', 'value': '1'} in controls
        assert {'name': 'Haptics Source', 'value': 'Off'} in controls
        m = Controls(driver, blobs['cs40l26.wmfw'])
        records = m.records()
        # Private ALSA kcontrol -> component -> device -> driver_data chain,
        # following the loads in the original get callbacks. Not an ALSA core.
        control, value = 0x4080000, 0x4084000
        for address, pointer in [(control + 0x80, control + 0x1000),
                                 (control + 0x1010, control + 0x2000),
                                 (control + 0x2098, control + 0x3000),
                                 (control + 0x3000, 0x4000000)]:
            m.put64(address, pointer)
        defaults = {}
        elf = ELFFile(io.BytesIO(driver.read_bytes()))
        rodata = elf.get_section_by_name('.rodata').data()
        # Bind the coefficient names at the original get callback relocations.
        assert rodata[0x10e36:].split(b'\0')[0] == b'FLAGS'
        assert rodata[0x18781:].split(b'\0')[0] == b'EN'
        for kind, algorithm, name, expected in [('svc', 0x4013c, 'FLAGS', 0),
                                                 ('dvl', 0x40140, 'EN', 1)]:
            record, = [r for r in records if r['algorithm'] == algorithm and r['name'] == name]
            supplied = history(blobs, record['register'])
            assert supplied and supplied[-1]['value'] == expected
            defaults[kind] = dict(coefficient=record, file_history=supplied)
            m.hardware[record['register']] = expected
            for label in ['file-default', 'PM-error', 'read-error']:
                m.pm_error = -5 if label == 'PM-error' else 0
                m.failing_register = record['register'] if label == 'read-error' else None
                before = len(m.reads)
                m.pm_calls.clear()
                m.put32(value + 0x48, 0xa5a5a5a5)
                result = m.run('cs40l26_' + kind + '_en_get', control, value)
                observed = m.u32(value + 0x48)
                assert result == (0 if label == 'file-default' else -5)
                assert observed == (expected if label == 'file-default' else 0xa5a5a5a5)
                reads = m.reads[before:]
                coefficient_reads = [r for r in reads if r['address'] == record['register']]
                assert len(coefficient_reads) == (0 if label == 'PM-error' else 1)
                if coefficient_reads:
                    assert coefficient_reads[0]['result'] == (-5 if label == 'read-error' else 0)
                    assert coefficient_reads[0]['value'] == (None if label == 'read-error' else expected)
                assert [p['name'] for p in m.pm_calls] == (
                    ['cs40l26_pm_enter'] if label == 'PM-error'
                    else ['cs40l26_pm_enter', 'cs40l26_pm_exit'])
                cases.append(dict(sample=sample, case=kind + '-' + label, status='PASS',
                                  result=result, returned_value=observed, reads=reads,
                                  pm=m.pm_calls[:]))
        observations[sample] = dict(defaults=defaults, audio_controls=controls,
                                    long_id=long_id, long_id_in_no_svc=True,
                                    long_id_in_no_dvl=False)
        disasm = ROOT / 'logs' / (sample + '-haptics-algorithm-controls.disasm')
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump',
            '-dr', '--disassemble-symbols=cs40l26_get_ram_ext_algo_id,cs40l26_svc_en_get,cs40l26_dvl_en_get,cs40l26_vibe_start_worker',
            str(driver.relative_to(ROOT))], cwd=ROOT))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
    tests = [Path(__file__).resolve()] + [ROOT / 'tests' / p for p in [
        'haptics_calibration_coefficients_emulation.py', 'haptics_firmware_emulation.py',
        'haptics_coefficients_emulation.py', 'haptics_driver_emulation.py',
        'haptics_upload_emulation.py', 'haptics-emulator-dependencies.json']]
    tests.append(ROOT / 'scripts/firmware_facts.py')
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and
                  (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases,
                  observations=observations, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in tests},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in deps})
    target = ROOT / 'logs/haptics-algorithm-defaults-review.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original getter checks; file defaults SVC=0/DVL=1; no physical output conclusion')


if __name__ == '__main__':
    main()
