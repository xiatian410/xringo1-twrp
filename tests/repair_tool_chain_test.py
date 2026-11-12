#!/usr/bin/env python3
"""Join production repair wrapper/partition lookup/Repair/ExecCmd to delivered ARM64 e2fsck.

All targets are newly created regular files in a private chroot. Partition
unmount/device resolution and operation presentation are explicit fixtures;
there is no GUI, real mount, physical block device, phone, FBE or power-loss test.
The /system/bin/e2fsck compatibility launcher execs the same-image ARM64 tool
through QEMU and the same-image Android linker/libraries, preserving its status.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

from nested_partition_path_test import ROOT, SRC, method
sys.path.insert(0,str(ROOT/'scripts'))
from firmware_facts import boot_parts, ramdisk_entries

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'logs/repair-tool-chain.json')
    args=parser.parse_args()
    index=json.loads((ROOT/'simulation-report.json').read_text())
    image=Path(index['image']); assert image.is_file() and sha(image)==index['image_sha256']
    qemu=ROOT/'tools/qemu-user/qemu-aarch64'; qemu_source=qemu.parent/'source.json'
    assert sha(qemu)==json.loads(qemu_source.read_text())['binary_sha256']
    debugfs=Path(shutil.which('debugfs')); shell=Path('/bin/sh').resolve()
    tools_source=SRC/'gui2/backend/twrp_tools_backend.cpp'
    bodies=[]
    for path,signatures in [
        (SRC/'twrp_functions.cpp',['bool TWFunc::IsPathExists(', 'std::string TWFunc::GetRootPath(',
                                  'int TWFunc::ExecCmd(const std::string& cmd, std::string& result,']),
        (SRC/'partitionmanager.cpp',['bool TWPartitionManager::MatchesPath(',
                                    'TWPartition* TWPartitionManager::FindPartitionByPath(',
                                    'int TWPartitionManager::RepairByPath(']),
        (SRC/'partition.cpp',['bool TWPartition::Repair()']),
        (tools_source,['int repair('])]:
        text=path.read_text()
        bodies.extend(method(text,sig) for sig in signatures)
    dependencies={shell}
    for line in subprocess.check_output(['ldd',str(shell)],text=True).splitlines():
        match=re.search(r'(/[^\s()]+)',line)
        if match: dependencies.add(Path(match[1]))
    cases=[]; transcripts=[]; extracted={}
    _,parts=boot_parts(image.read_bytes())
    entries=ramdisk_entries(parts['ramdisk'])
    with tempfile.TemporaryDirectory(prefix='repair-tool-chain-') as tmp:
        work=Path(tmp); jail=work/'jail'; android=jail/'android'; android.mkdir(parents=True)
        for name,mode,*rest in entries:
            if not name.startswith(('system/bin/','system/lib64/','system/etc/')) or not stat.S_ISREG(mode): continue
            relative=Path(name); assert not relative.is_absolute() and '..' not in relative.parts
            target=android/relative; target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(rest[-1]); target.chmod(mode&0o777)
            extracted[name]=sha(target)
        (jail/'bin').mkdir(); shutil.copyfile(shell,jail/'bin/sh'); (jail/'bin/sh').chmod(0o755)
        for dep in dependencies-{shell}:
            target=jail/dep.relative_to('/'); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(dep,target); target.chmod(0o755)
        shutil.copyfile(qemu,jail/'qemu'); (jail/'qemu').chmod(0o755)
        (jail/'dev').mkdir(); (jail/'dev/null').touch() # ordinary private file, not a host device
        (jail/'system/bin').mkdir(parents=True)
        launcher=jail/'system/bin/e2fsck'
        launcher_text='''#!/bin/sh
printf '%s\\n' "$@" >> /checker-arguments.txt
LD_LIBRARY_PATH=/android/system/lib64 exec /qemu -L /android /android/system/bin/linker64 /android/system/bin/e2fsck "$@"
'''
        launcher.write_text(launcher_text); launcher.chmod(0o755)
        (work/'methods.inc').write_text('\n\n'.join(bodies))
        binary=jail/'repair-test'
        subprocess.run(['g++','-std=c++23','-O1','-g','-static','-pthread','-I'+str(work),
                        str(ROOT/'tests/repair_tool_chain_test.cpp'),'-o',str(binary)],check=True)
        fixtures=jail/'fixtures'; fixtures.mkdir()
        source=fixtures/'source'; source.mkdir()
        payload=b'dijun repair call chain\n'*1024+bytes(range(256)); (source/'payload.bin').write_bytes(payload)
        pristine=fixtures/'pristine.img'
        with pristine.open('xb') as stream: stream.truncate(64<<20)
        env={k:v for k,v in os.environ.items() if not k.startswith(('LD_','QEMU_'))}
        env.update(LD_LIBRARY_PATH=str(android/'system/lib64'),MKE2FS_CONFIG=str(android/'system/etc/mke2fs.conf'))
        def target_tool(tool,operands):
            assert tool in ['mke2fs','e2fsdroid','e2fsck']
            run=subprocess.run([str(qemu),'-L',str(android),str(android/'system/bin/linker64'),
                                str(android/'system/bin'/tool),*map(str,operands)],
                               env=env,capture_output=True,text=True,timeout=45)
            transcripts.append(dict(tool=tool,operands=list(map(str,operands)),exit=run.returncode,
                                    stdout=run.stdout,stderr=run.stderr))
            assert run.returncode==0,transcripts[-1]
        target_tool('mke2fs',['-t','ext4','-b','4096','-I','512','-O','metadata_csum,64bit,extent',pristine,'16384'])
        target_tool('e2fsdroid',['-e','-f',source,pristine])
        target_tool('e2fsck',['-fn',pristine])
        invalid=fixtures/'invalid.img'
        with invalid.open('xb') as stream: stream.truncate(4<<20)
        invalid_hash=sha(invalid)
        for name in ['clean','corrected','invalid','missing-checker','unmount-denied','unknown-target','child-invalid']:
            image_target=fixtures/'target.img'; shutil.copyfile(invalid if name=='invalid' else pristine,image_target)
            if name=='corrected':
                mutation=subprocess.run([str(debugfs),'-w','-R','set_inode_field /payload.bin links_count 7',str(image_target)],
                                        capture_output=True,text=True,timeout=15)
                assert mutation.returncode==0 and 'File not found' not in mutation.stderr
                transcripts.append(dict(host='debugfs-mutation',exit=mutation.returncode,stdout=mutation.stdout,stderr=mutation.stderr))
            before=sha(image_target)
            record=jail/'checker-arguments.txt'; record.unlink(missing_ok=True)
            if name=='missing-checker': launcher.rename(launcher.with_suffix('.absent'))
            run=subprocess.run(['chroot',str(jail),'/repair-test',name,'1' if name in ['clean','corrected'] else '0'],
                               env={k:v for k,v in env.items() if not k.startswith(('LD_','MKE2FS_'))},
                               capture_output=True,text=True,timeout=45)
            if name=='missing-checker': launcher.with_suffix('.absent').rename(launcher)
            invoked=record.read_text().splitlines() if record.exists() else []
            raw_statuses=[int(x) for x in re.findall(r'e2fsck repair wait status: (-?\d+)',run.stdout)]
            expected_status={'clean':[0],'corrected':[256],'invalid':[2048],
                             'missing-checker':[],'unmount-denied':[],'unknown-target':[],
                             'child-invalid':[0,2048]}[name]
            expected_args=['-fp','/fixtures/target.img'] if expected_status else []
            if name=='child-invalid': expected_args+=['-fp','/fixtures/invalid.img']
            checks={'harness':run.returncode==0,'checker_arguments':invoked==expected_args,
                    'actual_wait_status':raw_statuses==expected_status,
                    'unselected_image_absent':not (fixtures/'never-open.img').exists()}
            if name in ['missing-checker','unmount-denied','unknown-target','invalid']:
                checks['target_unchanged']=sha(image_target)==before
            if name=='corrected':
                checks['checker_changed_metadata']=sha(image_target)!=before
                checks['checker_reported_fixed']='FIXED' in run.stdout
                target_tool('e2fsck',['-fn',image_target])
                out=fixtures/'readback.bin'
                readback=subprocess.run([str(debugfs),'-R',f'dump /payload.bin {out}',str(image_target)],
                                        capture_output=True,text=True,timeout=15)
                checks['independent_content_readback']=readback.returncode==0 and out.read_bytes()==payload
            cases.append(dict(case=name,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
                              checker_arguments=invoked,actual_wait_status=raw_statuses,stdout=run.stdout,stderr=run.stderr))
            print(name,cases[-1]['status'],checks,flush=True)
        assert sha(invalid)==invalid_hash
    sources=[image,qemu,qemu_source,debugfs,Path(__file__).resolve(),ROOT/'tests/repair_tool_chain_test.cpp',
             ROOT/'tests/nested_partition_path_test.py',ROOT/'scripts/firmware_facts.py',
             ROOT/'scripts/acquire_firmware.py',SRC/'partition.cpp',SRC/'partitionmanager.cpp',
             SRC/'twrp_functions.cpp',tools_source,*sorted(dependencies)]
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,
                image_sha256=index['image_sha256'],cases=cases,tool_transcripts=transcripts,
                launcher=launcher_text,ramdisk_files=extracted,
                sources={str(p):sha(p) for p in sources})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__':
    raise SystemExit(main())
