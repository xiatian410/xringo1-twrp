#!/usr/bin/env python3
"""Original format/repair call chain executes current-image ARM64 tools on files.

Host C++ Wipe/helpers/manager/changefilesystem/Repair/ExecCmd/WaitForChild run in
private chroot. Exact tool argv pass through QEMU launchers to delivered linker,
libraries and ARM64 tools. Device resolution/unmount/block-size ioctl (stat),
properties, empty /proc/mounts and metadata/presentation are explicit fixtures; no physical mount,
full ARM Recovery, GUI, fscrypt or power-loss proof. Optional --selinux executes
the active e2fsdroid branch with host libselinux lookup, delivered text contexts
and actual ARM64 image labeling; it does not test kernel SELinux enforcement.
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


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=ROOT/'logs/format-tool-chain.json')
    parser.add_argument('--selinux',action='store_true',help='Only test ext4 labeling and policy-file failures; no ordinary tool regression rerun')
    args=parser.parse_args()
    index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image'])
    assert sha(image)==index['image_sha256']
    qemu=ROOT/'tools/qemu-user/qemu-aarch64';qsource=qemu.parent/'source.json'
    assert sha(qemu)==json.loads(qsource.read_text())['binary_sha256']
    clang=Path('/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++')
    shell=Path('/bin/sh').resolve();debugfs=Path(shutil.which('debugfs'))
    selected={
        SRC/'partition.cpp':['bool TWPartition::Wipe(const std::string&','bool TWPartition::WipeExtfs(','bool TWPartition::WipeExt4()','bool TWPartition::WipeFat()','bool TWPartition::WipeExfat()','bool TWPartition::WipeF2fs()','bool TWPartition::WipeNtfs()','bool TWPartition::Repair()'],
        SRC/'partitionmanager.cpp':['bool TWPartitionManager::MatchesPath(','TWPartition* TWPartitionManager::FindPartitionByPath(','int TWPartitionManager::WipeByPath(const std::string& Path,'],
        SRC/'gui2/backend/twrp_tools_backend.cpp':['int changefilesystem('],
        SRC/'twrp_functions.cpp':['bool TWFunc::IsPathExists(','std::string TWFunc::GetRootPath(','int TWFunc::ExecCmd(const std::string& cmd, std::string& result,','int TWFunc::ExecCmd(const std::string& cmd, const bool show_errors)','int TWFunc::WaitForChild(const pid_t pid,'],
    }
    bodies=[method(p.read_text(),s) for p,signatures in selected.items() for s in signatures]
    cases=[];transcripts=[];extracted={};deps={shell};launchers={}
    def deps_for(p):
        for line in subprocess.check_output(['ldd',str(p)],text=True).splitlines():
            found=re.search(r'(/[^\s()]+)',line)
            if found:deps.add(Path(found[1]))
    deps_for(shell)
    with tempfile.TemporaryDirectory(prefix='format-tool-chain-') as temp:
        work=Path(temp);jail=work/'jail';jail.mkdir();android=jail/'android'
        entries=ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk'])
        policy=None;policy_name=None;split_policies={}
        for name,mode,*rest in entries:
            if name in ['file_contexts','prebuilt_file_contexts'] and stat.S_ISREG(mode):
                if policy is None or name=='prebuilt_file_contexts':policy=rest[-1];policy_name=name
            if name in ['plat_file_contexts','system_ext_file_contexts','product_file_contexts','vendor_file_contexts','odm_file_contexts'] and stat.S_ISREG(mode):
                split_policies[name]=rest[-1]
            if not name.startswith(('system/bin/','system/lib64/','system/etc/')) or not stat.S_ISREG(mode):continue
            relative=Path(name);assert not relative.is_absolute() and '..' not in relative.parts
            dest=android/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(rest[-1]);dest.chmod(mode&0o777);extracted[name]=sha(dest)
        (work/'methods.inc').write_text('\n\n'.join(bodies));binary=jail/'test'
        cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-I'+str(work),str(ROOT/'tests/format_tool_chain_test.cpp'),'-Wl,-rpath,'+str(clang.parent.parent/'lib/x86_64-unknown-linux-gnu'),'-o',str(binary)]
        if args.selinux:
            assert policy is not None
            cmd+=['-DTEST_SELINUX','-lselinux']
            extracted[policy_name]=hashlib.sha256(policy).hexdigest()
            assert len(split_policies)==5
            extracted.update({name:hashlib.sha256(data).hexdigest() for name,data in split_policies.items()})
        subprocess.run(cmd,check=True);deps_for(binary)
        for dep in deps:
            dest=jail/dep.relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dep,dest);dest.chmod(0o755)
        (jail/'bin').mkdir(exist_ok=True);shutil.copyfile(shell,jail/'bin/sh');(jail/'bin/sh').chmod(0o755)
        shutil.copyfile(qemu,jail/'qemu');(jail/'qemu').chmod(0o755)
        (jail/'dev').mkdir();(jail/'dev/null').touch()
        # Explicit empty mount-table fixture; no procfs mount or host mounts read.
        (jail/'proc').mkdir();(jail/'proc/mounts').write_text('')
        (jail/'system/bin').mkdir(parents=True);(jail/'system/bin/sh').symlink_to('/bin/sh')
        tools=['mke2fs','e2fsdroid','make_f2fs','sload_f2fs','e2fsck','fsck.f2fs']
        for tool in tools:
            assert (android/'system/bin'/tool).is_file()
            text=f'''#!/bin/sh
printf '%s\\n' '{tool}' "$@" >> /invocations.txt
LD_LIBRARY_PATH=/android/system/lib64 MKE2FS_CONFIG=/android/system/etc/mke2fs.conf exec /qemu -L /android /android/system/bin/linker64 /android/system/bin/{tool} "$@"
'''
            launcher=jail/'system/bin'/tool;launcher.write_text(text);launcher.chmod(0o755);launchers[tool]=text
        fixtures=jail/'fixtures';fixtures.mkdir();source=fixtures/'source';source.mkdir()
        payload=b'actual format chain readback\n'*1024+bytes(range(256));(source/'payload.bin').write_bytes(payload)
        env={k:v for k,v in os.environ.items() if not k.startswith(('LD_','QEMU_','MKE2FS_'))};env['PATH']='/system/bin:/bin:'+os.environ['PATH']
        pristine=fixtures/'pristine.img'
        with pristine.open('xb') as f:f.truncate(256<<20)
        def target(tool,args,expected=0):
            # Every explicit target path is private and selected by this script.
            assert tool in tools
            result=subprocess.run(['chroot',str(jail),'/system/bin/'+tool,*args],env=env,capture_output=True,text=True,timeout=60)
            transcripts.append(dict(tool=tool,args=args,exit=result.returncode,stdout=result.stdout,stderr=result.stderr))
            assert result.returncode==expected,transcripts[-1]
            return result
        target('mke2fs',['-t','ext4','-b','4096','-I','512','/fixtures/pristine.img','65536'])
        (jail/'invocations.txt').unlink()
        names=['label-data','label-system','label-combined-missing','label-missing','label-invalid'] if args.selinux else ['to-f2fs','to-ext4','global-rmrf','partition-rmrf','too-small','missing-tool']
        for name in names:
            path=fixtures/'target.img'
            if name=='too-small':
                with path.open('wb') as f:f.truncate(4<<20)
            else:shutil.copyfile(pristine,path)
            if name=='to-ext4' or args.selinux:target('make_f2fs',['-g','android','/fixtures/target.img','65536'])
            if args.selinux:
                (jail/'file_contexts').write_bytes(policy)
                for policy_path,data in split_policies.items():(jail/policy_path).write_bytes(data)
            before=sha(path);record=jail/'invocations.txt';record.unlink(missing_ok=True)
            launcher=jail/'system/bin/make_f2fs'
            if name=='missing-tool':launcher.rename(launcher.with_suffix('.absent'))
            run=subprocess.run(['chroot',str(jail),'/test',name],env=env,capture_output=True,text=True,timeout=90)
            if name=='missing-tool':launcher.with_suffix('.absent').rename(launcher)
            invoked=record.read_text().splitlines() if record.exists() else []
            if run.returncode!=0:raise AssertionError((name,run.returncode,run.stdout,run.stderr,invoked))
            ok=name not in ['too-small','missing-tool','label-missing','label-invalid'];checks={'caller_status':run.returncode==0,'missing_tool_unchanged':name!='missing-tool' or sha(path)==before}
            if args.selinux:
                checks['formatted_ext4']=path.read_bytes()[1080:1082]==b'\x53\xef'
                checks['disk_changed']=sha(path)!=before
                checks['original_tool_arguments']=invoked[:12]==['mke2fs','-t','ext4','-b','4096','-I','512','-O','metadata_csum,64bit,extent','/fixtures/target.img','65536','e2fsdroid'] and invoked[12:]==['-e','-S','/file_contexts','-a','/' if name=='label-system' else '/data','/fixtures/target.img']+(['e2fsck','-fp','/fixtures/target.img'] if ok else [])
                # Independent ext reader: inspect bytes stored in the image,
                # rather than treating a successful tool exit as proof.
                read=subprocess.run([str(debugfs),'-R','ea_list /',str(path)],capture_output=True,text=True,timeout=15)
                root_context='u:object_r:rootfs:s0' if name=='label-system' else 'u:object_r:system_data_root_file:s0'
                checks['root_label']=read.returncode==0 and ('security.selinux' in read.stdout and root_context in read.stdout if ok else 'security.selinux' not in read.stdout)
                if not ok:
                    checks['failure_propagated']='RESULT status=1 filesystem=ext4 repair=0' in run.stdout and 'e2fsck' not in invoked
                cases.append(dict(name=name,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,invocations=invoked,stdout=run.stdout,stderr=run.stderr,label_readback=dict(stdout=read.stdout,stderr=read.stderr)))
                print(name,cases[-1]['status'],checks,flush=True)
                continue
            if ok:
                blob=path.read_bytes();checks['disk_changed']=sha(path)!=before
                if name=='to-ext4':
                    checks['ext4_magic']=blob[1080:1082]==b'\x53\xef';checks['formatter_checker_invoked']=invoked[:1]==['mke2fs'] and 'e2fsck' in invoked
                    target('e2fsdroid',['-e','-f','/fixtures/source','/fixtures/target.img'])
                    target('e2fsck',['-fn','/fixtures/target.img'])
                    out=fixtures/'readback.bin'
                    read=subprocess.run([str(debugfs),'-R',f'dump /payload.bin {out}',str(path)],capture_output=True,text=True,timeout=15)
                    checks['independent_payload_readback']=read.returncode==0 and out.read_bytes()==payload
                else:
                    checks['f2fs_magic']=blob[1024:1028]==b'\x10\x20\xf5\xf2';checks['formatter_loader_checker_invoked']=invoked[:1]==['make_f2fs'] and 'sload_f2fs' in invoked and 'fsck.f2fs' in invoked
                    target('sload_f2fs',['-f','/fixtures/source','/fixtures/target.img'])
                    stable=sha(path);target('fsck.f2fs',['-f','--dry-run','/fixtures/target.img']);checks['populated_check_nonmutating']=sha(path)==stable
            elif name=='missing-tool':checks['no_command']=not invoked
            else:checks['actual_tool_rejection']='make_f2fs' in invoked and 'sload_f2fs' not in invoked and 'fsck.f2fs' not in invoked
            cases.append(dict(name=name,status='PASS' if all(checks.values()) else 'FAIL',checks=checks,invocations=invoked,stdout=run.stdout,stderr=run.stderr))
            print(name,cases[-1]['status'],checks,flush=True)
    paths=[*selected,Path(__file__),ROOT/'tests/format_tool_chain_test.cpp',ROOT/'tests/nested_partition_path_test.py',ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py',SRC/'partitions.hpp',image,qemu,qsource,clang,debugfs,*deps]
    if args.selinux:paths += [Path('/usr/include/selinux/label.h'),Path('/usr/include/selinux/selinux.h')]
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,image_sha256=index['image_sha256'],cases=cases,tool_transcripts=transcripts,launchers=launchers,ramdisk_files=extracted,sources={str(p):sha(p) for p in paths})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
