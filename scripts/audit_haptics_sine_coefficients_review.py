#!/usr/bin/env python3
"""Verify original SINE/coefficient evidence and current delivery identity."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    path = ROOT / 'logs/haptics-sine-coefficients-review.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 46
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            p = Path(name) if name.startswith('/') else ROOT / name
            assert sha(p) == digest, name
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert len(cases) == 23 and all(c['status'] == 'PASS' for c in cases.values())
        for label, values in [('production-80', [20, 125, 64]),
                              ('period-0', [20, 250, 64]),
                              ('period-65535', [20, 100, 64]),
                              ('magnitude--1', [20, 125, 0]),
                              ('magnitude-32767', [20, 125, 255]),
                              ('same-id-retry-after-error', [20, 125, 64])]:
            writes = cases[label]['writes']
            assert [w['address'] for w in writes] == [0x280701c, 0x2807014, 0x2807018]
            assert [w['value'] for w in writes] == values
            assert all(w['result'] == 0 for w in writes)
        failure = cases['first-write-error']
        assert failure['result'] == -5 and failure['slot_id'] == 7
        assert failure['writes'] == [dict(address=0x280701c, value=20, result=-5)]
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    check, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-sine-coefficients']
    assert check['evidence_sha256'] == sha(path) and check['count'] == 46
    assert index['status'] == 'in_progress'
    assert sha(Path(index['image'])) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, cases=46, evidence_sha256=sha(path),
                  image_sha256=index['image_sha256'], production_change=False,
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md',
                             'MAINTENANCE.md', 'simulation-report.md', 'simulation-report.json',
                             'docs/HAPTICS-ADAPTATION.md']}, audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-sine-coefficients-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 46 original SINE/parser/resolver cases; no physical-output conclusion')


if __name__ == '__main__': main()
