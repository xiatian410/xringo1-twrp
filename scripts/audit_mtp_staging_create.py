#!/usr/bin/env python3
"""Bind directory-relative staging creation to patch0116 and a clean image."""
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
    assert image.name == 'recovery-dijun-unified-mtp-staging-create.img'
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
    assert patch['file'] == '0116-mtp-staging-create-at.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports, loaded = {}, {}
    for suffix, count, failures in [('objects', 257, 0), ('old', 4, 4)]:
        path = ROOT / ('logs/mtp-staging-create.json' if suffix == 'objects' else f'logs/mtp-staging-create-{suffix}.json')
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        for group in ['sources', 'shared_sources', 'test_sources']:
            for name, digest in report.get(group, {}).items():
                source = Path(name)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[suffix] = dict(sha256=sha(path), cases=count, failures=failures)
        loaded[suffix] = report
    assert loaded['objects']['test_sources'] == loaded['old']['test_sources']
    current = {c['case']: c for c in loaded['objects']['cases']}
    expected = {'staging-create-parent-' + kind + '-' + mode
                for kind in ['new', 'overwrite'] for mode in ['directory', 'symlink']}
    assert {c['case'] for c in loaded['old']['cases']} == expected
    for name in expected:
        assert 'create_anchored=1 both_directories_clean=1 replacement_untouched=1' in current[name]['output']
    for kind in ['eintr', 'short', 'error', 'zero', 'collision', 'exhausted']:
        assert 'entropy_and_exclusive_creation=1 user_collision_preserved=1' in current['staging-create-random-' + kind]['output']
    changed_sources = {'mtp/IMtpDatabase.h', 'mtp/MtpServer.cpp', 'mtp/twrp/TwrpMtpDatabase.hpp',
                       'mtp/twrp/TwrpMtpDatabase.cpp', 'mtp/twrp/TwrpMtpStorage.hpp', 'mtp/twrp/TwrpMtpStorage.cpp'}
    observed_changes = set()
    for name, digest in loaded['old']['sources'].items():
        relative = Path(name).relative_to('logs/mtp-staging-create-before')
        now = ANDROID / 'bootable/recovery' / relative
        if sha(now) != digest:
            observed_changes.add(str(relative))
    assert observed_changes == changed_sources, observed_changes
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-mtp-parent-identity.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libtwrpmtp-ffs.so'], changed
    library = 'system/lib64/libtwrpmtp-ffs.so'
    assert after[library] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / library).read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Host server/database/inotify/threads with ASan/UBSan and ordinary files; USB/properties fixtures. '
                         'Creation, publication, cleanup and sync use original parent fd. Random errors and exclusive-name '
                         'collisions are injected at syscall boundaries. No ARM64 MTP/Windows/power loss/cross-restart recovery. '
                         'Check-to-use basename race and in-place modifications remain open.')
    (ROOT / 'logs/mtp-staging-create-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0116; objects257; old4/4 failures; clean image and six profiles')


if __name__ == '__main__':
    main()
