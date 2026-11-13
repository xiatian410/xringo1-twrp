#!/usr/bin/env python3
"""Bind directory-relative upload publication and cleanup to patch0115 and a clean image."""
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
    assert image.name == 'recovery-dijun-unified-mtp-parent-identity.img'
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
    assert patch['file'] == '0115-mtp-upload-parent-directory.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports, loaded = {}, {}
    for suffix, count, failures in [('objects', 247, 0), ('old', 6, 6)]:
        path = ROOT / ('logs/mtp-parent-identity.json' if suffix == 'objects' else f'logs/mtp-parent-identity-{suffix}.json')
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
    expected = {'upload-parent-' + kind + '-' + mode for kind in ['new', 'overwrite']
                for mode in ['directory', 'symlink', 'moved-inode']}
    assert {c['case'] for c in loaded['old']['cases']} == expected
    for case in loaded['old']['cases']:
        assert 'parent_replacement_rejected=1 replacement_untouched=1 original_directory_cleanup=1' in current[case['case']]['output']
    for name, digest in loaded['old']['sources'].items():
        relative = Path(name).relative_to('logs/mtp-parent-identity-before')
        now = ANDROID / 'bootable/recovery' / relative
        if str(relative) not in ['mtp/MtpServer.cpp']:
            assert sha(now) == digest, relative
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-mtp-active-identity.img')
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
                  limits='Host server/database/inotify and ordinary files; USB/properties fixtures. '
                         'No ARM64 MTP/Windows/power loss or cross-restart ownership recovery. '
                         'Directory fd anchors publish, cleanup and sync after creation. Path-based staging creation still has a pre-create race; check-to-use filename race and in-place edits remain, with no cross-restart recovery or full device integration.')
    (ROOT / 'logs/mtp-parent-identity-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0115; objects247; old6/6 failures; clean image and six profiles')


if __name__ == '__main__':
    main()
