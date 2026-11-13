#!/usr/bin/env python3
"""Bind slot HAL failure publication/callbacks, patch0101 and clean-built image."""
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
    assert image.name == 'recovery-dijun-unified-slot-result.img'
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
    assert patch['file'] == '0101-slot-hal-failure-propagation.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    reports = {}
    for stem, count, failures in [('slot-result', 14, 0), ('slot-result-negative', 14, 9),
                                  ('slot-result-storage', 21, 0), ('slot-result-sideload', 20, 0)]:
        path = ROOT / f'logs/{stem}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[stem] = dict(sha256=sha(path), cases=count, failures=failures)
        if stem == 'slot-result-negative':
            assert {c['case'] for c in report['cases'] if c['status'] == 'FAIL'} == {
                'invalid', 'no-service', 'hal-fail', 'backend-hal-fail', 'unsupported',
                'backup-no-service', 'backup-hal-fail', 'reboot-no-service', 'reboot-hal-fail'}
        if stem == 'slot-result-sideload':
            assert next(c for c in report['cases'] if c['case'] == 'storage-gate')['status'] == 'PASS'
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-reboot-storage-guard.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery',
                       'system/lib64/libgui2.so'], changed
    assert after['system/bin/recovery'] == (ANDROID / 'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    assert after['system/lib64/libgui2.so'] == (ANDROID / 'out/target/product/O1_asic/recovery/root/system/lib64/libgui2.so').read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), jobs=provenance['jobs'],
                  reports=reports, changed_ramdisk_entries=changed,
                  limits='Real host storage mutex/threads and original backend/core routing; '
                         'HAL, DataManager, mounts, USB and final reboot are fixtures. '
                         'HAL/state/navigation are doubles; no Binder/TEE cancellation, '
                         'shutdown reservation, full ARM64 GUI or device proof.')
    (ROOT / 'logs/slot-result-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0101; slot14; old9 failures; contention21; sideload20; clean image/six profiles')


if __name__ == '__main__':
    main()
