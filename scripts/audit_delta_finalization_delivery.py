#!/usr/bin/env python3
"""Bind finalization-error fix to a clean-built image; no full OTA acceptance."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-delta-finalization.img'
    old = ROOT/'imgs/built/recovery-dijun-unified-bounded-maintenance.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image) and provenance['jobs'] == 30
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    assert 'libpayload_consumer clang++ payload_consumer/delta_performer.cc' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/delta-finalization-final-source.log').read_text()
    def entries(path):
        return {e[0]: (e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    before, after = entries(old), entries(image)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/update_engine_sideload']
    engine = ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/update_engine_sideload'
    assert after['system/bin/update_engine_sideload'][1] == engine.read_bytes()
    assert b'Failed to close final partition:' in engine.read_bytes()
    reports = {}
    for old_report in [False, True]:
        path = ROOT/('logs/ota-delta-finalization-before.json' if old_report else 'logs/ota-delta-finalization.json')
        r = json.loads(path.read_text())
        assert r['fixture_elf_machine'] == 183 and len(r['cases']) == 8
        assert r['image_sha256'] == sha(image)
        for group in ['sources', 'dependencies']:
            for name, digest in r[group].items():
                assert sha(name) == digest, name
        failed = [c['name'] for c in r['cases'] if c['status'] == 'FAIL']
        assert failed == (['final-finish-fail', 'final-close-fail', 'switch-close-fail'] if old_report else [])
        reports[path.name] = dict(sha256=sha(path), failures=failed, cases=8)
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image),
        production_sources=len(provenance['files']), changed_ramdisk_entries=changed,
        reports=reports, hardware_testing=False, full_payload_install=False,
        reused_scope='Unchanged GUI/runtime/stock asset bytes compared to prior candidate; no redundant feature reruns.')
    (ROOT/'logs/delta-finalization-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: clean build, pinned sources, eight ARM64 cases / three old failures, six profiles, current engine bytes')


if __name__ == '__main__':
    main()
