#!/usr/bin/env python3
"""Bind sparse tar restoration, codec regressions, patch0092 and the clean image."""
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
    assert image.name == 'recovery-dijun-unified-sparse-restore.img'
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
    assert patch['file'] == '0092-libtar-sparse-restore.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    loaded, reports = {}, {}
    for suffix, count, failures in [('restore', 40, 0), ('negative', 10, 9), ('pipeline', 50, 0)]:
        path = ROOT / f'logs/archive-sparse-{suffix}-delivery.json'
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
    for name, digest in loaded['negative']['sources'].items():
        source = Path(name)
        if source.is_relative_to('logs/archive-sparse-old/libtar'):
            relative = source.relative_to('logs/archive-sparse-old/libtar')
            if str(relative) != 'extract.c':
                assert sha(ANDROID / 'bootable/recovery/libtar' / relative) == digest
    old = {c['case']: c for c in loaded['negative']['cases']}
    assert [n for n, c in old.items() if c['status'] == 'PASS'] == ['sparse-empty']
    current = {c['case']: c for c in loaded['restore']['cases']}
    for name in old:
        assert current[name]['returncode'] == 0
        assert ('failure propagated' if name.endswith('error') else 'sparse logical progress=') in current[name]['output']
    pipeline = {c['case']: c for c in loaded['pipeline']['cases']}
    for kind in ['plain', 'gzip', 'aes', 'both']:
        assert 'PASS codec sparse restored_blocks=' in pipeline[kind + '-sparse']['output']
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-mtp-staging-identity.img')
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
                  limits='Host files and codecs, ASan/UBSan; fscrypt/UI/mount fixtures. '
                         'Zero runs recreated, not original extent topology or a sparse tar format. '
                         'No ARM64 restore, physical filesystem, full GUI/manager or power-loss validation.')
    (ROOT / 'logs/archive-sparse-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0092; restore40; negative9/10; codec50; clean image and six profiles')


if __name__ == '__main__':
    main()
