#!/usr/bin/env python3
"""Verify the original CUSTOM callback join without asserting physical output."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/haptics-custom-callback-review.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 12
    for group in ['sources', 'tests', 'emulator_files']:
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    expected = {'stock-long31': 0, 'copy-residual1': -14, 'copy-residual4': -14,
                'allocation-failure': -12, 'user-range-rejected': -14, 'outside43': -22}
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert set(cases) == set(expected)
        for label, result in expected.items():
            case = cases[label]
            assert case['status'] == 'PASS' and case['result'] == result
            assert case['stock_wave_count'] == 43 and len(case['allocations']) == 1
            assert case['frees'] == case['allocations']
            assert len(case['copies']) == int(label not in ['allocation-failure', 'user-range-rejected'])
            if label in ['copy-residual1', 'copy-residual4', 'user-range-rejected']:
                length = 1 if label == 'copy-residual1' else 4
                assert len(case['zero_fills']) == 1 and case['zero_fills'][0]['length'] == length
                assert case['freed_custom_bytes'] == ['00001f00' if length == 1 else '00000000']
            else:
                assert not case['zero_fills']
            if label == 'stock-long31':
                assert case['mailbox'] == [dict(command=0x100001f, result=0)]
                assert [w['value'] for w in case['writes']] == [0, 0]
                assert case['workers'] == ['cs40l26_upload_worker', 'cs40l26_vibe_start_worker']
            else:
                assert not case['mailbox'] and not case['writes']
                assert case['workers'] == (['cs40l26_upload_worker'] if label == 'outside43' else [])
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    check, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-custom-callback']
    assert check['count'] == 12 and check['evidence_sha256'] == sha(path)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    assert sha(Path(index['image'])) == index['image_sha256']
    out = dict(status='PASS', scope=__doc__, cases=12, production_change=False,
               physical_vibration='unverified', image_sha256=index['image_sha256'],
               evidence_sha256=sha(path), documents={n: sha(ROOT / n) for n in [
                   'ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'simulation-report.md',
                   'simulation-report.json', 'docs/HAPTICS-ADAPTATION.md']},
               audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-custom-callback-review-audit.json').write_text(json.dumps(out, indent=2) + '\n')
    print('PASS: 12 original callback/copy-boundary joins; no DSP or motor result')


if __name__ == '__main__':
    main()
