#!/usr/bin/env python3
"""Verify finite allocated-COW/controller/VABC handoff evidence, not full OTA."""
import hashlib
from pathlib import Path
import json

from audit_snapshot_allocation import ROOT, read, sha
from firmware_facts import boot_parts, ramdisk_entries


def main():
    path = ROOT / 'logs/ota-snapshot-payload-handoff.json'
    r = read(path)
    assert r['status'] == 'PASS' and r['fixture_elf_machine'] == 183
    assert all(r[k] for k in ['actual_snapshot_manager', 'actual_controller_open_writer',
                             'actual_vabc_writer', 'synthetic_layout', 'file_mapping_model',
                             'scratch_and_daemon_disabled_for_test'])
    assert not any(r[k] for k in ['actual_kernel_mapping', 'full_ota_install', 'production_changes', 'new_build'])
    for mapping in ['sources', 'dependencies']:
        for name, expected in r[mapping].items():
            assert sha(name) == expected, name
    support = ROOT / 'tests/ota_snapshot_initialize.cpp'
    prefix = support.read_text().split('int main(int argc,char**argv){', 1)[0]
    assert hashlib.sha256(prefix.encode()).hexdigest() == r['support_prefix_sha256']
    index = read(ROOT / 'simulation-report.json')
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    image = Path(index['image'])
    assert sha(image) == index['image_sha256'] == r['image_sha256']
    provenance = read(image.with_name(image.stem + '-sources.json'))
    assert provenance['image_sha256'] == r['image_sha256']
    for name, expected in provenance['files'].items():
        assert sha(name) == expected, name
    entries = {e[0]: e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    assert all(hashlib.sha256(entries[n]).hexdigest() == expected for n, expected in r['image_entries'].items())
    sample = ROOT / 'firmware/samples/os4-stable'
    assert sha(sample / 'inventory.json') == r['inventory_sha256']
    assert sha(sample / 'payload-manifest.pb') == r['manifest_sha256'] == read(sample / 'inventory.json')['manifest_sha256']
    assert r['stock_partition_sha256'] == read(sample / 'inventory.json')['partitions']['mi_ext']['sha256']
    assert [(o['number'], o['type']) for o in r['operations']] == [(0, 8), (1, 0)]
    assert r['expected_bytes'] == 4194304
    assert [c['name'] for c in r['cases']] == ['normal', 'resume', 'corrupt-header']
    for c in r['cases']:
        assert c['status'] == 'PASS' and c['returncode'] == 0
        assert 'PASS ' + c['name'] in c['stdout']
        if c['name'] != 'corrupt-header':
            assert c['readback_sha256'] == r['expected_sha256']
            assert 'allocated=10 stock_operations=2 bytes=4194304 unmap=1 state=1 completed=0' in c['stdout']
            if c['name'] == 'resume':
                assert 'Resuming update on partition `mi_ext` op index 1' in c['stderr']
        else:
            assert c['readback_sha256'] is None
            assert 'init_rejected=1 unmap=1 state=1 completed=0' in c['stdout']
            assert 'OpenCompressedSnapshotWriter: read header failed' in c['stderr']
    entry = next(c for c in index['additional_checks'] if c['evidence'] == str(path.relative_to(ROOT)))
    assert entry['evidence_sha256'] == sha(path)
    result = dict(status='PASS', report_sha256=sha(path), image_sha256=r['image_sha256'],
                  production_sources=len(provenance['files']), cases=3, stock_operations_per_success=2,
                  verified_bytes_per_success=4194304, full_ota_install=False, production_changes=False,
                  new_build=False, scope=__doc__, audit_source_sha256=sha(Path(__file__)))
    (ROOT / 'logs/snapshot-payload-handoff-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS allocated COW -> original controller/VABC, stock2 operations, resume/rejection; no new build')


if __name__ == '__main__':
    main()
