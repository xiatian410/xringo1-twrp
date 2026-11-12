#!/usr/bin/env python3
"""Bind legacy config/input/self-test results to actual module and fixture bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/haptics-legacy-config-input-join.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and report['count'] == len(report['cases']) == 44
    assert report['hardware_result'] == 'unverified'
    for group in ['sources', 'tests', 'emulator_files']:
        for name, fingerprint in report[group].items():
            assert sha(ROOT / name) == fingerprint, name
    labels = {'CALL-RAM-exhausted', 'active-sequence-read-error', 'HALO-invalid',
              'runtime-resume-error', 'IRQ-chip-error', 'IRQ-last-thread-error',
              'input-FF-error', 'input-register-error', 'MFD-error',
              'selftest-ACK-fixture', 'selftest-mailbox-error'}
    for sample in ['os2-initial', 'os2-final', 'os3-initial', 'os3-final']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert set(cases) == labels
        for label, case in cases.items():
            success = label.startswith('selftest-')
            assert case['status'] == 'PASS'
            assert case['result'] == (0 if success else -62 if label == 'CALL-RAM-exhausted' else
                                      -22 if label == 'HALO-invalid' else -12 if label == 'input-FF-error' else -5)
            assert case['entries'].count('cs40l26_remove') == int(not success)
            assert case['remove_body'] == 'original instructions; kernel teardown services are fixtures'
            assert case['fw_loaded'] == int(label != 'CALL-RAM-exhausted')
            assert len(case['raw_writes']) == 68
            assert len(case['requests']) == len(case['releases']) == 6
            assert case['input_registered_flag'] == int(label == 'MFD-error' or success)
            assert case['workqueue_spec'] == [dict(name='vibe_workqueue', flags=0xa0012, max_active=1)]
            assert not case['completion_services_called']
            bulk_count = (0 if label in ['CALL-RAM-exhausted', 'active-sequence-read-error'] else
                          2 if label == 'HALO-invalid' else 23 if label == 'runtime-resume-error' else 25)
            assert len(case['bulk_writes']) == bulk_count
            if label == 'CALL-RAM-exhausted':
                assert len([w for w in case['writes'] if w['address'] == 0x2800ff8]) == 20
                assert len(case['sleeps']) == 22 and not case['debugfs'] and not case['raw_reads']
            else:
                assert case['debugfs'] == [0x4000000]
                assert len(case['raw_reads']) == (1 if label == 'active-sequence-read-error' else 2)
                assert all(r['fixture'] == 'all-FF-immediate-terminator' for r in case['raw_reads'])
            input_case = label in ['input-FF-error', 'input-register-error', 'MFD-error'] or success
            assert ('cs40l26_input_init' in case['entries']) == input_case
            assert case['threads'] == case['virqs'] == (27 if input_case or label == 'IRQ-last-thread-error' else 0)
            if input_case:
                assert case['capabilities'] == [[21, 81], [21, 93], [21, 90], [21, 96]]
            if label == 'MFD-error':
                assert [s['name'] for s in case['input_services']][-2:] == [
                    'sysfs_remove_groups', 'input_unregister_device']
            if success:
                assert case['workers'] == ['cs40l26_upload_worker', 'cs40l26_vibe_start_worker', 'cs40l26_erase_worker']
                assert len(case['effects']) == 1
                effect = bytes.fromhex(case['effects'][0])
                assert len(effect) == 48 and effect[:4] == bytes.fromhex('51000000')
                assert effect[10:12] == bytes.fromhex('6400') and effect[16:22] == bytes.fromhex('5a0008002d00')
                assert len(case['worker_writes']) == 5
                assert [(w['address'], w['value']) for w in case['worker_writes']] == [
                    (0x280701c, 25), (0x2807014, 125), (0x2807018, 45),
                    (0x2802134, 100), (0x28059f0, 0)]
                assert case['worker_mailbox'] == [dict(command=0x1800081,
                    result=-5 if label == 'selftest-mailbox-error' else 0)]
                assert all(w['upload_status'] == w['erase_status'] == 0 for w in case['work_results'])
            else:
                assert not case['effects'] and not case['workers'] and not case['worker_mailbox']
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    check, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS2-OS3-haptics-config-input-selftest']
    assert check['count'] == 44 and check['evidence_sha256'] == sha(path)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    assert sha(Path(index['image'])) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, count=44, production_change=False,
                  physical_vibration='unverified', image_sha256=index['image_sha256'],
                  evidence_sha256=sha(path), audit_script_sha256=sha(Path(__file__)),
                  documents={name: sha(ROOT / name) for name in [
                      'ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'simulation-report.md',
                      'simulation-report.json', 'docs/archive/haptics/HAPTICS-FIRMWARE-EMULATION.md']})
    (ROOT / 'logs/haptics-legacy-config-input-join-audit.json').write_text(
        json.dumps(result, indent=2) + '\n')
    print('PASS: 44 original legacy config/input/self-test paths; no DSP or motor claim')


if __name__ == '__main__':
    main()
