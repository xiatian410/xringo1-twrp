#!/usr/bin/env python3
"""Bind patch0084, multi-chunk first-error regressions and clean packaged MTP library."""
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
    assert image.name == 'recovery-dijun-unified-mtp-pipeline.img'
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
    assert patch['file'] == '0084-mtp-pipeline-first-error.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports = {}
    expected = {'send-'+kind+'-pipeline-'+case for kind in ['native', 'compat']
                for case in ['success', 'usb', 'dual']}
    loaded = {}
    for suffix in ['negative', 'current', 'send-regression']:
        path = ROOT / ('logs/mtp-pipeline-' + suffix + '.json')
        report = read(path)
        for group in ['sources', 'shared_sources', 'test_sources']:
            for name, digest in report[group].items():
                source = Path(name)
                if suffix == 'negative' and source == ANDROID / 'bootable/recovery/mtp/MtpFfsCompatHandle.cpp':
                    source = ROOT / 'logs/mtp-pipeline-before/mtp/MtpFfsCompatHandle.cpp'
                assert sha(source) == digest, name
        cases = {c['case']: c for c in report['cases']}
        if suffix != 'send-regression':
            assert set(cases) == expected
        if suffix == 'negative':
            assert report['status'] == 'FAIL'
            failures = [n for n, c in cases.items() if c['status'] == 'FAIL']
            assert failures == ['send-compat-pipeline-dual'], failures
            assert 'FAIL: first USB error retained after pending disk read' in cases[failures[0]]['output']
        else:
            assert report['status'] == 'PASS'
            assert all(c['returncode'] == 0 for c in cases.values())
        if suffix == 'current':
            for name, case in cases.items():
                if name.endswith('success'):
                    assert 'result=0' in case['output']
                else:
                    assert 'result=-1 errno=32 reads=2 completed=2' in case['output']
        if suffix == 'send-regression':
            assert len(cases) == 8
            assert all('result=-1 errno=5' in c['output'] for c in cases.values())
        check = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        reports[suffix] = dict(sha256=sha(path), cases=len(cases),
                               failures=sum(c['status'] == 'FAIL' for c in cases.values()))
        loaded[suffix] = report
    assert loaded['current']['test_sources'] == loaded['negative']['test_sources']
    before_image = ROOT / 'imgs/built/recovery-dijun-unified-mtp-send-errors.img'
    before, after = entries(before_image), entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libtwrpmtp-ffs.so'], changed
    library = 'system/lib64/libtwrpmtp-ffs.so'
    assert after[library] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / library).read_bytes()
    profiles = sorted(p.parent.name for p in (TREE / 'profiles').glob('*/profile.json'))
    for profile in profiles:
        for name in ['selection.conf', 'runtime-files.list', 'crypto.prop', 'modules.plan']:
            assert after[f'system/etc/dijun/profiles/{profile}/{name}'] == (TREE / 'profiles' / profile / name).read_bytes()
    assert len(profiles) == 6
    # All other ramdisk entries, including every profile and runtime asset, are byte-identical.
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', image_sha256=sha(image), production_sources=len(provenance['files']),
                  jobs=provenance['jobs'], reports=reports, changed_ramdisk_entries=changed,
                  profiles_unchanged=list(profiles), scope=__doc__,
                  limitations='Host production sendFile/PosixAsyncIO/AIO; private 7MiB+37 files/pipes, '
                  'host reader thread and second-read gate. No actual FunctionFS cancellation, '
                  'USB partial delivery, full server/Reset or Windows.')
    (ROOT / 'logs/mtp-pipeline-delivery.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: pinned0084 / six pipeline cases / old compat dual failure / eight regressions / clean image802')



if __name__ == '__main__':
    main()
