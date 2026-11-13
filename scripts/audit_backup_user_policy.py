#!/usr/bin/env python3
"""Bind per-attempt locked-user backup exclusions to regressions and a clean image."""
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
    assert image.name == 'recovery-dijun-unified-backup-user-policy.img'
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
    assert patch['file'] == '0113-backup-user-attempt-policy.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    assert sha(ANDROID / 'bootable/recovery/partition.cpp') == spec['result_files']['partition.cpp']
    loaded, reports = {}, {}
    names = {'locked-base', 'unlock-next', 'failed-retry', 'relock', 'mixed-users',
             'mount-failed', 'non-data', 'non-fbe'}
    for stem, failures in [('backup-user-policy', 0), ('backup-user-policy-old', 5)]:
        path = ROOT / f'logs/{stem}.json'
        report = read(path)
        assert len(report['cases']) == 8
        assert {c['case'] for c in report['cases']} == names
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        assert report['status'] == ('FAIL' if failures else 'PASS')
        for name, digest in report['sources'].items():
            assert sha(ROOT / name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        loaded[stem] = report
        reports[stem] = dict(sha256=sha(path), cases=8, failures=failures)
    harness = str(ROOT / 'tests/backup_user_policy_test.py')
    assert loaded['backup-user-policy']['sources'][harness] == loaded['backup-user-policy-old']['sources'][harness]
    assert {c['case'] for c in loaded['backup-user-policy-old']['cases'] if c['status'] == 'FAIL'} == {
        'locked-base', 'unlock-next', 'failed-retry', 'relock', 'mixed-users'}
    for case in loaded['backup-user-policy']['cases']:
        assert 'current_user_selection=1 base_policy_preserved=1' in case['output']
    previous = ROOT / 'imgs/built/recovery-dijun-unified-exclusion-union.img'
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
                  limits='Original BackupTar and exclusion methods with real private files under '
                         'ASan/UBSan. Mount/users/DataManager/console and tar creation are fixtures. '
                         'No real unlock, archive/fork/codec, manager/GUI, device or current-image OTA. '
                         'Local policy lifetime additionally inspected against synchronous createTarFork/Wait.')
    (ROOT / 'logs/backup-user-policy-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0113; policy8; old5/8 failures; clean image/six profiles')


if __name__ == '__main__':
    main()
