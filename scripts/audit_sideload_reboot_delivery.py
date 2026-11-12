#!/usr/bin/env python3
"""Bind the sideload reboot handoff to the final clean offline image.

Private host process/socket execution only; USB, properties, FUSE, sync and
final reboot are doubles. No actual minadbd/BCB/device reboot acceptance.
"""
import hashlib
import json
import os
from pathlib import Path

from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def bindings(files):
    for path, digest in files.items():
        assert sha(ROOT / path) == digest, path


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    digest = sha(image)
    assert image.name == 'recovery-dijun-unified-sideload-reboot.img'
    assert digest == index['image_sha256']
    source = read(image.with_name(image.stem + '-sources.json'))
    bindings(source['files'])
    assert source['image_sha256'] == digest
    assert len(source['files']) == 764 and source['jobs'] == 30
    for path, target in source['symlinks'].items():
        assert os.readlink(path) == target
    log = ROOT / source['build_log']
    assert sha(log) == source['build_log_sha256']
    text = log.read_text()
    assert text.count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in text
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (
        ROOT / 'logs/sideload-reboot-final-source-recheck.log').read_text()
    metadata = read(image.with_suffix('.json'))
    assert metadata['sha256'] == digest and len(metadata['profiles']) == 6
    evidence = ['logs/' + name + '.json' for name in [
        'sideload-reboot', 'sideload-reboot-before', 'sideload-reboot-lifecycle',
        'sideload-reboot-package-regression', 'sideload-reboot-profile-runtime',
        'sideload-reboot-module-state']]
    reports = [read(p) for p in evidence]
    for path, report in zip(evidence, reports):
        assert report['status'] == ('FAIL' if path.endswith('-before.json') else 'PASS')
        for key in ['sources', 'test_sources', 'tests', 'binary_dependencies']:
            bindings(report.get(key, {}))
        assert any(c.get('evidence') == path and c['evidence_sha256'] == sha(ROOT / path)
                   for c in index['additional_checks']), path
    current, before, lifecycle, package, profile, modules = reports
    assert len(current['cases']) == len(before['cases']) == 19
    assert sum(c['status'] == 'FAIL' for c in before['cases']) == 15
    assert len(lifecycle['cases']) == 33 and len(package['cases']) == 27
    for report in [current, lifecycle, package]:
        assert all(c['status'] == 'PASS' for c in report['cases'])
    for name in ['tests/sideload_reboot_test.py', 'tests/sideload_reboot_test.cpp']:
        assert current['sources'][str(ROOT / name)] == before['sources'][str(ROOT / name)]
    assert current['binary_dependencies'] == before['binary_dependencies']
    for report, groups, calls in [(profile, 9, 102), (modules, 4, 24)]:
        assert report['image_sha256'] == digest and report['tests_run'] == groups
        assert len(report['cases']) == calls
        assert all(c['actual'] == c['expected'] for c in report['cases'])
    inherited = read('logs/nv-mount-policy.json')
    assert inherited['status'] == 'PASS' and len(inherited['cases']) == 26
    bindings(inherited['sources'])
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    documents = ['ADAPTATION-GOALS.md', 'MAINTENANCE.md', 'FEATURE-USAGE.md',
                 'simulation-report.json', 'simulation-report.md', 'README.md',
                 'docs/SIDELOAD-LIFECYCLE.md', 'docs/CURRENT-VALIDATION.json',
                 'AGENTS.md', 'docs/GITHUB-PUBLICATION.md']
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=digest,
                  production_sources=764, reboot_cases=19, old_failed_cases=15,
                  lifecycle_cases=33, package_cases=27,
                  evidence={p: sha(ROOT / p) for p in evidence},
                  documents={p: sha(ROOT / p) for p in documents},
                  audit_source_sha256=sha(Path(__file__)))
    (ROOT / 'logs/sideload-reboot-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: reboot19/old15 failures; lifecycle33/package27;764 sources;six profiles;runtime9/module4. Full12 remains open.')


if __name__ == '__main__':
    main()
