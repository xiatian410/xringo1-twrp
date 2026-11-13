#!/usr/bin/env python3
"""Bind actual SnapshotManager cleanup ordering to modeled mapper/image boundaries."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    evidence = ROOT/'logs/ota-snapshot-devices.json'
    report = json.loads(evidence.read_text())
    assert report['status'] == 'PASS' and report['image_sha256'] == sha(image)
    assert report['fixture_elf_machine'] == 183 and len(report['cases']) == 15
    assert report['snapshot_manager_executed'] and report['snapshot_device_cleanup_executed']
    assert report['hardware_effects_denied'] and not report['full_payload_install']
    for group in ['sources', 'dependencies']:
        for name, digest in report[group].items():
            assert sha(name) == digest, name
    cases = {c['name']: c for c in report['cases']}
    stops = {'snapshot-fail': 1, 'cow-fail': 3, 'image-fail': 5, 'base-fail': 6,
             'source-fail': 7, 'open-image': 2, 'missing-metadata': 0,
             'all-missing-directory': 0, 'control-cow-fail': 3, 'userspace-delete-fail': 3}
    for name, case in cases.items():
        assert case['status'] == 'PASS' and case['returncode'] == 0
        output = case['stdout']
        expected = 0 if name in stops else 1
        assert f'result={expected} expected={expected}' in output
        order = next(line for line in output.splitlines() if line.startswith('ORDER')).split()[1:]
        assert len(order) == stops.get(name, 9 if name == 'userspace-active' else 7), name
        assert 'PASS original SnapshotManager unmap ordering/retry' in output
    ramdisk = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name, digest in report['image_entries'].items():
        assert hashlib.sha256(ramdisk[name]).hexdigest() == digest, name
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    result = dict(status='PASS', scope=__doc__, evidence_sha256=sha(evidence),
                  image_sha256=sha(image), cases=15, production_changed=False,
                  actual_snapshot_manager=True, actual_kernel_mapping=False,
                  actual_snapuserd=False, actual_image_manager=False, full_ota_install=False)
    (ROOT/'logs/snapshot-devices-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: actual SnapshotManager cleanup15/order/partial state/retry; modeled devices; unchanged image')


if __name__ == '__main__':
    main()
