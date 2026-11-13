#!/usr/bin/env python3
"""Verify actual ARM64 snapuserd client/handler/read/merge evidence and image provenance."""
import hashlib
import json
from pathlib import Path

from sync_device_tree import ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    path = ROOT/'logs/ota-snapuserd-handler.json'
    report = json.loads(path.read_text())
    assert report['status'] == 'PASS' and report['fixture_elf_machine'] == 183
    assert report['real_server'] and report['real_unix_stream'] and report['actual_client']
    assert report['handler_lifecycle'] and report['snapshot_handlers'] and report['actual_merge_worker']
    assert not report['kernel_mapping'] and not report['original_daemon_main']
    for group in ['sources', 'dependencies']:
        for name, digest in report[group].items():
            assert sha(name) == digest, name
    for leaf in ['handler_manager.cpp', 'snapuserd_client.cpp', 'snapuserd_core.cpp',
                 'merge_worker.cpp', 'read_worker.cpp', 'dm_user_block_server.cpp']:
        assert any(n.endswith('/'+leaf) for n in report['sources']), leaf
    for leaf in ['libsnapuserd.a', 'libsnapuserd_client.a', 'libsnapshot_cow.a']:
        assert any(n.endswith('/'+leaf) for n in report['dependencies']), leaf
    cases = {c['name']: c for c in report['cases']}
    assert set(cases) == {'init-delete', 'active-read-delete', 'corrupt-cow', 'missing-control',
                          'reinitialize', 'merge-readback', 'merge-write-error', 'merge-sync-error'}
    for name, case in cases.items():
        assert case['status'] == 'PASS' and case['returncode'] == 0
        out = case['stdout']
        assert 'server_wait_status=0 result=PASS' in out
        reject = name in {'corrupt-cow', 'missing-control'}
        assert f'init_sectors={0 if reject else 128}' in out
        counts = {'corrupt-cow': (1, 0), 'missing-control': (1, 1), 'reinitialize': (4, 2)}.get(name, (2, 1))
        assert f'size_calls={counts[0]} control_opens={counts[1]}' in out
        assert f'injected_writes={int(name == "merge-write-error")} injected_syncs={int(name == "merge-sync-error")}' in out
        if name == 'active-read-delete' or name.startswith('merge-'):
            assert 'read_content=1' in out
        if name.startswith('merge-'):
            failed = int(name != 'merge-readback')
            assert f'merge_complete={1-failed} merge_failed={failed} independent_base_readback=1' in out
            assert 'Merge starting: MergeWorker_offline' in case['stderr']
        if name == 'corrupt-cow': assert 'Header Magic corrupted' in case['stderr']
        if name == 'missing-control': assert 'Unable to open block server' in case['stderr']
    check = next(c for c in index['additional_checks'] if c['name']=='actual-snapuserd-handler-merge')
    assert check['evidence_sha256'] == sha(path)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS', evidence_sha256=sha(path), image_sha256=sha(image), cases=8,
        production_changed=False, production_sources=len(provenance['files']), actual_client_server=True,
        actual_handler=True, actual_replace_zero_merge=True, full_base_readback=True,
        base_capacity_boundary=True, dm_user_socket_boundary=True, kernel_mapping=False,
        ordered_copy_xor=False, persistent_resume=False, full_ota_install=False)
    (ROOT/'logs/snapuserd-handler-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: client/server/handler8, actual read/decompress/replace-zero merge and write/sync errors; unchanged image; no full OTA claim')


if __name__ == '__main__':
    main()
