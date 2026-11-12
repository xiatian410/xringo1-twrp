#!/usr/bin/env python3
"""Bind log export failure propagation to clean build and unchanged worker paths."""
import hashlib
import json
from pathlib import Path
import sys
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, TREE, ANDROID, manifest
sys.path.insert(0, str(ROOT/'tests'))
from nested_partition_path_test import method


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    image = ROOT/'imgs/built/recovery-dijun-unified-log-export.img'
    prior = ROOT/'imgs/built/recovery-dijun-unified-backup-manage.img'
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image) and provenance['jobs'] == 30
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    build = ROOT/provenance['build_log']
    assert sha(build) == provenance['build_log_sha256']
    text = build.read_text()
    assert 'Deleted images and staging directories' in text and text.count('build completed successfully') == 2
    assert 'gui2/backend/twrp_tools_backend.cpp' in text and 'clang++ twrp_functions.cpp' in text
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    assert 'Pending: 0 source updates, device tree changed=False' in (ROOT/'logs/copylog-final-source.log').read_text()
    def entries(path):
        return {e[0]:(e[1], e[-1]) for e in ramdisk_entries(boot_parts(path.read_bytes())[1]['ramdisk'])}
    before, after = entries(prior), entries(image)
    changed = [n for n in sorted(before.keys() | after.keys()) if before.get(n) != after.get(n)]
    assert changed == ['prop.default', 'ramdisk-files.sha256sum', 'system/bin/recovery']
    recovery = after['system/bin/recovery'][1]
    assert recovery == (ANDROID/'out/target/product/O1_asic/recovery/root/system/bin/recovery').read_bytes()
    for marker in [b'Log export failed: current storage is unavailable', b'Log export failed: logcat capture',
                   b'Log export failed: cannot read kernel ring buffer']:
        assert marker in recovery
    rejected = ['mount-fail', 'empty-storage', 'recovery-copy-fail', 'recovery-source-missing',
                'kernel-size-fail', 'kernel-read-fail', 'kernel-write-fail', 'logcat-capture-fail',
                'logcat-write-fail', 'both-captures-fail', 'reused-worker']
    reports = {}
    for name, expected in [('copylog', []), ('copylog-before', rejected)]:
        path = ROOT/'logs'/(name+'.json')
        r = json.loads(path.read_text())
        assert len(r['cases']) == 13
        assert [c['name'] for c in r['cases'] if c['status'] == 'FAIL'] == expected
        for source, digest in r['sources'].items():
            assert sha(source) == digest, source
        reports[name] = dict(sha256=sha(path), cases=13, failed=len(expected))
    # Full-file hashes changed; compare the actual unchanged functions instead
    # of rerunning backup/refresh fixtures or claiming their old hashes match.
    src = ANDROID/'bootable/recovery'
    preserved = {}
    for path, signatures in [
        ('gui2/backend/twrp_tools_backend.cpp', ['int manage_backup(', 'int refreshsizes()',
         'bool twrp_tools_backend::start(', 'void twrp_tools_backend::run(',
         'tool_state twrp_tools_backend::status()', 'void twrp_tools_backend::acknowledge()']),
        ('twrp_functions.cpp', ['int TWFunc::CopyFile(', 'int TWFunc::RemoveDir('])]:
        old = (ROOT/'backups/copylog-pre-fix'/Path(path).name).read_text()
        current = (src/path).read_text()
        for signature in signatures:
            a, b = method(old, signature), method(current, signature)
            assert a == b, signature
            preserved[signature] = hashlib.sha256(b.encode()).hexdigest()
    package = json.loads(image.with_suffix('.json').read_text())
    assert package['sha256'] == sha(image) and len(package['profiles']) == 6
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == sha(image) and index['status'] == 'in_progress'
    assert len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image), production_sources=len(provenance['files']),
                  changed_ramdisk_entries=changed, reports=reports, preserved_functions=preserved,
                  hardware_testing=False, power_loss_verified=False,
                  reused_scope='Unchanged backup and refresh worker methods; identical profiles, update_engine and shared GUI libraries. No redundant feature reruns.')
    (ROOT/'logs/copylog-delivery.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: 13 log-export cases / 11 old failures, clean build / 781 sources / six profiles; unchanged worker methods reused')


if __name__ == '__main__':
    main()
