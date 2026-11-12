#!/usr/bin/env python3
"""Execute actual TWPartition BackupImage/RestoreImage/RawReadWrite methods.

Uses real disposable file contents and AOSP unique_fd/scopeguard. fstat/BLKGETSIZE64
describe one ordinary fixture file as a partition; BLKDISCARD is emulated on that
file only. File I/O/commit faults and cancellation are injected at syscall boundaries.
Partition discovery, UI progress sink, filesystem-kind lookup and default metadata
are substitutes. No physical block device, Android storage or phone is accessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
BASE=SRC.parents[1]/'system/libbase/include'

def method(text,signature):
    a=text.index(signature);b=text.index('{',a)+1;depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}');b+=1
    return text[a:b]

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=SRC/'partition.cpp')
parser.add_argument('--report',type=Path,default=ROOT/'logs/raw-image.json')
args=parser.parse_args()
body=args.source.read_text()
code='\n\n'.join(method(body,s) for s in ['bool TWPartition::RawReadWrite(', 'bool TWPartition::BackupImage(', 'bool TWPartition::RestoreImage('])
code+='\n'+method((SRC/'partitionmanager.cpp').read_text(),'int TWPartitionManager::CheckBackupCancel(')
common=['normal','no-progress','block-alias','short-read','short-write','read-eintr','write-eintr','sync-eintr','capacity-eintr','read-zero','read-error','write-zero','full-disk','sync-error','close-error','cancel-before','cancel-read','cancel-write','capacity-error','zero-capacity','missing-source','ordinary-file']
cases=[(direction,c,False) for direction in ['backup','restore'] for c in common]
cases += [('backup',c,False) for c in ['cached-size-low','cached-size-high','backup-symlink','same-source','rename-error','directory-sync-error','directory-open-error','cancel-close','optional-metadata-error']]
cases += [('restore',c,False) for c in ['oversized','empty-image','missing-target']]
cases += [('restore',c,True) for c in ['normal','oversized','missing-source','capacity-error','cancel-before','discard-error']]
cases += [('backup',c,False) for c in ['process-exit','commit-exit','roundtrip']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='dijun-raw-',dir='/tmp') as tmp:
    tmp=Path(tmp);harness=tmp/'test.cpp'
    harness.write_text((ROOT/'tests/raw_image_test.cpp').read_text().replace('// PRODUCTION_METHODS',code))
    commands=[]
    for discard in [False,True]:
        cmd=['g++','-std=c++23','-O1','-g','-Wall','-Wextra','-Wno-attributes','-Wno-unused-function',
             '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie',
             '-I'+str(BASE),str(harness),'-o',str(tmp/('test-discard' if discard else 'test'))]
        if discard:cmd.insert(1,'-DTW_ENABLE_BLKDISCARD')
        subprocess.run(cmd,check=True);commands.append(cmd)
    results=[]
    for direction,case,discard in cases:
        name=direction+'-'+case+('-discard' if discard else '')
        wd=tmp/name;wd.mkdir();(wd/'.fixture').touch()
        run=subprocess.run([str(tmp/('test-discard' if discard else 'test')),direction,case],cwd=wd,capture_output=True,text=True,timeout=10)
        passed=run.returncode==0
        observation={}
        if case in ['process-exit','commit-exit']:
            backup=wd/'backup/partition.emmc.win'
            expected=(b'previous complete backup' if case=='process-exit' else
                      bytes((i*97+31)%251 for i in range(2*1024*1024+137)))
            pending=list((wd/'backup').glob('*.tmp.*'))
            passed=(run.returncode==(73 if case=='process-exit' else 74) and
                    backup.read_bytes()==expected and len(pending)==(1 if case=='process-exit' else 0))
            observation=dict(expected_process_exit=73 if case=='process-exit' else 74,
                             backup_sha256=sha(backup),expected_sha256=hashlib.sha256(expected).hexdigest(),
                             temporary_files=[dict(name=p.name,size=p.stat().st_size,sha256=sha(p)) for p in pending])
        results.append(dict(case=name,status='PASS' if passed else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr,observation=observation))
        print(results[-1]['status'],name,flush=True)
    report=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'FAIL',scope=__doc__.strip(),
                cases=results,compile_commands=commands,
                sources={str(p):sha(p) for p in [args.source,SRC/'partitionmanager.cpp',BASE/'android-base/unique_fd.h',BASE/'android-base/scopeguard.h']},
                test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/raw_image_test.cpp']},
                default_build_cases=sum(not c[2] for c in cases),optional_discard_cases=sum(c[2] for c in cases))
    args.report.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(report['status']!='PASS')
