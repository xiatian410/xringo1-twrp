#!/usr/bin/env python3
"""Validate the bounded original-service routing evidence, not motor operation."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report_path = ROOT / 'logs/haptics-service-route-review.json'
    report = json.loads(report_path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 20
    for group in ['sources', 'tests', 'emulator_files']:
        assert report[group]
        for name, digest in report[group].items():
            assert sha(ROOT / name) == digest, name
    for sample in ['os4-current', 'os4-stable']:
        cases = {c['case']: c for c in report['cases'] if c['sample'] == sample}
        assert len(cases) == 10 and all(c['status'] == 'PASS' for c in cases.values())
        for duration in [80, 300]:
            calls = cases['ordinary-on-' + str(duration)]['calls']
            assert [c['call'] for c in calls] == ['write', 'upload', 'write', 'AStatus_newOk']
            assert calls[1]['custom'] == '00001f00'
        writes = lambda label: [c for c in cases[label]['calls'] if c['call'] == 'mixer_ctl_set_value']
        assert [(c['control'], c['value']) for c in writes('wave31')] == [
            ('SVC Algo Enable', 0), ('Haptics Source', 0), ('Haptics Source', 1)]
        assert all(c['result'] == -5 for c in writes('set-error'))
        assert [c['control'] for c in writes('retry-after-set-error')] == ['Haptics Source'] * 2
        assert not writes('missing-control')
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    entry, = [c for c in index['checks'] if c['name'] == 'stock-ARM64-OS4-haptics-service-route-review']
    assert entry['evidence_sha256'] == sha(report_path) and entry['count'] == 20
    assert index['status'] == 'in_progress'
    image = ROOT / index['image']
    assert sha(image) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, cases=20,
                  evidence_sha256=sha(report_path), image_sha256=sha(image),
                  production_change=False,
                  documents={n: sha(ROOT / n) for n in ['ADAPTATION-GOALS.md',
                             'MAINTENANCE.md', 'simulation-report.md', 'simulation-report.json',
                             'docs/HAPTICS-ADAPTATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-service-route-review-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 20 service cases/current source hashes/index/image; vibration remains unresolved')


if __name__ == '__main__': main()
