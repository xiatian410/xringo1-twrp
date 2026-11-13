#!/usr/bin/env python3
"""Review the preserved engine run without repeating its full 7.8GB execution.

The first fixture expected the wrong terminal boundary/code. Its FAIL record
is retained. Actual intact engine completed download/hash verification then
returned63 at block-readonly setup, before mount, postinstall or slot switch.
This review cannot turn that failed installation into a complete OTA success.
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


def main():
    raw=ROOT/'logs/ota-engine-entry-first-attempt.json'
    first=ROOT/'logs/ota-engine-entry-first-script.py'
    r=json.loads(raw.read_text())
    assert r['status']=='FAIL' and r['returncode']==63
    assert sha(first)==r['sources'][str(ROOT/'tests/ota_engine_entry.py')]
    for mapping in ['sources','dependencies']:
        for name,digest in r[mapping].items():
            if name==str(ROOT/'tests/ota_engine_entry.py'):
                continue
            assert sha(name)==digest,name
    stderr=ROOT/'logs/ota-engine-entry.stderr'
    stdout=ROOT/'logs/ota-engine-entry.stdout'
    assert sha(stderr)==r['stderr_sha256'] and stdout.read_text()==r['stdout']
    err=stderr.read_text()
    assert 'Completed 4933/4933 operations (100%), 7883589123/7883589123 bytes downloaded (100%)' in err
    assert 'Payload hash matches value in payload.' in err
    assert 'finished DownloadAction with code ErrorCode::kSuccess' in err
    assert 'finished FilesystemVerifierAction with code ErrorCode::kSuccess' in err
    assert 'finished last action PostinstallRunnerAction with code ErrorCode::kPostInstallMountError' in err
    terminal=err.split('ActionProcessor: starting PostinstallRunnerAction')[1]
    assert 'Marking block device /work/system.bin as read_only=1: Inappropriate ioctl for device' in terminal
    assert 'BOUNDARY denied postinstall mount' not in r['stdout']
    assert 'Error applying update: 63' in r['stdout']
    assert 'Step 1/2' in r['stdout'] and 'Step 2/2' in r['stdout']
    assert r['fixture_elf_machine']==183
    assert any(n.endswith('/aosp/sideload_main.o') for n in r['dependencies'])
    assert any(n.endswith('/aosp/update_attempter_android.o') for n in r['dependencies'])
    assert any(n.endswith('/download_action.o') for n in r['dependencies'])
    assert not any(n.endswith('/aosp/hardware_android.o') for n in r['dependencies'])
    inventory_path=ROOT/'firmware/samples/os4-stable/inventory.json'
    inventory=json.loads(inventory_path.read_text())
    rows=re.findall(r'Hash of ([A-Za-z0-9_]+): ([A-F0-9]{64})',err)
    assert len(rows)==len(dict(rows))==42
    assert {n:h.lower() for n,h in rows}=={n:p['sha256'] for n,p in inventory['partitions'].items()}
    assert r['stdout'].count('BOUNDARY mapped COW view ')==10
    index=json.loads((ROOT/'simulation-report.json').read_text())
    assert r['image_sha256']==index['image_sha256']==sha(index['image'])
    provenance=json.loads(Path(index['image']).with_name(Path(index['image']).stem+'-sources.json').read_text())
    for n,d in provenance['files'].items():
        assert sha(n)==d,n
    result=dict(status='PASS',scope=__doc__,image_sha256=r['image_sha256'],
        raw_report_sha256=sha(raw),first_script_sha256=sha(first),
        current_harness_sha256=sha(ROOT/'tests/ota_engine_entry.py'),
        stderr_sha256=sha(stderr),stdout_sha256=sha(stdout),inventory_sha256=sha(inventory_path),
        source_zip_sha256=r['source_zip_sha256'],payload_bytes=7883589123,
        operations=4933,partition_hashes=dict(rows),cow_views=10,
        engine_returncode=63,installation_result='FAILED at postinstall block-readonly setup',
        original_sideload_main=True,original_attempter=True,original_download_action=True,
        postinstall_mount_reached=False,postinstall_program_executed=False,slot_switched=False,
        original_zip_installer_joined=False,snapshot_manager_executed=False,
        full_ota_install=False,production_changes=False,new_build=False,
        review_script_sha256=sha(Path(__file__)))
    (ROOT/'logs/ota-engine-entry-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS evidence review: original ARM64 engine4933/42 hashes; INSTALL FAILED63 before postinstall mount; no replay')


if __name__=='__main__':
    main()
