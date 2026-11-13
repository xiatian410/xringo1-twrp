#!/usr/bin/env python3
"""Bind joined original ZIP parent/ARM64 engine evidence, including install failure.

A PASS here requires actual engine exit63 and parent INSTALL_ERROR. It does not
turn successful data/hash processing into full OTA installation success.
"""
import hashlib
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
    path=ROOT/'logs/zip-engine-joined.json'
    r=read(path)
    assert r['status']=='PASS' and all(r['checks'].values())
    assert r['installation_result']=='FAILED' and r['engine_returncode']==63
    assert r['original_zip_installer_joined'] and r['signature_enabled']
    assert r['full_payload_installed'] and not r['full_ota_install']
    assert not r['snapshot_manager_executed'] and not r['postinstall_mount_reached']
    assert not r['production_trust_changed'] and not r['hardware_testing']
    for block,mappings in [(r,['sources','binary_dependencies']),
                           (r['engine'],['sources','dependencies'])]:
        for mapping in mappings:
            for name,digest in block[mapping].items():
                assert sha(name)==digest,name
    outpath=ROOT/'logs/zip-engine-joined.stdout'
    errpath=ROOT/'logs/zip-engine-joined.stderr'
    assert sha(outpath)==r['stdout_sha256'] and sha(errpath)==r['stderr_sha256']
    out,err=outpath.read_text(),errpath.read_text()
    assert 'whole-file signature verified' in err
    assert 'engine_wait_status=16128' in out
    assert 'stock_result=1 engine_entered=1 mounts=1 unmounts=1' in out
    assert 'finished DownloadAction with code ErrorCode::kSuccess' in err
    assert 'finished FilesystemVerifierAction with code ErrorCode::kSuccess' in err
    assert 'finished last action PostinstallRunnerAction with code ErrorCode::kPostInstallMountError' in err
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
        operations=4933,partition_hashes=42,engine_returncode=63,
        installation_result='FAILED',parent_result='INSTALL_ERROR',
        full_ota_install=False,production_changes=False,new_build=False,
        audit_source_sha256=sha(Path(__file__)))
    (ROOT/'logs/zip-engine-joined-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS joined ZIP/ARM64 evidence: actual install FAILED63 -> parent INSTALL_ERROR;4933/42 verified')


if __name__=='__main__':
    main()
