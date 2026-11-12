#!/usr/bin/env python3
"""Check original legacy probe/upload evidence without claiming hardware success."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/haptics-legacy-probe-upload-join.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and report['count'] == len(report['cases']) == 20
    assert report['hardware_result'] == 'unverified'
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, fingerprint in report[group].items():
            assert sha(ROOT / name) == fingerprint, name
    labels = {'config-MEM_RDY-error', 'pre-state2-config-MEM_RDY-error',
              'pre-state3-stuck', 'firmware-first-write-error', 'main-bin-missing'}
    for sample in ['os2-initial', 'os2-final', 'os3-initial', 'os3-final']:
        cases = {case['case']: case for case in report['cases'] if case['sample'] == sample}
        assert set(cases) == labels
        for label, case in cases.items():
            assert case['status'] == 'PASS' and case['fw_loaded'] == 0
            assert case['result'] == (-22 if label == 'pre-state3-stuck' else -5)
            assert case['no_input_registration'] and case['no_dsp_execution']
            assert case['remove_body'] == 'original instructions; kernel teardown services are fixtures'
            assert case['entries'].count('cs40l26_remove') == 1
            assert case['entries'][0] == 'cs40l26_probe'
            assert 'cs40l26_input_init' not in case['entries']
            assert case['teardown'][-1] == 'debugfs_remove'
            assert case['mailbox'] == [dict(command=0x02000003, result=0)]
            assert case['reads'][:2] == [dict(address=0, value=0x40a270, result=0),
                                         dict(address=4, value=0xb2, result=0)]
            states = [r['value'] for r in case['reads'] if r['address'] == case['rom'][0]]
            assert states == ([3] * 11 if label == 'pre-state3-stuck' else
                              [3, 2 if label == 'pre-state2-config-MEM_RDY-error' else 1])
            assert len(case['raw_writes']) == (0 if label == 'pre-state3-stuck' else
                                               1 if label == 'firmware-first-write-error' else
                                               63 if label == 'main-bin-missing' else 68)
            if label == 'pre-state3-stuck':
                assert not case['releases']
                assert case['messages'].count('DSP core not safe to kill\n') == 10
                assert len(case['sleeps']) == 12  # Two original power/reset waits, ten PM polls.
                assert 'cl_dsp_firmware_parse' not in case['entries']
            elif label == 'firmware-first-write-error':
                assert len(case['releases']) == 1 and len(case['requests']) == 1
                assert 'cs40l26_coeff_load' not in case['entries']
            else:
                assert len(case['requests']) == 6
                assert len(case['releases']) == (5 if label == 'main-bin-missing' else 6)
                assert case['entries'][-2:] == ['cs40l26_dsp_config', 'cs40l26_remove']
                assert case['updates'][-1] == dict(address=0x2900, mask=2, value=2, result=-5)
                assert case['entries'].count('cl_dsp_coeff_file_parse') == (
                    4 if label == 'main-bin-missing' else 5)
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    check, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS2-OS3-haptics-probe-upload-join']
    assert check['count'] == 20 and check['evidence_sha256'] == sha(path)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    assert sha(Path(index['image'])) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, count=20, production_change=False,
                  physical_vibration='unverified', image_sha256=index['image_sha256'],
                  evidence_sha256=sha(path), audit_script_sha256=sha(Path(__file__)),
                  documents={name: sha(ROOT / name) for name in [
                      'ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'simulation-report.md',
                      'simulation-report.json', 'docs/archive/haptics/HAPTICS-FIRMWARE-EMULATION.md']})
    (ROOT / 'logs/haptics-legacy-probe-upload-join-audit.json').write_text(
        json.dumps(result, indent=2) + '\n')
    print('PASS: 20 original legacy probe/upload paths; source hashes bound, no motor claim')


if __name__ == '__main__':
    main()
