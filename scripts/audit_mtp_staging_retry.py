#!/usr/bin/env python3
"""Bind failed-cleanup upload retry to its pinned patch and clean-built MTP library."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-mtp-staging-retry.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == index['image_sha256']
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = Path(provenance['build_log'])
    if not build.is_absolute():
        build = ROOT / build
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    patch = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']['patches'][-1]
    assert patch['file'] == '0081-mtp-staging-retry.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports = {}
    for suffix, count, failures in [('objects', 116, 0), ('negative', 2, 1), ('transfers', 48, 0)]:
        path = ROOT / ('logs/mtp-staging-retry-' + suffix + '.json')
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        for group in ['sources', 'test_sources', 'shared_sources']:
            for name, digest in report.get(group, {}).items():
                source = Path(name)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, name
        reports[suffix] = dict(sha256=sha(path), cases=count, failures=failures)
    current = read(ROOT / 'logs/mtp-staging-retry-objects.json')
    old = read(ROOT / 'logs/mtp-staging-retry-negative.json')
    assert current['test_sources'] == old['test_sources']
    for name in ['staging-cleanup-retry', 'staging-cleanup-new']:
        case = next(c for c in current['cases'] if c['case'] == name)
        assert 'retry_after_two_cleanup_failures=1 hidden_orphans=2 user_prefix_visible=1' in case['output']
    failed = [c for c in old['cases'] if c['status'] == 'FAIL']
    assert failed[0]['case'] == 'staging-cleanup-retry'
    assert 'leftovers.size()==static_cast<size_t>(round+1)' in failed[0]['output']
    def entries(path):
        return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-snapuserd-eof.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libtwrpmtp-ffs.so'], changed
    library = 'system/lib64/libtwrpmtp-ffs.so'
    assert after[library] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / library).read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    for suffix, result in reports.items():
        item = next(c for c in index['additional_checks'] if c['evidence'] == 'logs/mtp-staging-retry-' + suffix + '.json')
        assert item['evidence_sha256'] == result['sha256']
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limitations='Host MTP with private files/inotify; USB transport and properties are fixtures. '
                              'No ARM64 MTP/Windows, restart ownership recovery, prefix deletion or hardware test.')
    (ROOT / 'logs/mtp-staging-retry-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: pinned0081 / objects116 / old overwrite retry failure / transfers48 / clean image; six profiles')


if __name__ == '__main__':
    main()
