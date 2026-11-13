#!/usr/bin/env python3
"""Bind patch0083, finite send-error regressions and clean packaged MTP library."""
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
    assert image.name == 'recovery-dijun-unified-mtp-send-errors.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT / provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0083-mtp-send-error-propagation.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports = {}
    expected = {'send-'+kind+'-'+error for kind in ['native', 'compat']
                for error in ['disk-eio', 'disk-short', 'usb-eio', 'usb-short']}
    loaded = {}
    for suffix in ['negative', 'current', 'roundtrip', 'completion-regression']:
        path = ROOT / ('logs/mtp-send-' + suffix + '.json')
        report = read(path)
        for group in ['sources', 'shared_sources', 'test_sources']:
            for name, digest in report[group].items():
                assert sha(name) == digest, name
        cases = {c['case']: c for c in report['cases']}
        if suffix in ['negative', 'current']:
            assert set(cases) == expected
        if suffix == 'negative':
            assert report['status'] == 'FAIL'
            assert cases['send-native-disk-eio']['returncode'] == 124
            assert 'TIMEOUT' in cases['send-native-disk-eio']['output']
            for name, case in cases.items():
                if name == 'send-native-disk-eio':
                    continue
                if name in ['send-compat-disk-eio', 'send-compat-disk-short']:
                    assert case['status'] == 'PASS'
                else:
                    assert case['status'] == 'FAIL'
                    assert 'FAIL: send failure returns -1/EIO' in case['output']
        else:
            assert report['status'] == 'PASS'
            assert all(c['returncode'] == 0 for c in cases.values())
        if suffix == 'current':
            assert all('result=-1 errno=5' in c['output'] for c in cases.values())
        if suffix == 'roundtrip':
            assert 'PASS: native AIO and compat FFS' in cases['roundtrip']['output']
        if suffix == 'completion-regression':
            assert set(cases) == {'completion-eio', 'completion-eagain', 'completion-eintr'}
            assert 'calls=2 result=7' in cases['completion-eintr']['output']
        check = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        reports[suffix] = dict(sha256=sha(path), cases=len(cases),
                               failures=sum(c['status'] == 'FAIL' for c in cases.values()))
        loaded[suffix] = report
    assert loaded['current']['test_sources'] == loaded['negative']['test_sources']
    before_image = ROOT / 'imgs/built/recovery-dijun-unified-mtp-aio-error.img'
    before, after = entries(before_image), entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libtwrpmtp-ffs.so'], changed
    library = 'system/lib64/libtwrpmtp-ffs.so'
    assert after[library] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / library).read_bytes()
    profiles = read(before_image.with_suffix('.json'))['profiles']
    assert len(profiles) == 6
    # All other ramdisk entries, including every profile and runtime asset, are byte-identical.
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', image_sha256=sha(image), production_sources=len(provenance['files']),
                  jobs=provenance['jobs'], reports=reports, changed_ramdisk_entries=changed,
                  profiles_unchanged=list(profiles), scope=__doc__,
                  limitations='Host production sendFile/PosixAsyncIO/Linux AIO with private files/pipes. '
                  'Injected pread64 failure/short read, compat write failure/short write and native '
                  'completion result after real request completion. Does not emulate physical USB '
                  'partial delivery, multi-chunk cancellation, complete server/Reset or Windows.')
    (ROOT / 'logs/mtp-send-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: pinned0083 / eight send errors / six old failures / transport regression / clean image801')


if __name__ == '__main__':
    main()
