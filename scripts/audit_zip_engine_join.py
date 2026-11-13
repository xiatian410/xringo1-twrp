#!/usr/bin/env python3
"""Bind joined original ZIP parent/ARM64 engine evidence, including install failure.

A PASS here requires actual engine exit63 and parent INSTALL_ERROR. It does not
turn successful data/hash processing into full OTA installation success.
"""
import hashlib
import argparse
import json
from pathlib import Path
import re
from collections import Counter

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-finish',action='store_true',help='Audit modeled postinstall/mount/HAL/slot scope; not physical installation')
    parser.add_argument('--allocate-snapshots',action='store_true',help='Require actual controller preparation, COW initialization and writer handoff in the same run')
    parser.add_argument('--review-exit-failure',action='store_true',help='Review preserved allocated run with model lifetime crash; requires allocated mode, never marks installation successful')
    args=parser.parse_args()
    if args.allocate_snapshots and not args.model_finish:parser.error('--allocate-snapshots requires --model-finish')
    if args.review_exit_failure and not args.allocate_snapshots:parser.error('--review-exit-failure requires --allocate-snapshots')
    prefix='zip-engine-allocated-finish' if args.allocate_snapshots else 'zip-engine-model-finish' if args.model_finish else 'zip-engine-joined'
    path=ROOT/'logs'/(prefix+'.json')
    r=read(path)
    if args.review_exit_failure:
        assert r['status']=='FAIL'
        assert {k for k,v in r['checks'].items() if not v}=={'parent_assertions','child_exit0','parent_success'}
    else:
        assert r['status']=='PASS' and all(r['checks'].values())
    expected_code=1 if args.review_exit_failure else 0 if args.model_finish else 63
    assert r['installation_result']==('MODEL_SUCCESS' if args.model_finish and not args.review_exit_failure else 'FAILED') and r['engine_returncode']==expected_code
    assert r['original_zip_installer_joined'] and r['signature_enabled']
    assert r['full_payload_installed'] and not r['full_ota_install']
    assert r['snapshot_manager_executed']==args.model_finish and r['postinstall_mount_reached']==args.model_finish
    assert not r['production_trust_changed'] and not r['hardware_testing']
    for block,mappings in [(r,['sources','binary_dependencies']),
                           (r['engine'],['sources','dependencies'])]:
        for mapping in mappings:
            for name,digest in block[mapping].items():
                assert sha(name)==digest,name
    outpath=ROOT/'logs'/(prefix+'.stdout')
    errpath=ROOT/'logs'/(prefix+'.stderr')
    assert sha(outpath)==r['stdout_sha256'] and sha(errpath)==r['stderr_sha256']
    out,err=outpath.read_text(),errpath.read_text()
    assert 'whole-file signature verified' in err
    assert ('engine_wait_status=256' if args.review_exit_failure else 'engine_wait_status=0' if args.model_finish else 'engine_wait_status=16128') in out
    assert ('stock_result=0 engine_entered=1 mounts=1 unmounts=1' if args.model_finish and not args.review_exit_failure else 'stock_result=1 engine_entered=1 mounts=1 unmounts=1') in out
    assert 'finished DownloadAction with code ErrorCode::kSuccess' in err
    assert 'finished FilesystemVerifierAction with code ErrorCode::kSuccess' in err
    assert ('finished last action PostinstallRunnerAction with code ErrorCode::kSuccess' if args.model_finish else
        'finished last action PostinstallRunnerAction with code ErrorCode::kPostInstallMountError') in err
    assert 'Completed 4933/4933 operations (100%), 7883589123/7883589123 bytes downloaded (100%)' in err
    inventory_path=ROOT/'firmware/samples/os4-stable/inventory.json'
    assert sha(inventory_path)==r['inventory_sha256']
    inventory=read(inventory_path)
    rows=re.findall(r'Hash of ([A-Za-z0-9_]+): ([A-F0-9]{64})',err)
    assert len(rows)==len(dict(rows))==42
    assert dict(rows)==r['partition_hashes']
    assert {n:h.lower() for n,h in rows}=={n:p['sha256'] for n,p in inventory['partitions'].items()}
    assert out.count('BOUNDARY mapped COW view ')==10
    engine=r['engine']
    if args.model_finish:
        assert r['slot_model_updated'] and not r['physical_slot_switched']
        assert r['postinstall_mount_is_model'] and r['postinstall_program_executed']
        assert 'boot-complete not detected' in err
        assert 'MODEL actual FinishedSnapshotWrites result=1 state=2 merges=1' in out
        assert out.index('MODEL actual FinishedSnapshotWrites')<out.index('MODEL active slot=1 after Unverified')
        if args.allocate_snapshots:
            assert 'MODEL allocation metadata seeded' not in out
            assert 'MODEL actual controller allocation initialized=10 state=1 seeded=0' in out
            assert 'MODEL actual snapshot unmapping active=0' in out
            assert r['actual_snapshot_allocation'] and r['actual_controller_preparation']
            assert r['actual_controller_cow_writer'] and not r['allocation_metadata_seeded']
            assert r['synthetic_source_layout'] and r['file_mapping_model']
            assert r['scratch_and_daemon_disabled_for_test'] and not r['actual_kernel_mapping']
            assert engine['finish_model']['actual_allocation']
            assert out.index('MODEL actual controller allocation') < out.index('BOUNDARY mapped COW view') < out.index('MODEL actual FinishedSnapshotWrites')
            mapped=Counter(re.findall(r'Mapped COW device for (\w+_b) at /work/cows/\w+_b-cow',err))
            expected_dynamic={n+'_b' for group in inventory['groups'] for n in group['partitions']}
            assert mapped==Counter({n:2 for n in expected_dynamic}),mapped
            adapter_path=ROOT/'logs'/('zip-engine-allocated-adapter.cpp' if args.review_exit_failure else 'zip-engine-allocated-adapter-current.cpp')
            assert sha(adapter_path)==engine['adapter_sha256']
            adapter=adapter_path.read_text()
            assert adapter.count('model_prepare_allocated(manifest);')==1
            assert adapter.count('return allocated_control->OpenCowWriter(name,source,label);')==1
            assert 'model_prepare(dynamic);' not in adapter
            assert 'return CreateCowWriter(cow_version' not in adapter
            if not args.review_exit_failure:
                assert 'allocated_control->Cleanup();' in adapter
                assert 'allocated_control.reset();' in adapter
                assert out.count('MODEL released controller during Cleanup')==1
                assert out.index('MODEL actual FinishedSnapshotWrites') < out.index('MODEL released controller during Cleanup') < out.index('engine_wait_status=0')
                assert 'Fatal signal' not in err
            support=ROOT/'logs/zip-engine-allocated-support.inc'
            assert support.read_text()==(ROOT/'tests/ota_snapshot_initialize.cpp').read_text().split('int main(int argc,char**argv){',1)[0]
        else:
            assert 'MODEL allocation metadata seeded snapshots=10' in out
        assert engine['finish_model']['rlimit_nofile']==256
        # Compare exact stock script identity with its existing independent run.
        previous=read(ROOT/'logs/ota-stock-postinstall.json')
        stock=next(s for s in previous['samples'] if s['sample']=='os4-stable')
        assert stock['script_sha256']==engine['finish_model']['script_sha256']
    for name in ['sideload_main','update_attempter_android','download_action']:
        assert any(n.endswith('/'+name+'.o') for n in engine['dependencies'])
    index=read(ROOT/'simulation-report.json')
    assert r['image_sha256']==engine['image_sha256']==index['image_sha256']==sha(index['image'])
    image=Path(index['image'])
    provenance=read(image.with_name(image.stem+'-sources.json'))
    for n,d in provenance['files'].items():
        assert sha(n)==d,n
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    check=next(c for c in index['additional_checks'] if c['evidence']==str(path.relative_to(ROOT)))
    assert check['evidence_sha256']==sha(path)
    result=dict(status='PASS',scope=__doc__,image_sha256=r['image_sha256'],
        report_sha256=sha(path),production_sources=len(provenance['files']),
        operations=4933,partition_hashes=42,engine_returncode=expected_code,
        installation_result=r['installation_result'],parent_result='INSTALL_SUCCESS in explicit model' if args.model_finish else 'INSTALL_ERROR',
        full_ota_install=False,production_changes=False,new_build=False,
        audit_source_sha256=sha(Path(__file__)))
    if args.model_finish:
        result['scope']='Joined ZIP/ARM64/stock script/actual SnapshotManager completion with modeled mount/readonly/allocation/HAL/slot. Not real mount, snapshot creation, hardware slot or merge; not full OTA acceptance.'
    if args.allocate_snapshots:
        result.update(actual_snapshot_allocation=True, actual_controller_preparation=True,
                      actual_controller_cow_writer=True, allocation_metadata_seeded=False,
                      scope='One run joins original host ZIP installer/signature, intact ARM64 engine, actual controller preparation/SnapshotManager initialization10 COWs, original writer handoff4933 operations/42 hashes, exact stock Recovery script, actual completion then modeled slot. Source LP/file DM/readonly/mount/HAL/proc/cleanup/GUI remain explicit models; scratch/daemon disabled, no real mapping/boot/merge/full device OTA.')
    if args.review_exit_failure:
        probe_path=ROOT/'logs/ota-allocated-exit-probe.json'
        probe=read(probe_path)
        assert probe['status']=='PASS' and probe['full_run_report_sha256']==sha(path)
        for mapping in ['sources','dependencies']:
            for name,digest in probe[mapping].items():assert sha(name)==digest,name
        assert probe['image_sha256']==r['image_sha256']
        assert [c['name'] for c in probe['cases']]==['static','scoped']
        static,scoped=probe['cases']
        assert static['status']==scoped['status']=='PASS'
        assert static['returncode']!=0 and scoped['returncode']==0
        assert 'Fatal signal 11 (SIGSEGV)' in static['stderr']
        assert all('PROBE main completed' in c['stdout'] for c in probe['cases'])
        assert 'Update successfully applied, waiting to reboot.' in err
        assert 'Fatal signal 11 (SIGSEGV)' in err
        result.update(installation_result='FAILED', parent_result='INSTALL_ERROR',
                      exit_probe_sha256=sha(probe_path), model_lifetime_defect=True,
                      scope=result['scope']+' Full run exits1 after success callbacks due model static controller lifetime; parent correctly fails. Allocation-only same-adapter probe reproduces SIGSEGV with static ownership and exits0 with scoped release. Review PASS preserves INSTALLATION FAILED, no production defect proven.')
    (ROOT/'logs'/(prefix+'-audit.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS joined ZIP/ARM64 evidence:',r['installation_result'],'4933/42 verified; full OTA false')


if __name__=='__main__':
    main()
