#!/usr/bin/env python3
"""Bind startup media directory lifecycle, regression and clean Recovery image."""
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
    assert image.name == 'recovery-dijun-unified-media-recreate.img'
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
    assert patch['file'] == '0089-media-recreation-lifecycle.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']
    reports = {}
    loaded = {}
    sizes = {'negative':13, 'current':13, 'wipe-regression':16}
    for suffix, size in sizes.items():
        path = ROOT/('logs/media-recreate-'+suffix+'.json')
        report = read(path)
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        cases = {c.get('case', c.get('name')): c for c in report['cases']}
        assert len(cases) == size
        if suffix.endswith('negative'):
            assert report['status'] == 'FAIL'
            expected = {'recreate-'+state for state in ['success','existing','media-denied','internal-denied',
                        'media-file','media-symlink','internal-file','internal-symlink','bind-failed','metadata-failed']}
            assert {n for n,c in cases.items() if c['status']=='FAIL'} == expected
        else:
            assert report['status'] == 'PASS'
            assert all(c['status']=='PASS' for c in cases.values())
        check = next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        reports[suffix] = dict(sha256=sha(path), cases=len(cases),
                               failures=sum(c['status']=='FAIL' for c in cases.values()))
        loaded[suffix] = report
    for current_label,old_label in [('current','negative')]:
        current, old = loaded[current_label]['sources'], loaded[old_label]['sources']
        assert {p:d for p,d in current.items() if p!=str(ANDROID/'bootable/recovery/partition.cpp')} == {
            p:d for p,d in old.items() if Path(p).resolve()!=ROOT/'logs/media-recreate-before/partition.cpp'}
    before = entries(ROOT/'imgs/built/recovery-dijun-unified-andsec-recreate.img')
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
                  profiles_unchanged=profiles, scope=__doc__, limitations='Original RecreateMediaFolder/BindMount plus manager wipe regression '
                  'run on private chroot directories with uid65534 permission failures. Mount/bind, metadata and presentation are explicit fixtures; no real mount, startup init, GUI, fscrypt or hardware validation.')
    (ROOT/'logs/media-recreate-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: pinned0089 / 13 startup media cases / old10 failures / 16 wipe regression / clean807')


if __name__ == '__main__':
    main()
