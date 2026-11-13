#!/usr/bin/env python3
"""Bind MTP session regression, patch0098 and the clean-built library."""
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
    assert image.name == 'recovery-dijun-unified-mtp-session-boundary.img'
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
    assert patch['file'] == '0098-mtp-session-file-boundary.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    loaded, reports = {}, {}
    for suffix, count, failures in [('objects', 149, 0), ('negative', 23, 22), ('transfers', 48, 0)]:
        path = ROOT / f'logs/mtp-session-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        for group in ['sources', 'shared_sources', 'test_sources']:
            for name, digest in report.get(group, {}).items():
                source = Path(name)
                assert sha(source if source.is_absolute() else ROOT / source) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        loaded[suffix] = report
        reports[suffix] = dict(sha256=sha(path), cases=count, failures=failures)
    assert loaded['objects']['test_sources'] == loaded['negative']['test_sources']
    current = {c['case']: c for c in loaded['objects']['cases']}
    for case in loaded['negative']['cases']:
        assert current[case['case']]['status'] == 'PASS'
        assert (case['status'] == 'PASS') == (case['case'] == 'session-close-pending')
        expected = ('no_data_or_mutation=1' if '-unopened-' in case['case'] or '-closed-' in case['case']
                    else 'pending_released=1' if case['case'] == 'session-close-pending'
                    else 'session_edit_closed=1 prior_writes_preserved=1 reopen_fresh_edit=1')
        assert expected in current[case['case']]['output']
    changed_sources = []
    for name, digest in loaded['negative']['sources'].items():
        relative = Path(name).relative_to('logs/mtp-session-old-source')
        if sha(ANDROID / 'bootable/recovery' / relative) != digest:
            changed_sources.append(str(relative))
    assert sorted(changed_sources) == ['mtp/MtpServer.cpp', 'mtp/MtpServer.h']
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-special-file-errors.img')
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
                  limits='Host production server/database/storage with ordinary files/inotify/threads; '
                         'USB/properties/logging fixtures. No target ARM64 MTP, Windows, actual USB reset, '
                         'full endpoint lifecycle or rollback. Session gating is not authentication.')
    (ROOT / 'logs/mtp-session-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0098; objects149; old22/23 failures; transfers48; clean image/six profiles')


if __name__ == '__main__':
    main()
