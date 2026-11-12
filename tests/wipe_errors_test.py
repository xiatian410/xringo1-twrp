#!/usr/bin/env python3
"""Real directory permission failures to production wipe result publication.

Private chroots and unprivileged uid, ordinary files only. Execute RemoveDir,
three partition wipe helpers, real manager routing and backend LIST/run/report.
Mount/device resolution, remaining wipe modes and presentation are fixtures;
run is invoked synchronously, not a complete GUI or worker-start lifecycle.
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
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',action='store_true')
    a=p.parse_args()
    base=ROOT/'logs/wipe-errors-before' if a.before else SRC
    selected={
        base/'twrp_functions.cpp':['int TWFunc::RemoveDir('],
        base/'partition.cpp':['bool TWPartition::WipeRmrf()', 'bool TWPartition::WipeAndSec()', 'bool TWPartition::WipeDataCache()'],
        SRC/'partitionmanager.cpp':['bool TWPartitionManager::MatchesPath(', 'TWPartition* TWPartitionManager::FindPartitionByPath(', 'int TWPartitionManager::WipeByPath(const std::string& Path) const'],
        SRC/'gui2/backend/twrp_wipe_backend.cpp':['bool wipe_target_allowed(', 'int wipe(', 'void twrp_wipe_backend::report_item(', 'void twrp_wipe_backend::run('],
    }
    bodies=[]
    for path,signatures in selected.items():
        for sig in signatures:
            body=method(path.read_text(),sig)
            if 'twrp_wipe_backend.cpp' in str(path):body='namespace gui2_backend {\n'+body+'\n}'
            bodies.append(body)
    cases=[]
    with tempfile.TemporaryDirectory(prefix='wipe-errors-') as temp:
        work=Path(temp)
        (work/'methods.inc').write_text('\n\n'.join(bodies))
        binary=work/'test'
        cmd=['g++','-std=c++23','-O1','-g','-static','-pthread','-I'+str(work),'-I'+str(SRC/'gui2/backend'),str(ROOT/'tests/wipe_errors_test.cpp'),'-o',str(binary)]
        subprocess.run(cmd,check=True)
        for name in ['rm-success','rm-denied','rm-missing','mount-denied','secure-success','secure-denied','secure-missing','cache-success','cache-denied','cache-missing','remove-first-error']:
            jail=work/name;jail.mkdir();jail.chmod(0o755)
            (jail/'test').write_bytes(binary.read_bytes());(jail/'test').chmod(0o755)
            def isolate():
                os.chroot(jail);os.chdir('/')
            r=subprocess.run(['/test',name],preexec_fn=isolate,capture_output=True,text=True,timeout=10)
            cases.append(dict(name=name,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
            print(name,cases[-1]['status'],flush=True)
    sources=[*selected,Path(__file__),ROOT/'tests/wipe_errors_test.cpp',ROOT/'tests/nested_partition_path_test.py',SRC/'gui2/backend/wipe_backend.h',SRC/'gui2/backend/mount_backend.h']
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,baseline=a.before,cases=cases,compile_command=cmd,sources={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources})
    (ROOT/'logs'/('wipe-errors-before.json' if a.before else 'wipe-errors.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
