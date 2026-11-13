#!/usr/bin/env python3
"""Bind application user xattrs across codecs/workers, patch0095 and the clean image."""
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
    assert image.name == 'recovery-dijun-unified-user-xattrs.img'
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
    assert patch['file'] == '0095-archive-application-user-xattrs.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    loaded, reports = {}, {}
    paths = {
        'restore': ('logs/archive-xattr-restore-delivery.json', 64, 0),
        'negative': ('logs/archive-xattr-negative.json', 14, 10),
        'pipeline': ('logs/archive-xattr-pipeline-delivery.json', 104, 0),
        'pipeline-negative': ('logs/archive-xattr-pipeline-negative.json', 20, 20),
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
    assert current['xattr-file']['gnu_tar_readback'] == 'PASS binary3000/empty/no leakage'
    for case in loaded['negative']['cases']:
        assert current[case['case']]['status'] == 'PASS'
    pipeline = {c['case']: c for c in loaded['pipeline']['cases']}
    for case in loaded['pipeline-negative']['cases']:
        assert case['status'] == 'FAIL'
        now = pipeline[case['case']]
        assert now['status'] == 'PASS'
        marker = ('read failure rejects backup publication' if case['case'].endswith('-read-error') else
                  'failure reaches restore parent' if case['case'].endswith('-write-error') else
                  'binary/empty/directory/isolation through codec/workers')
        assert marker in now['output']
    source = (ANDROID / 'bootable/recovery/twrpTar.cpp').read_text()
    assert source.count('TAR_STORE_ANDROID_USER_XATTR | TAR_STORE_USER_XATTR') == 2
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-directory-times.img')
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
                  limits='Actual host ordinary-file xattrs/codecs/fork/workers and GNU tar independent readback; '
                         'UI/fscrypt/mount/security providers remain fixtures. Application user namespace only, '
                         'excluding Android user.default and all user.inode_* references; no kernel security '
                         'namespace, arbitrary ACL/trusted attributes, ARM64 restore/full GUI/manager or power-loss proof. '
                         'New large PAX headers require a compatible reader; errors do not roll back restored files.')
    (ROOT / 'logs/archive-xattr-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0095; libtar64/GNU readback; old10/14; codec104; old20/20; clean image/six profiles')


if __name__ == '__main__':
    main()
