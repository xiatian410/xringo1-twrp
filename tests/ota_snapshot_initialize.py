#!/usr/bin/env python3
"""Original ARM64 SnapshotManager allocates/initializes stock-manifest COW files.

Explicit synthetic32GiB LP, regular-file DM view and HAL/kernel/ImageManager
boundaries. Real COW writer/reader, LP/state writes and recreated completion.
IsTestDevice=true disables scratch and daemon startup; no physical map/device,
actual source layout, payload operation, init, slot switch or full OTA install.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from ota_vabc_session import ROOT,ANDROID,build
from ota_snapshot_allocate import sha
from firmware_facts import boot_parts,ramdisk_entries


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,default=ROOT/'logs/ota-snapshot-initialize.json')
    p.add_argument('--snapshot-source',type=Path)
    args=p.parse_args()
    index=json.loads((ROOT/'simulation-report.json').read_text());image=Path(index['image']);assert sha(image)==index['image_sha256']
    ref=json.loads((ROOT/'logs/ota-snapshot-postinstall.json').read_text())
    dependencies={p:sha(p) for p in ref['dependencies']};qemu=ROOT/'tools/qemu-user/qemu-aarch64'
    assert dependencies[str(qemu)]==ref['dependencies'][str(qemu)]
    fixture=ROOT/'tests/ota_snapshot_initialize.cpp'
    source=(args.snapshot_source or ANDROID/'system/core/fs_mgr/libsnapshot/snapshot.cpp').resolve()
    sources={str(p):sha(p) for p in [Path(__file__),fixture,ROOT/'tests/ota_snapshot_allocate.cpp',ROOT/'tests/ota_snapshot_allocate.py',ROOT/'tests/ota_snapshot_finish.cpp',ROOT/'tests/ota_vabc_session.py',ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py',source]}
    manifest=ROOT/'firmware/samples/os4-stable/payload-manifest.pb';inventory=manifest.with_name('inventory.json')
    assert sha(manifest)==json.loads(inventory.read_text())['manifest_sha256']
    with tempfile.TemporaryDirectory(prefix='snapshot-initialize-',dir=ROOT/'logs') as tmp:
        work=Path(tmp);command=[a for a in ref['compile_template'] if a!='-DNDEBUG']
        command.insert(1,'-I'+str(ROOT/'tests'));command.insert(-1,'-UNDEBUG')
        command[command.index('-o')+1]=str(work/'fixture.o');command[command.index('-MF')+1]=str(work/'fixture.d');command[-1]=str(fixture);build(command)
        link=ref['link_command'].copy();old=next(a for a in link if a.endswith('/fixture.o'));link[link.index(old)]=str(work/'fixture.o');link[link.index('-o')+1]=str(work/'test')
        extra_command=None
        if args.snapshot_source:
            obj='out/soong/.intermediates/system/core/fs_mgr/libsnapshot/libsnapshot_nobinder/android_recovery_arm64_armv8-a_static/obj/system/core/fs_mgr/libsnapshot/snapshot.o'
            commands=subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja','-f','out/combined-twrp_dijun.ninja','-t','commands',obj],cwd=ANDROID,text=True)
            row=next(r for r in commands.splitlines() if r.endswith(' system/core/fs_mgr/libsnapshot/snapshot.cpp'))
            extra_command=shlex.split(row)[1:] if row.startswith('PWD=') else shlex.split(row)
            extra_command[extra_command.index('-o')+1]=str(work/'snapshot.o');extra_command[extra_command.index('-MF')+1]=str(work/'snapshot.d');extra_command.insert(-1,'-I'+str(ANDROID/'system/core/fs_mgr/libsnapshot'));extra_command[-1]=str(source);build(extra_command)
            link.insert(link.index(str(work/'fixture.o'))+1,str(work/'snapshot.o'))
        for depfile in work.glob('*.d'):
            for name in shlex.split(depfile.read_text().replace('\\\n',' ').split(':',1)[1]):
                dep=ANDROID/name
                if dep.is_file():sources[str(dep)]=sha(dep)
        link+=['-Wl,--wrap=_ZN7android2dm12DeviceMapper15GetTargetByNameERKNSt3__112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEEPNS0_16DmTargetTypeInfoE'];build(link)
        elf=(work/'test').read_bytes();assert elf[:6]==b'\x7fELF\x02\x01' and elf[18:20]==b'\xb7\0'
        jail=work/'jail';entries={}
        for n,m,*rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(m) and (n=='system/bin/linker64' or n.startswith('system/lib64/') and n.endswith('.so')):
                dest=jail/'android'/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(rest[-1]);dest.chmod(m&0o777);entries[n]=hashlib.sha256(rest[-1]).hexdigest()
        (jail/'dev').mkdir();(jail/'dev/null').touch()
        shutil.copyfile(qemu,jail/'qemu');(jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'test',jail/'test');(jail/'test').chmod(0o755)
        def isolate():os.chroot(jail);os.chdir('/')
        cases=[]
        for name in ['normal','path-error','header-sync-error']:
            shutil.rmtree(jail/'work',ignore_errors=True);(jail/'work').mkdir();shutil.copyfile(manifest,jail/'work/manifest.pb')
            child=subprocess.run(['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64','/android/system/bin/linker64','/test',name],preexec_fn=isolate,capture_output=True,text=True,timeout=45)
            cases.append(dict(name=name,status='PASS' if child.returncode==0 and 'PASS '+name in child.stdout else 'FAIL',returncode=child.returncode,stdout=child.stdout,stderr=child.stderr));print(cases[-1]['status'],name,flush=True)
        report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,sources=sources,dependencies=dependencies,compile_command=command,snapshot_compile_command=extra_command,link_command=link,image=str(image),image_sha256=sha(image),image_entries=entries,manifest_sha256=sha(manifest),inventory_sha256=sha(inventory),fixture_elf_machine=183,fixture_sha256=hashlib.sha256(elf).hexdigest(),snapshot_override=str(source) if args.snapshot_source else None,cases=cases,actual_snapshot_manager=True,cow_writer_reader_executed=True,synthetic_layout=True,file_mapping_model=True,scratch_and_daemon_disabled_for_test=True,actual_kernel_mapping=False,full_ota_install=False)
        args.report.write_text(json.dumps(report,indent=2)+'\n');return 0 if report['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
