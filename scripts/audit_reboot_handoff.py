#!/usr/bin/env python3
"""Bind accepted-only sideload reboot consumption to patch0120 and delivery."""
import json
from pathlib import Path

from audit_backup_root import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    index = read(ROOT / 'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-reboot-handoff.img'
    assert sha(image) == index['image_sha256']
    source = read(image.with_name(image.stem + '-sources.json'))
    assert source['image_sha256'] == sha(image)
    for name, digest in source['files'].items():
        assert sha(name) == digest, name
    build = ROOT / source['build_log']
    assert sha(build) == source['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    patch = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']['patches'][-1]
    assert patch['file'] == '0120-sideload-reboot-handoff-retry.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports, loaded = {}, {}
    for name, count, failures in [('reboot-handoff-current', 23, 0),
                                  ('reboot-handoff-old', 4, 4),
                                  ('reboot-handoff-lifecycle', 33, 0)]:
        path = ROOT / ('logs/' + name + '.json')
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['exit'] != 0 for c in report['cases']) == failures
        for group in ['sources', 'binary_dependencies']:
            for filename, digest in report[group].items():
                assert sha(filename) == digest, filename
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[name] = dict(sha256=sha(path), cases=count, failures=failures)
        loaded[name] = report
    current = loaded['reboot-handoff-current']
    old = loaded['reboot-handoff-old']
    for name in ['tests/sideload_reboot_test.py', 'tests/sideload_reboot_test.cpp']:
        assert current['sources'][str(ROOT / name)] == old['sources'][str(ROOT / name)]
    rows = {c['case']: c for c in current['cases']}
    for name in ['write-retry', 'unsupported-retry']:
        assert 'handoff_retry_preserved=1' in rows[name]['output']
    assert 'handoff_cancel_preserved=1' in rows['write-cancel']['output']
    assert all('FAIL ' in c['output'] for c in old['cases'])
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-backup-paths.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    assert after['system/bin/recovery'] == (ANDROID / 'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(source['files']), jobs=source['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Native original sideload/GUI handoff with real private processes/socket/epoll/threads. '
                         'USB/properties/FUSE/MTP/DataManager/capabilities/sync/final reboot are fixtures; '
                         'no actual USB/device/BCB/full GUI or shutdown reservation. Historical OTA reused.')
    (ROOT / 'logs/reboot-handoff-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0120; handoff23/lifecycle33; old4/4 fail; clean image/six profiles')


if __name__ == '__main__':
    main()
