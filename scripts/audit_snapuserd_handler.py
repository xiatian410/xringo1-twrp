#!/usr/bin/env python3
"""Verify actual ARM64 snapuserd client/handler/read/merge evidence and image provenance."""
import argparse
import hashlib
import json
from pathlib import Path

from sync_device_tree import ROOT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ordered', action='store_true', help='Audit ordered COPY/XOR/RA evidence and affected handler regression')
    args = parser.parse_args()
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    provenance = json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert provenance['image_sha256'] == sha(image)
    for name, digest in provenance['files'].items():
        assert sha(name) == digest, name
    path = ROOT/('logs/ota-snapuserd-ordered.json' if args.ordered else 'logs/ota-snapuserd-handler.json')
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
    if args.ordered:
        assert report['ordered_copy_xor'] and report['actual_readahead']
        assert any(n.endswith('/snapuserd_readahead.cpp') for n in report['sources'])
        cases = {c['name']: c for c in report['cases']}
        assert set(cases)=={'ordered-copy', 'ordered-xor', 'ordered-mixed', 'ordered-scratch',
                            'ordered-write-error', 'ordered-sync-error'}
        for name, case in cases.items():
            assert case['status']=='PASS' and case['returncode']==0
            out=case['stdout']; err=case['stderr']
            assert 'server_wait_status=0 result=PASS' in out and 'read_content=1' in out
            assert 'size_calls=2 control_opens=1' in out
            failed=int(name in {'ordered-write-error', 'ordered-sync-error'})
            progress=0 if failed else 2 if name=='ordered-copy' else 1 if name=='ordered-xor' else 4
            assert f'persisted_merge_ops={progress} expected={progress}' in out
            assert f'merge_complete={1-failed} merge_failed={failed} independent_base_readback=1 ordered=1 scratch={int(name=="ordered-scratch")}' in out
            assert f'injected_writes={int(name=="ordered-write-error")} injected_syncs={int(name=="ordered-sync-error")}' in out
            assert 'ReadAhead thread started.' in err and 'ReadAhead processing: RA_offline' in err
            assert 'ReadAhead thread terminating.' in err and 'MergeOrderedOps started' in err
        regression=json.loads((ROOT/'logs/ota-snapuserd-ordered-handler-regression.json').read_text())
        assert regression['status']=='PASS' and len(regression['cases'])==8
        assert all(c['status']=='PASS' and c['returncode']==0 for c in regression['cases'])
        assert regression['sources']==report['sources'] and regression['dependencies']==report['dependencies']
    else:
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
    check = next(c for c in index['additional_checks'] if c['name']==('actual-snapuserd-ordered-merge' if args.ordered else 'actual-snapuserd-handler-merge'))
    assert check['evidence_sha256'] == sha(path)
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result = dict(status='PASS', evidence_sha256=sha(path), image_sha256=sha(image), cases=len(cases),
        production_changed=False, production_sources=len(provenance['files']), actual_client_server=True,
        actual_handler=True, actual_replace_zero_merge=True, full_base_readback=True,
        base_capacity_boundary=True, dm_user_socket_boundary=True, kernel_mapping=False,
        ordered_copy_xor=args.ordered, actual_readahead=args.ordered, persisted_cow_progress=args.ordered, persistent_resume=False, full_ota_install=False)
    (ROOT/('logs/snapuserd-ordered-audit.json' if args.ordered else 'logs/snapuserd-handler-audit.json')).write_text(json.dumps(result, indent=2)+'\n')
    print('PASS:', len(cases), 'actual client/server/handler cases; ordered COPY/XOR/RA=', args.ordered, '; unchanged image; no full OTA claim')


if __name__ == '__main__':
    main()
