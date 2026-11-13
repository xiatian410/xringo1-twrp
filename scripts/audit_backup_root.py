#!/usr/bin/env python3
"""Bind patch0118 root metadata roundtrips and negative controls to delivery."""
import hashlib
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nested-paths', action='store_true')
    paths = parser.parse_args().nested_paths
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == ('recovery-dijun-unified-backup-paths.img' if paths else 'recovery-dijun-unified-backup-root.img')
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
    assert patch['file'] == ('0119-backup-nested-root-paths.patch' if paths else '0118-backup-root-metadata.patch')
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports, loaded = {}, {}
    specs = ([('archive-path-current', 33, 0), ('archive-path-old', 10, 2)] if paths else
             [('archive-root-current', 39, 0), ('archive-root-negative-final', 10, 10)])
    for name, count, failures in specs:
        path = ROOT / ('logs/' + name + '.json')
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['returncode'] != 0 for c in report['cases']) == failures
        for group in ['sources', 'shared_sources', 'test_sources']:
            for filename, digest in report.get(group, {}).items():
                source = Path(filename)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, filename
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[name] = dict(sha256=sha(path), cases=count, failures=failures)
        loaded[name] = report
    current, old = loaded.values()
    assert current['test_sources'] == old['test_sources']
    root = [c for c in current['cases'] if '-root' in c['case']]
    assert len(root) == (28 if paths else 24)
    for case in root:
        expected = ('root metadata read error reaches backup parent' if case['case'].endswith('read-error')
                    else 'root metadata write error reaches restore parent' if case['case'].endswith('write-error')
                    else 'root mode owner time xattr restored once after all volumes/workers')
        assert expected in case['output'], case['case']
    for case in old['cases']:
        if case['returncode']:
            assert 'FAIL ' in case['output'] and 'AddressSanitizer' not in case['output']
    if paths:
        assert {c['case'] for c in old['cases'] if c['returncode']} == {'plain-root-nested', 'gzip-root-nested'}
        for case in current['cases']:
            if '-nested' in case['case']:
                assert 'nested mount root has no duplicated ancestor components' in case['output']
                assert 'byte/mode/symlink/xattr roundtrip' in case['output']
    before = entries(ROOT / ('imgs/built/recovery-dijun-unified-backup-root.img' if paths else
                             'imgs/built/recovery-dijun-unified-size-scan-errors.img'))
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
                  limits='Original host tar/libtar/pigz/OAES and real private-file metadata under ASan/UBSan. '
                         'UI/progress/fscrypt/security providers are explicit fixtures. No real mounts, '
                         'fscrypt root policy installation, ACL/privileged xattrs, full manager/GUI, '
                         'source-concurrency or device powerloss proof. Historical OTA evidence reused.')
    output = 'logs/backup-path-delivery-audit.json' if paths else 'logs/backup-root-delivery-audit.json'
    (ROOT / output).write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0119; paths24 + controls9; old2/10 fail; clean image/six profiles' if paths else
          'PASS: patch0118; root24 + relevant controls15; old10/10 fail; clean image/six profiles')


if __name__ == '__main__':
    main()
