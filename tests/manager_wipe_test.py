#!/usr/bin/env python3
"""Dalvik and media manager wipe to production backend LIST/run terminal states.

Private chroot ordinary files, uid/gid65534, actual filesystem permission errors,
RemoveDir and manager methods; media root inode/user xattr readback. Mounts, MTP,
metadata and presentation are fixtures. User xattr is NOT real fscrypt policy.
No actual mount, phone, full GUI/start/thread, I/O kernel or power-loss test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--before',action='store_true');args=parser.parse_args()
    manager=ROOT/'logs/manager-wipe-before/partitionmanager.cpp' if args.before else SRC/'partitionmanager.cpp'
    selected={manager:['int TWPartitionManager::WipeDalvikCache()', 'int TWPartitionManager::WipeMediaFromData()'],SRC/'partition.cpp':['void TWPartition::RecreateMediaFolder()'],SRC/'twrp_functions.cpp':['int TWFunc::RemoveDir('],SRC/'gui2/backend/twrp_wipe_backend.cpp':['bool wipe_target_allowed(', 'int wipe(', 'void twrp_wipe_backend::report_item(', 'void twrp_wipe_backend::run(']}
    bodies=[]
    for path,signatures in selected.items():
        for sig in signatures:
            body=method(path.read_text(),sig)
            if path.name=='twrp_wipe_backend.cpp':body='namespace gui2_backend {\n'+body+'\n}'
            bodies.append(body)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='manager-wipe-') as temp:
        work=Path(temp);(work/'methods.inc').write_text('\n\n'.join(bodies));binary=work/'test'
        cmd=['g++','-std=c++23','-O1','-g','-static','-pthread','-I'+str(work),'-I'+str(SRC/'gui2/backend'),str(ROOT/'tests/manager_wipe_test.cpp'),'-o',str(binary)]
        subprocess.run(cmd,check=True)
        for name in ['dalvik-success','dalvik-cache','dalvik-missing','dalvik-delete-denied','dalvik-query-denied','dalvik-data-mount-denied','dalvik-cache-mount-denied','dalvik-sd-mount-denied','media-fbe','media-legacy','media-delete-denied','media-missing','media-symlink','media-mount-denied','media-unsupported','media-no-data']:
            jail=work/name;jail.mkdir();jail.chmod(0o755);(jail/'test').write_bytes(binary.read_bytes());(jail/'test').chmod(0o755)
            def isolate():os.chroot(jail);os.chdir('/')
            run=subprocess.run(['/test',name],preexec_fn=isolate,capture_output=True,text=True,timeout=10)
            cases.append(dict(name=name,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,stdout=run.stdout,stderr=run.stderr));print(name,cases[-1]['status'],flush=True)
    paths=[*selected,Path(__file__),ROOT/'tests/manager_wipe_test.cpp',ROOT/'tests/nested_partition_path_test.py',SRC/'gui2/backend/wipe_backend.h',SRC/'gui2/backend/mount_backend.h']
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',baseline=args.before,scope=__doc__,cases=cases,compile_command=cmd,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (ROOT/'logs'/('manager-wipe-before.json' if args.before else 'manager-wipe.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
