#!/usr/bin/env python3
"""Bind directory-upload metadata/completion checks to the clean candidate.

Native production MTP server/database with real private files and inotify;
USB transport, properties and hardware remain explicit fixtures.
"""
import hashlib
import json
from pathlib import Path

from sync_device_tree import ANDROID, ROOT, TREE, manifest
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def bindings(files):
    for name, digest in files.items():
        assert sha(ROOT / name) == digest, name


def main():
    index = read('simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-mtp-directory.img'
    assert sha(image) == index['image_sha256']
    sources = read(image.with_name(image.stem + '-sources.json'))
    assert sources['image_sha256'] == index['image_sha256']
    bindings(sources['files'])
    assert len(sources['files']) == 765 and sources['jobs'] == 30
    assert sha(ROOT / sources['build_log']) == sources['build_log_sha256']
    build = (ROOT / sources['build_log']).read_text()
    assert build.count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (
        ROOT / 'logs/mtp-directory-final-source.log').read_text()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == index['image_sha256'] and len(package['profiles']) == 6
    paths = ['logs/mtp-directory-' + n + '.json' for n in [
        'objects', 'before', 'transfers', 'profile-runtime', 'module-state']]
    reports = [read(p) for p in paths]
    for path, report in zip(paths, reports):
        assert report['status'] == ('FAIL' if path.endswith('-before.json') else 'PASS')
        for key in ['sources', 'test_sources', 'shared_sources']:
            bindings(report.get(key, {}))
        assert any(c.get('evidence') == path and c['evidence_sha256'] == sha(ROOT / path)
                   for c in index['additional_checks']), path
    objects, before, transfers, profile, modules = reports
    assert len(objects['cases']) == 110 and len(transfers['cases']) == 48
    assert len(before['cases']) == 16
    assert sum(c['status'] == 'FAIL' for c in before['cases']) == 14
    for report in [objects, transfers]:
        assert all(c['status'] == 'PASS' for c in report['cases'])
    assert objects['test_sources'] == before['test_sources']
    current = {c['case']: c for c in objects['cases']}
    for case in before['cases']:
        assert case['case'] in current and current[case['case']]['status'] == 'PASS'
    for report, groups, calls in [(profile, 9, 102), (modules, 4, 24)]:
        assert report['image_sha256'] == index['image_sha256']
        assert report['tests_run'] == groups and len(report['cases']) == calls
        assert all(c['actual'] == c['expected'] for c in report['cases'])
    # Inspect actual delivered ELF bytes, not just the source patch.
    def entries(path):
        _, parts = boot_parts(Path(path).read_bytes())
        return {e[0]: e[-1] for e in ramdisk_entries(parts['ramdisk'])}
    previous = entries(ROOT / 'imgs/built/recovery-dijun-unified-sideload-reboot.img')
    latest = entries(image)
    changed = [p for p in latest if p.endswith('.so') or p == 'system/bin/recovery'
               if latest[p] != previous.get(p)]
    assert changed == ['system/lib64/libtwrpmtp-ffs.so'], changed
    for p in ['system/bin/recovery', 'system/lib64/libtwrpmtp-ffs.so']:
        assert latest[p] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / p).read_bytes()
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=index['image_sha256'],
                  production_sources=765, objects=110, new_cases=16, old_failures=14,
                  transfers=48, profile_groups=9, module_groups=4,
                  changed_core_binaries=changed,
                  evidence={p: sha(ROOT / p) for p in paths},
                  audit_source_sha256=sha(Path(__file__)),
                  limitations='No real USB/Windows, ARM64 MTP execution, power loss, '
                  'cross-restart staging recovery or post-child directory timestamp restoration.')
    (ROOT / 'logs/mtp-directory-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: MTP objects110/new16/old14 failures/transfers48;765 sources;six profiles;runtime9/module4. Full12 open.')


if __name__ == '__main__':
    main()
