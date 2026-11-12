#!/usr/bin/env python3
"""Review metadata-unavailable fallback scope; reject isolated-map defect claims."""
import hashlib
import json
from pathlib import Path
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    evidence = ROOT/'logs/ota-recovery-fallback.json'
    r = json.loads(evidence.read_text())
    assert r['status'] == 'PASS' and len(r['cases']) == 6
    assert r['fixture_elf_machine'] == 183 and r['production_fix'] is False
    assert r['caller_compression_gate_checked'] is True and r['snapshot_manager_executed'] is False
    for group in ['sources', 'dependencies']:
        for name, digest in r[group].items():
            assert sha(name) == digest, name
    current = json.loads((ROOT/'simulation-report.json').read_text())
    assert current['image_sha256'] == r['image_sha256'] == sha(current['image'])
    assert current['status'] == 'in_progress' and len(current['not_yet_completed']) == 12
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    provenance = json.loads(Path(current['image']).with_name(Path(current['image']).stem+'-sources.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    production = ANDROID/'system/update_engine'
    originals = [production/'aosp/dynamic_partition_control_android.cc',
                 production/'payload_consumer/filesystem_verifier_action.cc',
                 production/'payload_consumer/partition_writer_factory_android.cc',
                 ANDROID/'system/core/fs_mgr/libsnapshot/snapshot.cpp']
    # Source review only: preserve exact callers and libsnapshot implementation
    # used to reject the initial hypothesis, not a claim of runtime execution.
    verifier = originals[1].read_text()
    factory = originals[2].read_text()
    snapshot = originals[3].read_text()
    assert 'dynamic_control_->UpdateUsesSnapshotCompression() &&' in verifier
    assert 'dynamic_control && dynamic_control->UpdateUsesSnapshotCompression() &&' in factory
    assert 'auto lock = LockShared();\n    if (!lock) return false;\n    return UpdateUsesSnapuserd(lock.get());' in snapshot
    result = dict(status='PASS', scope=__doc__, report_sha256=sha(evidence),
                  image_sha256=current['image_sha256'], production_sources=len(provenance['files']),
                  original_sources={str(p):sha(p) for p in originals},
                  source_review_only=['verifier/factory compression gate', 'SnapshotManager lock failure returns false'],
                  production_fix=False, full_ota_install=False, snapshot_manager_executed=False,
                  decision='No map-gate patch: diagnostic direct MapAllPartitions rejection does not prove an install failure. Actual SnapshotManager lifecycle remains open.')
    (ROOT/'logs/ota-recovery-fallback-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: six ARM64 controller cases, compression gate scope, unchanged 781-source delivered image; no production fix')


if __name__ == '__main__':
    main()
