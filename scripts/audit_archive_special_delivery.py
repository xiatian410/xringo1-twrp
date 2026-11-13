#!/usr/bin/env python3
"""Bind special-file creation errors across codecs/fork, patch0097 and the clean image."""
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
    return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}


def main():
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-special-file-errors.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT / provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0097-restore-special-file-errors.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    loaded, reports = {}, {}
    paths = {
        'restore': ('logs/archive-special-restore.json', 89, 0),
        'negative': ('logs/archive-special-negative.json', 10, 8),
        'pipeline': ('logs/archive-special-pipeline.json', 124, 0),
        'pipeline-negative': ('logs/archive-special-pipeline-negative.json', 8, 8),
    }
    for suffix, (name, count, failures) in paths.items():
        path = ROOT / name
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        for group in ['sources', 'shared_sources', 'tests', 'test_sources']:
            for name, digest in report.get(group, {}).items():
                source = Path(name)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        loaded[suffix] = report
        reports[suffix] = dict(sha256=sha(path), cases=count, failures=failures)
    assert loaded['restore']['tests'] == loaded['negative']['tests']
    assert loaded['pipeline']['test_sources'] == loaded['pipeline-negative']['test_sources']
    current = {c['case']: c for c in loaded['restore']['cases']}
    for case in loaded['negative']['cases']:
        assert current[case['case']]['status'] == 'PASS'
    assert sum(c['status']=='FAIL' for c in loaded['negative']['cases']) == 8
    pipeline = {c['case']: c for c in loaded['pipeline']['cases']}
    for case in loaded['pipeline-negative']['cases']:
        assert case['status'] == 'FAIL'
        now = pipeline[case['case']]
        assert now['status'] == 'PASS'
        assert 'without changing existing file' in now['output']
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-restore-paths.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    assert after['system/bin/recovery'] == (ANDROID / 'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Original host libtar/codecs/fork; mknod is intercepted and always fails with '
                         'checked node kind/device number. Direct errno and existing-file metadata are checked. '
                         'FIFO creation is real; no character/block nodes created, no target kernel/node success, '
                         'full GUI/manager/ARM64 restore/power-loss or rollback proof.')
    (ROOT / 'logs/archive-special-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0097; libtar89; old8/10; codec124; old8/8; clean image/six profiles')


if __name__ == '__main__':
    main()
