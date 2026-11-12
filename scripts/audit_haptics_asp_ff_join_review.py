#!/usr/bin/env python3
"""Bind original ASP/FF state evidence to the current delivery; no motor claim."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/haptics-asp-ff-join-review.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 14
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            p = Path(name) if Path(name).is_absolute() else ROOT / name
            assert sha(p) == digest, name
    labels = {'no-ASP', 'ASP-stop-timeout', 'ASP-stop-command-error', 'ASP-start-command-error',
              'ASP-PLL-read-error', 'ASP-invalid-BCLK', 'ASP-clock-update-error'}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert cases.keys() == labels
        for label, case in cases.items():
            assert case['status'] == 'PASS'
            enabled = label != 'no-ASP'
            stale = label in ['ASP-stop-command-error', 'ASP-start-command-error', 'ASP-PLL-read-error']
            assert case['enable_result'] == (None if not enabled else 0 if label == 'ASP-stop-timeout' else -22 if label == 'ASP-invalid-BCLK' else -110 if label == 'ASP-clock-update-error' else -5)
            assert case['before_FF'] == dict(vibe_state=2 if enabled else 0, count=0, asp_active=int(enabled))
            assert case['triggered'] == dict(vibe_state=1, count=1, asp_active=int(enabled))
            assert case['finished'] == dict(vibe_state=0 if not enabled else 1 if stale else 2, count=0, asp_active=int(enabled))
            assert case['FF_mailbox'] == [dict(command=0x1800081, result=0)]
            assert [(c['address'], c['value'], c['result']) for c in case['FF_writes']] == [
                (0x280701c, 20, 0), (0x2807014, 125, 0), (0x2807018, 64, 0), (0x2802134, 80, 0), (0x28059f0, 0, 0)]
            assert case['waveform_complete_counter'] == 0xffffffff
            assert case['ASP_mailbox'] == case['initial_ASP_mailbox'] * 2
            assert len(case['ASP_waits']) == int(label in ['ASP-stop-timeout', 'ASP-invalid-BCLK', 'ASP-clock-update-error'])
            assert all(w['timeout'] == 13 and w['result'] == 0 for w in case['ASP_waits'])
            clock = [(u['mask'], u['value'], u['result']) for u in case['clock_updates']]
            assert clock == ([(0x800, 0x800, 0), (0x7e7, 0x420, 0), (0x800, 0, 0)] if label == 'ASP-stop-timeout' else
                             [(0x800, 0x800, -5)] * 5 if label == 'ASP-clock-update-error' else [])
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-ASP-FF-joined']
    assert entry['count'] == 14 and entry['evidence_sha256'] == sha(path)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = json.loads(image.with_name(image.stem + '-sources.json').read_text())
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(Path(name)) == digest, name
    for name, target in source['symlinks'].items():
        assert str(Path(name).readlink()) == target, name
    result = dict(status='PASS', scope=__doc__, cases=14, production_changed=False,
                  field_vibration='unresolved', evidence_sha256=sha(path),
                  image_sha256=index['image_sha256'], production_source_files=len(source['files']),
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                             'simulation-report.md', 'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md',
                             'docs/archive/haptics/HAPTICS-ASP-FF-STATE.md']}, audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-asp-ff-join-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS:14 original ASP/FF joined cases; current image/source binding; physical vibration unresolved')


if __name__ == '__main__': main()
