#!/usr/bin/env python3
"""Bind patch0109 worker lifetime ordering to finite tests and clean image."""
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
    assert image.name == 'recovery-dijun-unified-reboot-worker-drain.img'
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT / provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    assert build.read_text().count('build completed successfully') == 2
    assert 'Deleted images and staging directories' in build.read_text()
    assert provenance['build_command'] == 'make -j$(nproc) installclean; make -j$(nproc) recoveryimage'
    assert manifest(TREE) == manifest(ANDROID / 'device/xiaomi/O1_asic')
    spec = read(TREE / 'patches/series.json')['repositories']['bootable/recovery']
    patch = spec['patches'][-1]
    assert patch['file'] == '0109-reboot-worker-quiescence.patch'
    assert sha(TREE / 'patches' / patch['file']) == patch['sha256']
    for name in ['twrp.cpp', 'gui2/backend/twrp_background_backend.cpp']:
        assert sha(ANDROID / 'bootable/recovery' / name) == spec['result_files'][name]
    reports = {}
    loaded = {}
    for stem, count, failures in [
        ('reboot-quiescence', 4, 0),
        ('reboot-quiescence-old-main', 4, 2),
        ('reboot-quiescence-old-background', 4, 4),
        ('reboot-quiescence-cli', 12, 0),
        ('reboot-quiescence-entry', 21, 0),
    ]:
        path = ROOT / f'logs/{stem}.json'
        report = read(path)
        assert len(report['cases']) == count
        assert sum(c['status'] == 'FAIL' for c in report['cases']) == failures
        assert report['status'] == ('FAIL' if failures else 'PASS')
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        item = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert item['evidence_sha256'] == sha(path)
        reports[stem] = dict(sha256=sha(path), cases=count, failures=failures)
        loaded[stem] = report
    for case in loaded['reboot-quiescence']['cases']:
        assert 'joined_all_workers_before_intent_and_reboot=1 cli_stop_idempotent=1' in case['output']
    for case in loaded['reboot-quiescence-old-main']['cases']:
        assert (case['status'] == 'FAIL') == case['case'].endswith('gui-0')
        if case['status'] == 'FAIL':
            assert 'destroyed==7' in case['output']
    for case in loaded['reboot-quiescence-old-background']['cases']:
        assert '!gui2_backend::command_thread.joinable()' in case['output']
    harness = str(ROOT / 'tests/reboot_quiescence_test.py')
    assert len({loaded[n]['sources'][harness] for n in [
        'reboot-quiescence', 'reboot-quiescence-old-main',
        'reboot-quiescence-old-background']}) == 1
    before = entries(ROOT / 'imgs/built/recovery-dijun-unified-backup-source-types.img')
    after = entries(image)
    changed = sorted(n for n in set(before) | set(after) if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery'], changed
    for name in ['system/bin/recovery', 'system/lib64/libgui2.so']:
        assert after[name] == (ANDROID / 'out/target/product/O1_asic/recovery/root' / name).read_bytes()
    package = read(image.with_suffix('.json'))
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(
        status='PASS', scope=__doc__, image_sha256=sha(image),
        production_sources=len(provenance['files']), jobs=provenance['jobs'],
        reports=reports, changed_ramdisk_entries=changed,
        limits='Original backend scope/seven destructors/background stop with real host threads '
               'and storage mutex under ASan/UBSan. Constructors/work/GUI/controllers/intent/'
               'reboot are fixtures. Already accepted work drains before final reboot; no new '
               'admission reservation, safe synchronous Binder/TEE cancellation, full MTP/USB '
               'shutdown or Android/device proof. Full OTA evidence remains historical.')
    (ROOT / 'logs/reboot-quiescence-delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: patch0109; worker ordering4; old-main2/4; old-background4/4; CLI12; entry21; clean image/six profiles')


if __name__ == '__main__':
    main()
