#!/usr/bin/env python3
"""Bind stock-manifest snapshot allocation attempts; never full OTA acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controller', action='store_true')
    args = parser.parse_args()
    path = ROOT / ('logs/ota-snapshot-prepare.json' if args.controller else 'logs/ota-snapshot-allocate.json')
    r = read(path)
    assert r['status'] == 'PASS' and r['fixture_elf_machine'] == 183
    assert r['actual_snapshot_manager'] and r['actual_snapshot_allocation_attempt']
    assert r['synthetic_source_layout'] and not r['actual_kernel_mapping']
    assert not any(r[k] for k in ['full_ota_install', 'production_changes', 'new_build'])
    for mapping in ['sources', 'dependencies']:
        for p, digest in r[mapping].items():
            assert sha(p) == digest, p
    inventory = ROOT / 'firmware/samples/os4-stable/inventory.json'
    manifest = inventory.with_name('payload-manifest.pb')
    assert sha(inventory) == r['inventory_sha256']
    assert sha(manifest) == r['manifest_sha256'] == read(inventory)['manifest_sha256']
    expected = ['map-denied', 'no-space', 'no-kernel', 'missing-estimate',
                'bad-cow-version', 'overlay', 'wrong-state']
    if args.controller:
        expected = ['map-denied', 'no-space', 'cancel-sync-error', 'store-error', 'unmap-error']
    assert r['controller_preparation_joined'] == args.controller
    assert [c['name'] for c in r['cases']] == expected
    for c in r['cases']:
        assert c['status'] == 'PASS' and c['returncode'] == 0
        assert c['diagnostic_observed'] and c['expected_diagnostic'] in c['stderr']
        assert 'PASS ' + c['name'] in c['stdout']
        if args.controller:
            assert 'source_metadata_unchanged=1' in c['stdout']
        else:
            assert 'images=0' in c['stdout'] and 'source_partitions=10' in c['stdout']
    mapped = r['cases'][0]['stdout']
    assert 'PLANNED checked stock sizes and COW estimates=10' in mapped
    assert 'BOUNDARY mapping rejected odm_b-cow targets=1' in mapped
    assert 'maps=1' in mapped
    if args.controller:
        for c in r['cases'][:2]:
            assert 'target_published=1 state=0' in c['stdout']
            assert 'overlap_sectors=18676176' in c['stdout']
            assert 'unmaps=10 stores=1 sync_failures=0' in c['stdout']
            assert 'Will overwrite existing partitions.' in c['stderr']
        assert 'unmaps=0 stores=0 sync_failures=1' in r['cases'][2]['stdout']
        assert 'target_published=0 state=1' in r['cases'][2]['stdout']
        assert 'unmaps=10 stores=1 sync_failures=0' in r['cases'][3]['stdout']
        assert 'unmaps=1 stores=0 sync_failures=0' in r['cases'][4]['stdout']
        for c in r['cases'][3:]:
            assert 'target_published=0 state=0' in c['stdout']
    else:
        assert 'code=-28 required=9287806976 maps=0' in r['cases'][1]['stdout']
    index = read(ROOT / 'simulation-report.json')
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    assert sha(index['image']) == index['image_sha256'] == r['image_sha256']
    image = Path(index['image'])
    provenance = read(image.with_name(image.stem + '-sources.json'))
    for p, digest in provenance['files'].items():
        assert sha(p) == digest, p
    entry = next(c for c in index['additional_checks']
                 if c['evidence'] == str(path.relative_to(ROOT)))
    assert entry['evidence_sha256'] == sha(path)
    result = dict(status='PASS', scope=__doc__, report_sha256=sha(path),
                  image_sha256=r['image_sha256'], production_sources=len(provenance['files']),
                  cases=len(expected), controller_preparation_joined=args.controller,
                  planned_dynamic_partitions=10, synthetic_source_layout=True,
                  actual_kernel_mapping=False, full_ota_install=False,
                  production_changes=False, new_build=False,
                  audit_source_sha256=sha(Path(__file__)))
    output = 'logs/snapshot-preparation-audit.json' if args.controller else 'logs/snapshot-allocation-audit.json'
    (ROOT / output).write_text(json.dumps(result, indent=2) + '\n')
    print('PASS stock-manifest preparation' if args.controller else 'PASS stock-manifest allocation',
          len(expected), '; synthetic LP, full OTA false')


if __name__ == '__main__':
    main()
