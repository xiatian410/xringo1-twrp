#!/usr/bin/env python3
"""Audit original-mailbox execution and field ordering evidence, not hardware."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    execution = ROOT / 'logs/haptics-mailbox-error-review.json'
    field = ROOT / 'logs/haptics-playback-field-observation.json'
    report = json.loads(execution.read_text())
    observed = json.loads(field.read_text())
    for group in ('sources', 'tests', 'emulator_files'):
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    for name, digest in observed['files'].items():
        assert sha(ROOT / name) == digest, name
    assert report['status'] == 'PASS' and len(report['cases']) == 32
    for sample in ('os4-current', 'os4-stable'):
        cases = [c for c in report['cases'] if c['sample'] == sample]
        assert len(cases) == 16 and all(c['status'] == 'PASS' for c in cases)
        mailbox = {c['case']: c for c in cases if c['entry'] == 'cs40l26_mailbox_write'}
        assert len(mailbox) == 9
        assert mailbox['first-write-NACK']['result'] == 0
        assert mailbox['write-exhausted']['result'] == -62
        assert len(mailbox['write-exhausted']['writes']) == 20
        assert mailbox['read-exhausted']['result'] == -62
        assert len(mailbox['read-exhausted']['reads']) == 20
        assert mailbox['busy-20-timeout']['result'] == -110
        assert len(mailbox['busy-20-timeout']['reads']) == 20
        for c in cases:
            if c['entry'] == 'cs40l26_vibe_stop_worker':
                assert c['done_logged'] == (c['case'] != 'PM-error')
                if c['case'] == 'write-exhausted':
                    assert len(c['writes']) == 20 and all(w['result'] == -5 for w in c['writes'])
                if c['case'] == 'read-exhausted':
                    assert len(c['reads']) == 20 and all(r['result'] == -5 for r in c['reads'])
    assert len(observed['mailbox_write_faults']) == len(observed['fault_time_windows']) == 5
    assert 'transient_fault_contexts' not in observed
    for window in observed['fault_time_windows']:
        assert window['preceding_stop_request']['line'] < window['fault']['line']
        assert window['fault']['line'] < window['following_stop_worker_done']['line']
        assert [r['message'] for r in window['pm_events_in_window']] == [
            'cs40l26_pm_state_transition: to state = 2',
            'cs40l26_pm_state_transition: done to state = 2',
        ]
        assert 'Timestamp/line-order only' in window['association']
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    for name, path, count in (
        ('stock-ARM64-OS4-haptics-mailbox-error-review', execution, 32),
        ('OS4-real-haptics-playback-observation', field, 43),
    ):
        check, = [c for c in index['checks'] if c['name'] == name]
        assert check['evidence_sha256'] == sha(path) and check['count'] == count
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    assert sha(Path(index['image'])) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, original_execution_cases=32,
                  field_fault_time_windows=5, physical_vibration='unverified',
                  production_change=False, image_sha256=index['image_sha256'],
                  evidence={str(p.relative_to(ROOT)): sha(p) for p in (execution, field)},
                  documents={n: sha(ROOT / n) for n in (
                      'ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'simulation-report.json',
                      'simulation-report.md', 'docs/HAPTICS-ADAPTATION.md')},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-mailbox-error-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 32 original error-path cases and 5 ordering-only field windows; motor unresolved')


if __name__ == '__main__':
    main()
