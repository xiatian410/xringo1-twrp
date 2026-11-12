#!/usr/bin/env python3
"""Media-preserving wipe with original exclusion policy and real permission failures.

Production recursion/wrapper, exclusion matching, manager routing, LIST/run/report
execute in private chroots after dropping uid/gid. Mount/device resolution,
same-filesystem Wipe dispatch and presentation are fixtures; no actual filesystem
mount, full worker start/GUI, concurrent writers, kernel faults or power-loss.
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',action='store_true')
    args=parser.parse_args()
    base=ROOT/'logs/media-wipe-before' if args.before else SRC
    selected={
        base/'partition.cpp':['bool TWPartition::WipeDataWithoutWipingMedia()', 'bool TWPartition::WipeDataWithoutWipingMediaFunc('],
        SRC/'exclude.cpp':['TWExclude::TWExclude()', 'void TWExclude::add_relative_dir(', 'void TWExclude::add_absolute_dir(', 'bool TWExclude::check_relative_skip_dirs(', 'bool TWExclude::check_absolute_skip_dirs(', 'bool TWExclude::check_skip_dirs('],
        SRC/'twrp_functions.cpp':['std::string TWFunc::RemoveTrailingSlashes('],
        SRC/'partitionmanager.cpp':['bool TWPartitionManager::MatchesPath(', 'TWPartition* TWPartitionManager::FindPartitionByPath(', 'int TWPartitionManager::WipeByPath(const std::string& Path) const'],
        SRC/'gui2/backend/twrp_wipe_backend.cpp':['bool wipe_target_allowed(', 'int wipe(', 'void twrp_wipe_backend::report_item(', 'void twrp_wipe_backend::run('],
    }
    bodies=[]
    for path,signatures in selected.items():
        for sig in signatures:
            body=method(path.read_text(),sig)
            if path.name=='twrp_wipe_backend.cpp':body='namespace gui2_backend {\n'+body+'\n}'
            bodies.append(body)
    retained='bool* retained' in (base/'partition.cpp').read_text()
    cases=[]
    with tempfile.TemporaryDirectory(prefix='media-wipe-') as temp:
        work=Path(temp);(work/'methods.inc').write_text('\n\n'.join(bodies))
        for workaround in [False,True]:
            binary=work/'test'
            cmd=['g++','-std=c++23','-O1','-g','-static','-pthread','-DMEDIA_WIPE_RETAINED='+str(int(retained)), '-I'+str(work),'-I'+str(SRC),'-I'+str(SRC/'gui2/backend'),str(ROOT/'tests/media_wipe_test.cpp'),'-o',str(binary)]
            if workaround:cmd.insert(1,'-DTW_WORKAROUND_BACKUP_BUG')
            subprocess.run(cmd,check=True)
            names=['workaround-directory'] if workaround else ['success','nested-exclusion','relative-exclusion','symlinks','unlink-denied','open-denied','rmdir-denied','nested-unlink-denied','excluded-unreadable','mount-denied','missing-root','workaround-directory']
            for name in names:
                jail=work/(name+str(int(workaround)));jail.mkdir();jail.chmod(0o755)
                (jail/'test').write_bytes(binary.read_bytes());(jail/'test').chmod(0o755)
                def isolate():
                    os.chroot(jail);os.chdir('/')
                run=subprocess.run(['/test',name],preexec_fn=isolate,capture_output=True,text=True,timeout=10)
                cases.append(dict(name=name,workaround=workaround,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,stdout=run.stdout,stderr=run.stderr))
                print(name,workaround,cases[-1]['status'],flush=True)
    paths=[*selected,base/'partitions.hpp',SRC/'exclude.hpp',SRC/'gui2/backend/wipe_backend.h',SRC/'gui2/backend/mount_backend.h',Path(__file__),ROOT/'tests/media_wipe_test.cpp',ROOT/'tests/nested_partition_path_test.py']
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',baseline=args.before,scope=__doc__,cases=cases,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (ROOT/'logs'/('media-wipe-before.json' if args.before else 'media-wipe.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
