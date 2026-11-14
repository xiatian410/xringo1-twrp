#!/usr/bin/env python3
"""Bind upload/partial receive error boundary isolation to patch0123 and a clean image."""
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
    assert image.name == 'recovery-dijun-unified-mtp-receive-boundary.img'
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
    assert patch['file'] == '0123-mtp-receive-error-boundary.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports, loaded = {}, {}
    for suffix, count, failures in [('final', 285, 0), ('old-final', 14, 14)]:
        path = ROOT / f'logs/mtp-receive-tail-{suffix}.json'
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
    assert loaded['final']['test_sources'] == loaded['old-final']['test_sources']
    current = {c['case']: c for c in loaded['final']['cases']}
    expected = {'receive-tail-' + kind + '-' + fault
                for kind in ['new', 'overwrite', 'partial'] for fault in ['enospc', 'eio', 'midwrite', 'terminator']}
    expected |= {'receive-tail-partial-zero', 'receive-tail-partial-write'}
    assert {c['case'] for c in loaded['old-final']['cases']} == expected
    for case in loaded['old-final']['cases']:
        assert 'receive_tail_victim_present=0' in case['output']
        assert 'FAIL ' in case['output'] and 'AddressSanitizer' not in case['output']
    for name in expected:
        assert 'receive_tail_victim_present=1' in current[name]['output']
        assert 'receive_tail_not_dispatched=1 resources_released=1 explicit_reconnect_upload=1 partial_rollback=0' in current[name]['output']
    for name, digest in loaded['old-final']['sources'].items():
        relative = Path(name).relative_to('logs/mtp-receive-tail-before')
        now = ANDROID / 'bootable/recovery' / relative
        assert (sha(now) != digest) == (str(relative) == 'mtp/MtpServer.cpp'), relative
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-mtp-upload-tail.img')
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
                  limits='Host production server/database/storage with real ordinary files/inotify/threads and ASan/UBSan. '
                         'Fourteen command-shaped tail cases cover receive ENOSPC/EIO/midwrite/terminator failures and initial partial writes; USB/properties fixtures. '
                         'No ARM64 MTP/Windows/full endpoint reconnect or full endpoint error recovery/powerloss, pathname race isolation or cross-restart recovery.')
    (ROOT / 'logs/mtp-receive-tail-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0123; objects285; old14/14 unread-tail mutations; clean image/six profiles')



if __name__ == '__main__':
    main()
