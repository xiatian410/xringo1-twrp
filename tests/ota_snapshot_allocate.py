#!/usr/bin/env python3
"""Actual ARM64 SnapshotManager BeginUpdate/CreateUpdateSnapshots, stock manifest.

Synthetic sparse LP layout (32GiB or nearly full), recorded property/kernel/DM
and ImageManager boundaries. No physical super/free-space/slot/AVB operation.
Stops at mapping denial or allocation errors, never full snapshot/OTA success.
"""
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
from ota_vabc_session import ROOT, ANDROID, build
sys.path.insert(0,str(ROOT/'scripts'))
from firmware_facts import boot_parts,ramdisk_entries


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for data in iter(lambda:f.read(8*1024*1024),b''):h.update(data)
    return h.hexdigest()


def main():
    index=json.loads((ROOT/'simulation-report.json').read_text())
    image=Path(index['image']);assert sha(image)==index['image_sha256']
    ref=json.loads((ROOT/'logs/ota-snapshot-postinstall.json').read_text())
    deps={p:sha(p) for p in ref['dependencies']}
    qemu=ROOT/'tools/qemu-user/qemu-aarch64'
    assert deps[str(qemu)]==ref['dependencies'][str(qemu)]
    sources={str(p):sha(p) for p in [Path(__file__),ROOT/'tests/ota_snapshot_allocate.cpp',
        ROOT/'tests/ota_snapshot_finish.cpp',ROOT/'tests/ota_vabc_session.py',
        ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py',
        *[ANDROID/'system/core/fs_mgr/libsnapshot'/n for n in ['snapshot.cpp','utility.cpp','snapshot_metadata_updater.cpp','partition_cow_creator.cpp']]]}
    manifest=ROOT/'firmware/samples/os4-stable/payload-manifest.pb'
    inventory=manifest.with_name('inventory.json');inv=json.loads(inventory.read_text())
    assert sha(manifest)==inv['manifest_sha256'] and inv['payload_metadata_hash_verified']
    with tempfile.TemporaryDirectory(prefix='snapshot-allocate-',dir=ROOT/'logs') as tmp:
        work=Path(tmp);command=ref['compile_template'].copy()
        command=[a for a in command if a!='-DNDEBUG']
        command.insert(1,'-I'+str(ROOT/'tests'));command.insert(-1,'-UNDEBUG')
        command[command.index('-o')+1]=str(work/'fixture.o')
        command[command.index('-MF')+1]=str(work/'fixture.d')
        command[-1]=str(ROOT/'tests/ota_snapshot_allocate.cpp');build(command)
        for name in shlex.split((work/'fixture.d').read_text().replace('\\\n',' ').split(':',1)[1]):
            p=ANDROID/name
            if p.is_file():sources[str(p)]=sha(p)
        link=ref['link_command'].copy();old=next(a for a in link if a.endswith('/fixture.o'))
        link[link.index(old)]=str(work/'fixture.o');link[link.index('-o')+1]=str(work/'test')
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
        for name in ['map-denied','no-space','no-kernel','missing-estimate','bad-cow-version','overlay','wrong-state']:
            shutil.rmtree(jail/'work',ignore_errors=True);(jail/'work').mkdir()
            shutil.copyfile(manifest,jail/'work/manifest.pb')
            result=subprocess.run(['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64','/android/system/bin/linker64','/test',name],preexec_fn=isolate,capture_output=True,text=True,timeout=40)
            diagnostic={
                'map-denied':'Could not create COW device:',
                'no-space':'Cannot create /data backed snapshots in recovery.',
                'no-kernel':'refusing to fall back to legacy',
                'missing-estimate':'Update manifest does not include a COW size',
                'bad-cow-version':'Manifest cow version is out of bounds',
                'overlay':'Cannot create update snapshots with overlayfs setup.',
                'wrong-state':'Cannot create update snapshots in state unverified'}[name]
            observed=diagnostic in result.stderr and (name!='map-denied' or 'PLANNED checked stock sizes and COW estimates=10' in result.stdout)
            cases.append(dict(name=name,expected_diagnostic=diagnostic,diagnostic_observed=observed,status='PASS' if result.returncode==0 and 'PASS '+name in result.stdout and observed else 'FAIL',returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
            print(cases[-1]['status'],name,flush=True)
        report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,sources=sources,dependencies=deps,image=str(image),image_sha256=sha(image),image_entries=entries,compile_command=command,link_command=link,fixture_sha256=hashlib.sha256(elf).hexdigest(),fixture_elf_machine=183,manifest_sha256=sha(manifest),inventory_sha256=sha(inventory),cases=cases,synthetic_source_layout=True,actual_snapshot_manager=True,actual_snapshot_allocation_attempt=True,actual_kernel_mapping=False,full_ota_install=False,production_changes=False,new_build=False)
        (ROOT/'logs/ota-snapshot-allocate.json').write_text(json.dumps(report,indent=2)+'\n')
        return 0 if report['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
