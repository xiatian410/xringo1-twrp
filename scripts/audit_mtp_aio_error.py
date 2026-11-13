#!/usr/bin/env python3
"""Verify native MTP completion-error bounds fix and clean packaged library."""
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
    assert image.name == 'recovery-dijun-unified-mtp-aio-error.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = Path(provenance['build_log'])
    if not log.is_absolute():
        log = ROOT / log
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0082-mtp-aio-completion-error.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports = {}
    target = ANDROID / 'bootable/recovery/mtp/MtpFfsHandle.cpp'
    for suffix in ['negative', 'current', 'roundtrip']:
        path = ROOT / ('logs/mtp-aio-error-' + suffix + '.json')
        report = read(path)
        for group in ['sources', 'shared_sources', 'test_sources']:
            for name, digest in report[group].items():
                source = Path(name)
                if suffix == 'negative' and source == target:
                    source = ROOT / 'logs/mtp-aio-error-before/mtp/MtpFfsHandle.cpp'
                assert sha(source) == digest, name
        cases = {c['case']: c for c in report['cases']}
        if suffix == 'negative':
            assert set(cases) == {'completion-eio', 'completion-eagain', 'completion-eintr'}
            for name in ['completion-eio', 'completion-eagain']:
                assert cases[name]['status'] == 'FAIL'
                assert 'AddressSanitizer: stack-buffer-overflow' in cases[name]['output']
                assert 'MtpFfsHandle::waitEvents' in cases[name]['output']
            assert cases['completion-eintr']['status'] == 'PASS'
        else:
            assert report['status'] == 'PASS'
            assert all(c['returncode'] == 0 for c in cases.values())
        if suffix == 'current':
            assert set(cases) == {'completion-eio', 'completion-eagain', 'completion-eintr'}
            assert 'calls=2 result=7' in cases['completion-eintr']['output']
            for name in ['completion-eio', 'completion-eagain']:
                assert 'result=-1' in cases[name]['output']
        if suffix == 'roundtrip':
            assert 'PASS: native AIO and compat FFS' in cases['roundtrip']['output']
        check = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        reports[suffix] = dict(sha256=sha(path), cases=len(cases), failures=sum(c['status']=='FAIL' for c in cases.values()))
    current = read(ROOT / 'logs/mtp-aio-error-current.json')
    old = read(ROOT / 'logs/mtp-aio-error-negative.json')
    assert current['test_sources'] == old['test_sources']
    def entries(path):
        return {e[0]: e[-1] for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-mtp-staging-retry.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libtwrpmtp-ffs.so'], changed
    library = 'system/lib64/libtwrpmtp-ffs.so'
    assert after[library] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / library).read_bytes()
    assert len(read(image.with_suffix('.json'))['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', image_sha256=sha(image), production_sources=len(provenance['files']),
                  jobs=provenance['jobs'], reports=reports, changed_ramdisk_entries=changed,
                  scope=__doc__, limitations='Real host AIO/pipes/files with one-shot io_getevents error injection; '
                  'Android properties/logging substituted. No physical FunctionFS/UDC, Windows, '
                  'proof of continuing an unconsumed transfer or full cancel/reset lifecycle.')
    (ROOT / 'logs/mtp-aio-error-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: pinned0082 / EIO,EAGAIN no overflow / EINTR retry / native+compat regression / clean six-profile image')


if __name__ == '__main__':
    main()
