#!/usr/bin/env python3
"""Bind offline format mount guards, finite regressions and clean Recovery image."""
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
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert image.name == 'recovery-dijun-unified-format-unmounted.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    assert log.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in log.read_text()
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    spec = read(TREE/'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0086-offline-format-mount-guards.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    loaded = {}
    sizes = {'negative':15, 'current':15, 'builtin-negative':1, 'builtin-current':1,
             'transition-regression':25, 'tool-regression':6, 'repair-regression':9}
    for suffix, size in sizes.items():
        path = ROOT/('logs/format-mounted-'+suffix+'.json')
        report = read(path)
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        cases = {c.get('case', c.get('name')): c for c in report['cases']}
        assert len(cases) == size
        if suffix.endswith('negative'):
            assert report['status'] == 'FAIL'
            expected = {'ext-retained'} if suffix=='builtin-negative' else {
                fs+'-retained' for fs in ['ext','ext2','ext3','fat','exfat','f2fs','ntfs']}
            assert {n for n,c in cases.items() if c['status']=='FAIL'} == expected
        else:
            assert report['status'] == 'PASS'
            assert all(c['status']=='PASS' for c in cases.values())
        if suffix=='builtin-current':
            assert '-DUSE_EXT4' in report['compile_command']
        if suffix=='tool-regression':
            assert report['image_sha256'] == sha(image)
            assert all(all(c['checks'].values()) for c in cases.values())
        check = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        reports[suffix] = dict(sha256=sha(path), cases=len(cases),
                               failures=sum(c['status']=='FAIL' for c in cases.values()))
        loaded[suffix] = report
    for current_label,old_label in [('current','negative'),('builtin-current','builtin-negative')]:
        current, old = loaded[current_label]['sources'], loaded[old_label]['sources']
        assert {p:d for p,d in current.items() if p!=str(ANDROID/'bootable/recovery/partition.cpp')} == {
            p:d for p,d in old.items() if Path(p).resolve()!=ROOT/'logs/format-mounted-before/partition.cpp'}
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-repair-unmounted.img')
    after = entries(image)
    changed = sorted(n for n in set(before)|set(after) if before.get(n)!=after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    assert after['system/bin/recovery'] == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    profiles = sorted(p.parent.name for p in (TREE/'profiles').glob('*/profile.json'))
    assert len(profiles) == 6
    for profile in profiles:
        for name in ['selection.conf', 'runtime-files.list', 'crypto.prop', 'modules.plan']:
            assert after[f'system/etc/dijun/profiles/{profile}/{name}'] == (TREE/'profiles'/profile/name).read_bytes()
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS', image_sha256=sha(image), production_sources=len(provenance['files']),
                  jobs=provenance['jobs'], reports=reports, changed_ramdisk_entries=changed,
                  profiles_unchanged=profiles, scope=__doc__, limitations='Original Wipe dispatch/helpers, manager/backend '
                  'run with mounted-state/unmount/device/command fixtures; optional USE_EXT4 compile check. Tool regressions execute ARM64 image tools '
                  'on private ordinary files under QEMU; no real mount, full GUI, fscrypt or hardware validation.')
    (ROOT/'logs/format-mounted-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: pinned0086 / 15 mount cases+USE_EXT4 / old seven+one failures / regressions / clean804')


if __name__ == '__main__':
    main()
