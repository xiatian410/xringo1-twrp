#!/usr/bin/env python3
"""Review actual snapshot completion -> postinstall slot gating and persisted retries."""
import hashlib
import json
from pathlib import Path
from sync_device_tree import ROOT, TREE, ANDROID, manifest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = ROOT/'logs/ota-snapshot-postinstall.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and len(report['cases']) == 6
    assert report['fixture_elf_machine'] == 183
    assert report['postinstall_connected'] and report['snapshot_manager_executed']
    assert report['hardware_effects_denied'] and not report['full_payload_install']
    for group in ['sources', 'dependencies']:
        for name, digest in report[group].items():
            assert sha(name) == digest, name
    required = ['aosp/dynamic_partition_control_android.cc', 'payload_consumer/postinstall_runner_action.cc']
    for suffix in required:
        assert str(ANDROID/'system/update_engine'/suffix) in report['sources']
    index = json.loads((ROOT/'simulation-report.json').read_text())
    assert index['image_sha256'] == report['image_sha256'] == sha(report['image'])
    assert index['status'] == 'in_progress' and len(index['not_yet_completed']) == 12
    provenance = json.loads(Path(report['image']).with_name(Path(report['image']).stem+'-sources.json').read_text())
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    assert manifest(TREE) == manifest(ANDROID/'device/xiaomi/O1_asic')
    names = ['normal', 'boot-sync-retry', 'state-sync-retry', 'state-open-retry', 'merge-status-retry', 'slot-retry']
    assert [c['name'] for c in report['cases']] == names
    for case in report['cases']:
        name, output = case['name'], case['stdout']
        assert 'PASS actual postinstall -> control -> SnapshotManager' in output
        first = next(line for line in output.splitlines() if line.startswith('FIRST '))
        assert 'finishes=1 switches='+str(int(name in ['normal', 'slot-retry'])) in first
        if name != 'normal':
            assert 'RETRY code=0 finishes=2 switches='+str(2 if name == 'slot-retry' else 1) in output
            assert 'reused_state=1' in output
        if name in ['boot-sync-retry', 'state-sync-retry']:
            assert 'sync_errors=1' in first
    result = dict(status='PASS', scope=__doc__, report_sha256=sha(path),
                  image_sha256=report['image_sha256'], production_sources=len(provenance['files']),
                  production_fix=False, new_build=False, hardware_testing=False,
                  cases=6, full_payload_install=False, actual_snapshot_manager=True,
                  boundaries=['synthetic plan skips postinstall scripts', 'metadata already-mounted token',
                              'merge HAL result', 'slot result', 'FakeHardware; no actual vbmeta writes',
                              'no mapping, snapuserd or merge'],
                  decision='Original failure gate blocks slot attempt. Recreated controller resumes persisted Initiated state, or skips republishing Unverified state after slot failure. No additional production patch justified.')
    (ROOT/'logs/ota-snapshot-postinstall-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: six joined ARM64 finalization/retry cases; unchanged', len(provenance['files']), 'production sources; no new build')


if __name__ == '__main__':
    main()
