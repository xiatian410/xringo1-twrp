#!/usr/bin/env python3
"""Bind the union of overlapping capacity exclusions to finite regressions and a clean image."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def entries(path):
    ramdisk = boot_parts(Path(path).read_bytes())[1]['ramdisk']
    return {e[0]: e[-1] for e in ramdisk_entries(ramdisk)}


def main():
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-exclusion-union.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for path, digest in provenance['files'].items():
        assert sha(path) == digest, path
    build = ROOT / provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert provenance['build_command'] == 'make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0112-backup-exclusion-union.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    assert sha(ANDROID / 'bootable/recovery/exclude.cpp') == spec['result_files']['exclude.cpp']
    reports = {}
    loaded = {}
    for stem, count, failures in [('exclusion-union', 19, 0), ('exclusion-union-old', 19, 7),
                                   ('exclusion-union-codec', 8, 0)]:
        path = ROOT / f'logs/{stem}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        assert report['status'] == ('FAIL' if failures else 'PASS')
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[stem] = dict(sha256=sha(path), cases=count, failures=failures)
        loaded[stem] = report
    harness = str(ROOT / 'tests/exclusion_size_test.py')
    assert loaded['exclusion-union']['sources'][harness] == loaded['exclusion-union-old']['sources'][harness]
    old_failed = {c['case'] for c in loaded['exclusion-union-old']['cases'] if c['status'] == 'FAIL'}
    assert old_failed == {'duplicate-file', 'duplicate-directory', 'nested-parent-first', 'nested-child-first',
                          'nested-three-levels', 'media-user-overlap', 'normalized-duplicate'}
    fixed = {c['case']: c for c in loaded['exclusion-union']['cases']}
    assert 'scanned=40 excluded=4097' in fixed['absolute-file']['output']
    assert 'scanned=4134 excluded=3' in fixed['directory-link']['output']
    assert 'scanned=0 excluded=0' in fixed['cancelled']['output']
    previous = ROOT / 'imgs/built/recovery-dijun-unified-mtp-stream-boundary.img'
    before, after = entries(previous), entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    assert after['system/bin/recovery'] == (ANDROID / 'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Whole exclusion source on private host files under ASan/UBSan; '
                         'logical sizes only, no mounts/manager/fscrypt/device. Eight existing '
                         'tar/pigz/OAES roundtrips include split output. Capacity remains approximate '
                         'on I/O errors, path aliases, allocation and concurrent source changes; '
                         'this does not resolve the DRM refresh stall or validate current-image OTA.')
    (ROOT / 'logs/exclusion-union-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0112; capacity19; old7/19 failures; codec8; clean image/six profiles')


if __name__ == '__main__':
    main()
