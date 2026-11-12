#!/usr/bin/env python3
"""Audit real ARM64 ZIP updater execution with an explicit host exec bridge.

This is offline updater ABI/protocol evidence, not A/B OTA engine, hardware
partition writes, full ARM64 recovery execution or GUI/device acceptance.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    source = read(image.with_name(image.stem+'-sources.json'))
    assert source['image_sha256'] == index['image_sha256']
    for name, digest in source['files'].items():
        assert sha(name) == digest, name
    evidence = ['logs/zip-install-arm64.json', 'logs/zip-arm64-host-regression.json']
    target, host = [read(p) for p in evidence]
    for path, report in zip(evidence, [target, host]):
        assert report['status'] == 'PASS'
        for mapping in ['sources', 'binary_dependencies']:
            for name, digest in report[mapping].items():
                assert sha(name) == digest, name
        assert all(c['status'] == 'PASS' and c['exit'] == 0 for c in report['cases'])
        assert any(c.get('evidence') == path and c['evidence_sha256'] == sha(ROOT/path)
                   for c in index['additional_checks'])
    assert len(target['cases']) == 20 and len(host['cases']) == 36
    assert target['target']['image_sha256'] == index['image_sha256']
    assert set(target['target']['payload_elf_machine'].values()) == {183}
    rows = {c['case']: c for c in target['cases']}
    for row in rows.values():
        assert row['target_checks'] and all(row['target_checks'].values()), row['case']
    for name in ['generic-stored', 'generic-deflated', 'signed-correct',
                 'digest-sha256-good', 'arch-first', 'generic-priority',
                 'generic-no-properties', 'arch-empty-fallback']:
        assert rows[name]['target_checks']['target_main']
        assert rows[name]['target_checks']['progress_pipe']
        assert rows[name]['target_checks']['wait_status']
    assert rows['generic-priority']['result_tag'] == 'generic'
    assert rows['arch-first']['result_tag'] == 'arm64'
    for name in ['target-link-failure', 'target-missing-lib']:
        assert rows[name]['target_checks']['linker_rejection']
    assert rows['target-partial-failure']['target_checks']['partial_effect_preserved']
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=index['image_sha256'],
                  target_cases=20, native_regression_cases=36,
                  production_sources=len(source['files']), production_changes=False,
                  evidence={p:sha(ROOT/p) for p in evidence},
                  audit_source_sha256=sha(Path(__file__)))
    (ROOT/'logs/zip-arm64-chain-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: genuine ARM64 updater20/native ZIP36; unchanged image/source binding. Full12 remains open.')


if __name__ == '__main__':
    main()
