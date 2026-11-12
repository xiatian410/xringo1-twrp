#!/usr/bin/env python3
"""Bind the six-profile stock probe relocation comparison and task status."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report_path = ROOT / 'logs/haptics-probe-callgraph.json'
    report = json.loads(report_path.read_text())
    assert report['status'] == 'PASS' and len(report['profiles']) == 6
    for group in ['sources', 'tests']:
        for name, digest in report[group].items():
            path = Path(name) if Path(name).is_absolute() else ROOT / name
            assert sha(path) == digest, name
    profiles = {item['sample']: item for item in report['profiles']}
    assert set(profiles) == {'os2-initial', 'os2-final', 'os3-initial', 'os3-final',
                             'os4-current', 'os4-stable'}
    targets = {sample: [call['target'] for call in item['direct_calls']]
               for sample, item in profiles.items()}
    assert targets['os2-initial'] == targets['os2-final'] == targets['os3-initial'] == targets['os3-final']
    assert targets['os4-current'] == targets['os4-stable']
    assert targets['os2-initial'] != targets['os4-current']
    delta = report['conclusions']['os2_os3_to_os4_target_delta']
    assert set(delta['legacy_only']) == set(targets['os2-initial']) - set(targets['os4-current'])
    assert set(delta['os4_only']) == set(targets['os4-current']) - set(targets['os2-initial'])
    assert all(name in targets['os2-initial'] for name in report['conclusions']['legacy_probe_direct_selftest_calls'])
    assert not any(name in targets['os4-current'] for name in report['conclusions']['legacy_probe_direct_selftest_calls'])
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    check, = [item for item in index['checks']
              if item['name'] == 'stock-ELF-six-profile-haptics-probe-relocation-inventory']
    assert check['evidence_sha256'] == sha(report_path) and check['count'] == 6
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    result = dict(status='PASS', scope=__doc__, profiles=6, evidence_sha256=sha(report_path),
                  image_sha256=index['image_sha256'], production_change=False,
                  runtime_execution=False, hardware_result='unverified',
                  documents={name: sha(ROOT / name) for name in
                             ['ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'simulation-report.json',
                              'simulation-report.md', 'docs/HAPTICS-ADAPTATION.md',
                              'docs/archive/haptics/HAPTICS-FIRMWARE-EMULATION.md']},
                  audit_script_sha256=sha(Path(__file__)))
    (ROOT / 'logs/haptics-probe-callgraph-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: six stock probe relocations bound; OS2/OS3 vs OS4 deltas verified; 12 goals remain')


if __name__ == '__main__':
    main()
