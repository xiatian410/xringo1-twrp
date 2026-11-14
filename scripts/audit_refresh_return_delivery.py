#!/usr/bin/env python3
"""Bind the backup refresh return regression to patch0139 and its clean image.

Checks only this route fix, source provenance and unchanged packaged profiles.
No hardware claims, broad functional reruns or unrelated resolved-item checks.
"""
import hashlib
import json
import os
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def image_entries(path):
    data = Path(path).read_bytes()
    header, parts = boot_parts(data)
    rows = ramdisk_entries(parts['ramdisk'])
    result = {row[0]: row for row in rows}
    assert len(result) == len(rows)
    return data, header, result


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-refresh-return.img'
    previous = ROOT/'imgs/built/recovery-dijun-unified-cli-results.img'
    provenance = read(image.with_name(image.stem+'-sources.json'))
    before_provenance = read(previous.with_name(previous.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    assert len(provenance['files']) == 877
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    for name, target in provenance['symlinks'].items():
        assert os.readlink(name) == target, name
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    text = build.read_text()
    assert text.count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in text
    spec = read(TREE/'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0139-backup-refresh-return-route.patch'
    assert sha(TREE/'patches'/patch['file']) == patch['sha256']

    reports = {}
    for suffix in ['current', 'old']:
        path = ROOT/f'logs/refresh-return-{suffix}.json'
        report = read(path)
        assert len(report['cases']) == 6
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        expected_failures = {'home-first', 'home-precompleted', 'home-custom-name', 'home-repeated'}
        for case in report['cases']:
            failed = suffix == 'old' and case['case'] in expected_failures
            assert case['status'] == ('FAIL' if failed else 'PASS'), case
            if failed:
                assert 'RETURN_BROKEN' in case['output'] and 'stale_progress=1 worker_idle=1' in case['output']
            else:
                assert 'complete_route_restored=1 no_stale_progress=1 worker_idle=1' in case['output']
            assert 'runtime error:' not in case['output']
        if suffix == 'old':
            source = next(p for p in report['sources'] if p.endswith('dijun-refresh-return-before.cpp'))
            assert report['sources'][source] == before_provenance['files'][str(ANDROID/'bootable/recovery/gui2/gui2.cpp')]
        reports[suffix] = dict(sha256=sha(path), cases=6,
                               failures=sum(c['status']=='FAIL' for c in report['cases']))

    old_data, old_header, old = image_entries(previous)
    data, header, entries = image_entries(image)
    assert len(data) == len(old_data) == 104857600
    assert header['header_version'] == 4 and header['kernel_size'] == 0
    assert header['header_without_ramdisk_size_sha256'] == old_header['header_without_ramdisk_size_sha256']
    changed = sorted(name for name in set(old)|set(entries)
                     if old.get(name) != entries.get(name))
    # Cpio metadata may contain build timestamps. Compare payloads independently.
    payload_changes = sorted(name for name in set(old)|set(entries)
                             if (old[name][-1] if name in old else None) !=
                                (entries[name][-1] if name in entries else None))
    assert payload_changes == ['prop.default', 'ramdisk-files.sha256sum', 'system/lib64/libgui2.so'], payload_changes
    staged = ANDROID/'out/target/product/O1_asic/recovery/root'
    for name in ['system/lib64/libgui2.so', 'system/bin/recovery', 'system/bin/twrp']:
        assert entries[name][-1] == (staged/name).read_bytes(), name
    profiles = {}
    blobs = set()
    for path in sorted((TREE/'profiles').glob('*/profile.json')):
        profile = read(path)
        name = path.parent.name
        for asset in ['selection.conf', 'crypto.prop', 'modules.plan', 'runtime-files.list']:
            assert entries[f'system/etc/dijun/profiles/{name}/{asset}'][-1] == (path.parent/asset).read_bytes()
        for item in profile['assets'].values():
            digest = item['sha256']; blobs.add(digest)
            blob = entries['system/etc/dijun/blobs/'+digest][-1]
            assert hashlib.sha256(blob).hexdigest() == digest and len(blob) == item['size']
        profiles[name] = dict(kernel_release=profile['kernel_release'],
                              crypto_identity=profile['crypto_identity'], asset_count=len(profile['assets']))
    assert len(profiles) == 6 and len(blobs) == 78
    for path in (TREE/'profiles/runtime').glob('*.sh'):
        assert entries['system/bin/'+path.name][-1] == path.read_bytes()
    package = dict(image=str(image), sha256=sha(image), size=len(data),
                   ramdisk_size=header['ramdisk_size'], profiles=profiles, unique_blobs=len(blobs),
                   payload_changes=payload_changes, scope=__doc__)
    image.with_suffix('.json').write_text(json.dumps(package, indent=2)+'\n')
    result = dict(status='PASS', image=str(image), image_sha256=sha(image),
                  production_patch=patch['file'], production_sources=len(provenance['files']),
                  jobs=provenance['jobs'], reports=reports, payload_changes=payload_changes,
                  cpio_entries_changed_including_metadata=len(changed), profiles=len(profiles),
                  hardware_testing=False, scope=__doc__,
                  limits='Original selected route/callback/worker and LVGL progress/page-host paths; backup/storage bodies, scan, settings, fonts and display are fixtures. No hardware reproduction, actual mount/backup or DRM diagnosis.')
    (ROOT/'logs/refresh-return-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
