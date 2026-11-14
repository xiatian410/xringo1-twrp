#!/usr/bin/env python3
"""Bind battery/Android Secure error propagation to the clean patch0132 image."""
import json
from pathlib import Path
from audit_terminal_reap import entries, read, sha
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-aux-wipe.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    patch = read(TREE/'patches/series.json')['repositories']['bootable/recovery']['patches'][-1]
    assert patch['file'] == '0132-aux-wipe-failure-propagation.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    failures = {'battery-delete-denied', 'battery-lookup-denied', 'battery-directory', 'secure-first-denied', 'secure-first-denied-list', 'secure-all-denied', 'secure-mount-denied'}
    summaries = {}
    for suffix, failed in [('current', set()), ('old', failures)]:
        path = ROOT/f'logs/aux-wipe-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == 15
        assert {c['case'] for c in report['cases'] if c['status']=='FAIL'} == failed
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        cases = {c['case']: c for c in report['cases']}
        if suffix == 'current':
            for name in failures:
                assert 'result=1 done=0' in cases[name]['output']
            for name in failures:
                if name.startswith('secure-'):
                    assert 'first=1 second=0' in cases[name]['output']
        else:
            assert 'result=0 done=1' in cases['secure-first-denied']['output']
            assert 'result=0 done=1' in cases['battery-delete-denied']['output']
            assert 'first=1 second=1' in cases['secure-all-denied']['output']
        summaries[suffix] = dict(cases=15, failures=len(failed), sha256=sha(path))
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-restore-enumeration.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image), production_sources=len(provenance['files']), jobs=provenance['jobs'], reports=summaries, changed_ramdisk_entries=changed,
                  limits='Original manager/partition/RemoveDir/backend run with private chroot files and actual uid65534 permission failures. Mount, settings, console, executor and unrelated routes are fixtures. No phone, full GUI/worker start, fscrypt, concurrency, physical I/O or rollback proof; existing full OTA evidence reused.')
    (ROOT/'logs/aux-wipe-delivery-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'PASS: patch0132; {summaries}; clean image/six profiles; {len(provenance["files"])} source bindings')


if __name__ == '__main__':
    main()
