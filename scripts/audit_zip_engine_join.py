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
    args=parser.parse_args()
    prefix='zip-engine-model-finish' if args.model_finish else 'zip-engine-joined'
    path=ROOT/'logs'/(prefix+'.json')
    r=read(path)
    assert r['status']=='PASS' and all(r['checks'].values())
    expected_code=0 if args.model_finish else 63
    assert r['installation_result']==('MODEL_SUCCESS' if args.model_finish else 'FAILED') and r['engine_returncode']==expected_code
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
    assert ('engine_wait_status=0' if args.model_finish else 'engine_wait_status=16128') in out
    assert ('stock_result=0 engine_entered=1 mounts=1 unmounts=1' if args.model_finish else 'stock_result=1 engine_entered=1 mounts=1 unmounts=1') in out
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
    (ROOT/'logs'/(prefix+'-audit.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('PASS joined ZIP/ARM64 evidence:',r['installation_result'],'4933/42 verified; full OTA false')


if __name__=='__main__':
    main()
