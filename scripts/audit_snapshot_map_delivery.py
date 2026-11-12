#!/usr/bin/env python3
"""Bind snapshot-map error fix to a clean-built image; no full OTA acceptance."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-snapshot-map.img'
    old = ROOT/'imgs/built/recovery-dijun-unified-delta-finalization.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image) and provenance['jobs'] == 30
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    log = ROOT/provenance['build_log']
    assert sha(log) == provenance['build_log_sha256']
    text = log.read_text()
    assert 'Deleted images and staging directories' in text
    assert text.count('build completed successfully') == 2
    assert 'libpayload_consumer clang++ payload_consumer/filesystem_verifier_action.cc' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/snapshot-map-final-source.log').read_text()
    def entries(path):
        return {e[0]: (e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    before, after = entries(old), entries(image)
    changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/update_engine_sideload']
    engine = ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/update_engine_sideload'
    assert after['system/bin/update_engine_sideload'][1] == engine.read_bytes()
    for marker in [b'Failed to map snapshot partitions for verification',
                   b'Failed to remap snapshot partitions for verification']:
        assert marker in engine.read_bytes()
    reports = {}
    for old_report in [False, True]:
        path = ROOT/('logs/ota-snapshot-map-before.json' if old_report else 'logs/ota-snapshot-map.json')
        r = json.loads(path.read_text())
        assert r['fixture_elf_machine'] == 183 and len(r['cases']) == 6
        assert r['image_sha256'] == sha(image)
        for group in ['sources', 'dependencies']:
            for name, digest in r[group].items():
                assert sha(name) == digest, name
        failed = [c['name'] for c in r['cases'] if c['status'] == 'FAIL']
        assert failed == (['initial-fail', 'remap-fail'] if old_report else [])
        assert r['snapshot_manager_executed'] is False
        assert r['mapping_result_boundary'] is True and r['full_payload_install'] is False
        expected = {'success': (0, 1), 'initial-fail': (47, 1),
                    'initial-fail-missing-path': (47, 1), 'remap-success': (0, 1),
                    'remap-fail': (47, 2), 'hash-mismatch': (15, 1)}
        assert [c['name'] for c in r['cases']] == list(expected)
        for case in r['cases']:
            code, unmaps = expected[case['name']]
            if old_report and case['name'] in failed:
                code, unmaps = 0, 1
            assert f"code={code} map=1 unmap={unmaps}\n" in case['stdout']
        # The exact linker/library bytes came from this candidate, not a host substitute.
        for name, digest in r['image_entries'].items():
            assert hashlib.sha256(after[name][1]).hexdigest() == digest, name
        reports[path.name] = dict(sha256=sha(path), failures=failed, cases=6)
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image),
        production_sources=len(provenance['files']), changed_ramdisk_entries=changed,
        reports=reports, hardware_testing=False, full_payload_install=False,
        reused_scope='Unchanged GUI/runtime/stock asset bytes compared to prior candidate; no redundant feature reruns.')
    (ROOT/'logs/snapshot-map-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: clean build, pinned sources, six ARM64 cases / two old failures, six profiles, current engine bytes')


if __name__ == '__main__':
    main()
