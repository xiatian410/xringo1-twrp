#!/usr/bin/env python3
"""Bind ext4 post-format labeling evidence without claiming mounts or enforcement."""
import hashlib
import json
from pathlib import Path

from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT, ANDROID


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    index = read(ROOT/'simulation-report.json')
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    provenance = read(image.with_name(image.stem+'-sources.json'))
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    entries = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    evidence = {}
    loaded = {}
    for label, count in [('current', 5), ('native-regression', 6)]:
        path = ROOT/'logs'/('format-selinux-chain-current.json' if label == 'current' else 'format-selinux-native-regression.json')
        report = read(path)
        assert report['status'] == 'PASS' and report['image_sha256'] == sha(image)
        assert len(report['cases']) == count
        assert all(c['status'] == 'PASS' and all(c['checks'].values()) for c in report['cases'])
        for name, digest in report['sources'].items():
            assert sha(name) == digest, name
        for name, digest in report['ramdisk_files'].items():
            assert hashlib.sha256(entries[name]).hexdigest() == digest, name
        check = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
        assert check['evidence_sha256'] == sha(path)
        evidence[label] = dict(sha256=sha(path), cases=count)
        loaded[label] = report
    report = loaded['current']
    cases = {c['name']: c for c in report['cases']}
    assert set(cases) == {'label-data', 'label-system', 'label-combined-missing', 'label-missing', 'label-invalid'}
    policies = ['plat_file_contexts', 'system_ext_file_contexts', 'product_file_contexts', 'vendor_file_contexts', 'odm_file_contexts']
    assert all(name in report['ramdisk_files'] for name in ['file_contexts', *policies])
    for name in ['label-data', 'label-system', 'label-combined-missing']:
        case = cases[name]
        assert 'RESULT status=0 filesystem=ext4 repair=1' in case['stdout']
        assert 'security.selinux' in case['label_readback']['stdout']
        assert all('/'+p in case['stderr'] for p in policies)
        assert case['invocations'][-3:] == ['e2fsck', '-fp', '/fixtures/target.img']
    for name in ['label-missing', 'label-invalid']:
        case = cases[name]
        assert 'RESULT status=1 filesystem=ext4 repair=0' in case['stdout']
        assert 'security.selinux' not in case['label_readback']['stdout']
        assert 'e2fsdroid: Invalid argument while configuring the file system' in case['stderr']
        assert 'e2fsck' not in case['invocations']
    assert any('libselinux.so' in p for p in report['sources'])
    # Bind the source explanation of Android's actual policy path selection.
    source_paths = [ANDROID/'external/e2fsprogs/contrib/android/perms.c',
                    ANDROID/'external/selinux/libselinux/src/android/android_seapp.c']
    perms, paths = [p.read_text() for p in source_paths]
    assert '#if !defined(__ANDROID__)' in perms and 'sehnd = selinux_android_file_context_handle();' in perms
    assert all('"/'+p+'"' in paths for p in policies)
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, image_sha256=sha(image),
                  production_sources=len(provenance['files']), evidence=evidence,
                  source_explanation={str(p): sha(p) for p in source_paths},
                  production_changed=False, new_build=False, hardware_testing=False,
                  full_filesystem_lifecycle=False, kernel_selinux_enforcement=False,
                  limitations='Host production callers and libselinux; actual ARM64 tools, image contexts and independent debugfs root xattr readback on private regular files. Unmount/device/metadata/presentation remain explicit fixtures. No real mounts, encryption or full GUI.')
    (ROOT/'logs/format-selinux-chain-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: labeling5 / default tool regression6 / image sources'+str(len(provenance['files']))+'; no production change or full lifecycle claim')


if __name__ == '__main__':
    main()
