#!/usr/bin/env python3
"""Bind actual ARM64 formatter/repair execution evidence to the unchanged image."""
import hashlib
import json
from pathlib import Path
from firmware_facts import boot_parts,ramdisk_entries
from sync_device_tree import ROOT


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image'])
    assert image.name=='recovery-dijun-unified-format-transition.img'
    assert sha(image)==index['image_sha256']
    sources=json.loads(image.with_name(image.stem+'-sources.json').read_text())
    assert sources['image_sha256']==sha(image) and len(sources['files'])==791
    for path,digest in sources['files'].items():assert sha(path)==digest,path
    path=ROOT/'logs/format-tool-chain.json';report=json.loads(path.read_text())
    assert report['status']=='PASS' and report['image_sha256']==sha(image)
    for file,digest in report['sources'].items():assert sha(file)==digest,file
    assert len(report['cases'])==6 and all(c['status']=='PASS' and all(c['checks'].values()) for c in report['cases'])
    cases={c['name']:c for c in report['cases']}
    f2=['make_f2fs','-g','android','-O','project_quota,extra_attr','/fixtures/target.img','65536','sload_f2fs','-t','/data','/fixtures/target.img','fsck.f2fs','-a','/fixtures/target.img']
    for name in ['to-f2fs','global-rmrf','partition-rmrf']:assert cases[name]['invocations']==f2
    assert cases['to-ext4']['invocations']==['mke2fs','-t','ext4','-b','4096','-I','512','-O','metadata_csum,64bit,extent','/fixtures/target.img','65536','e2fsck','-fp','/fixtures/target.img']
    assert cases['to-ext4']['checks']['independent_payload_readback']
    assert cases['missing-tool']['invocations']==[]
    assert cases['too-small']['invocations']==['make_f2fs','-g','android','-O','project_quota,extra_attr','/fixtures/target.img','1024']
    entries={e[0]:e[-1] for e in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])}
    for name,digest in report['ramdisk_files'].items():assert hashlib.sha256(entries[name]).hexdigest()==digest,name
    assert all(t['exit']==0 for t in report['tool_transcripts'])
    assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
    result=dict(status='PASS',scope=__doc__,image_sha256=sha(image),production_sources=791,cases=6,evidence_sha256=sha(path),production_changed=False,hardware_testing=False,full_filesystem_lifecycle=False)
    (ROOT/'logs/format-tool-chain-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: actual ARM64 format/repair chain6; unchanged image791 sources; no production fix or complete mount/GUI claim')

if __name__=='__main__':main()
