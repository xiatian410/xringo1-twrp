#!/usr/bin/env python3
"""Production Wipe dispatch and format helpers through manager/backend result.

Command execution, capacity/device discovery, unmount, properties and metadata
are explicit fixtures. No mkfs subprocess, physical device, mount, complete GUI
or real filesystem conversion; validates conversion selection/failure/state.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT,SRC,method


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',action='store_true');a=p.parse_args()
    partition=ROOT/'logs/format-transition-before/partition.cpp' if a.before else SRC/'partition.cpp'
    selected={partition:['bool TWPartition::Wipe(const std::string&', 'bool TWPartition::WipeExtfs(', 'bool TWPartition::WipeExt4()', 'bool TWPartition::WipeFat()', 'bool TWPartition::WipeExfat()', 'bool TWPartition::WipeF2fs()', 'bool TWPartition::WipeNtfs()'],SRC/'partitionmanager.cpp':['bool TWPartitionManager::MatchesPath(', 'TWPartition* TWPartitionManager::FindPartitionByPath(', 'int TWPartitionManager::WipeByPath(const std::string& Path,'],SRC/'gui2/backend/twrp_tools_backend.cpp':['int changefilesystem(']}
    bodies=[method(path.read_text(),sig) for path,sigs in selected.items() for sig in sigs]
    cases=[]
    with tempfile.TemporaryDirectory(prefix='format-transition-') as temp:
        work=Path(temp);(work/'methods.inc').write_text('\n\n'.join(bodies));binary=work/'test'
        # libc++ supplies production std::format; host libstdc++ lacks it here.
        clang=Path('/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++')
        cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-I'+str(work),str(ROOT/'tests/format_transition_test.cpp'),'-Wl,-rpath,'+str(clang.parent.parent/'lib/x86_64-unknown-linux-gnu'),'-o',str(binary)]
        subprocess.run(cmd,check=True)
        names=['f2fs-success','exfat-success','ntfs-success','fat-success','ext-success','from-tntfs','from-mifs','global-rmrf','partition-rmrf','same-rmrf','f2fs-missing','ext-missing','fat-missing','exfat-missing','ntfs-missing','f2fs-fallback','ext-fallback','fat-fallback','f2fs-failed','exfat-failed','ntfs-failed','ext-failed','unmount-denied','not-present','not-wipeable']
        for name in names:
            run=subprocess.run([str(binary),name],capture_output=True,text=True,timeout=10)
            cases.append(dict(name=name,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,stdout=run.stdout,stderr=run.stderr));print(name,cases[-1]['status'],flush=True)
    paths=[*selected,Path(__file__),ROOT/'tests/format_transition_test.cpp',ROOT/'tests/nested_partition_path_test.py',SRC/'partitions.hpp',clang]
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',baseline=a.before,scope=__doc__,cases=cases,compile_command=cmd,sources={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths})
    (ROOT/'logs'/('format-transition-before.json' if a.before else 'format-transition.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
