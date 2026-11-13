#!/usr/bin/env python3
"""Check independent ordinary-file F2FS content readback and reader provenance."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts, ramdisk_entries
from sync_device_tree import ROOT


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    index=json.loads((ROOT/'simulation-report.json').read_text());image=ROOT/index['image']
    assert sha(image)==index['image_sha256']
    evidence=ROOT/'logs/f2fs-readback.json';report=json.loads(evidence.read_text())
    assert report['status']=='PASS' and report['image_sha256']==sha(image)
    for name,digest in report['sources'].items():assert sha(name)==digest,name
    assert len(report['cases'])==2 and all(all(c['checks'].values()) for c in report['cases'])
    intact=report['cases'][0]
    assert intact['files']==intact['expected_files'] and len(intact['files'])==6
    assert intact['files']['nested/multi-node.bin']['size']>(5<<20)
    assert report['cases'][1]['checks']['only_payload_changed']
    original=json.loads((ROOT/'logs/f2fs-readback-stock-reader.json').read_text())
    assert original['status']=='FAIL'
    assert original['sources'][str(ROOT/'tests/f2fs_readback_test.py')]==sha(ROOT/'tests/f2fs_readback_test.py')
    old=original['cases'][0]
    assert {n for n in old['files'] if old['files'][n]!=old['expected_files'][n]}=={'inline.bin'}
    reference=json.loads((ROOT/'scripts/f2fs-reader-source.json').read_text())
    assert report['reader_package']['source']==reference
    assert sha(ROOT/'scripts/f2fs-inline-reader.patch')==reference['patch_sha256']
    for name,digest in reference['archives'].items():assert sha(ROOT/'tools/f2fs-host'/name)==digest
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name,digest in report['ramdisk_files'].items():assert hashlib.sha256(entries[name]).hexdigest()==digest,name
    for tool in ['make_f2fs','sload_f2fs']:
        a=[row for row in report['tool_transcripts'] if row['tool']==tool]
        assert len(a)==1 and a[0]['returncode']==0
    sources=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    for name,digest in sources['files'].items():assert sha(name)==digest,name
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result=dict(status='PASS',scope=__doc__,image_sha256=sha(image),evidence_sha256=sha(evidence),content_files=6,corruption_detected=True,reader_only_fix=True,production_changed=False,hardware_testing=False,full_filesystem_lifecycle=False)
    (ROOT/'logs/f2fs-readback-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: six actual F2FS file contents / corruption detected / host reader fix / unchanged production')


if __name__=='__main__':main()
