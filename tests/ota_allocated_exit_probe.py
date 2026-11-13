#!/usr/bin/env python3
"""Isolate allocated model's process-static versus scoped controller destruction.

Uses the exact saved adapter from the failed full run, current image libraries
and original snapshot allocation. No payload replay, kernel maps or hardware.
"""
import hashlib
import argparse
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
from ota_snapshot_allocate import sha
from firmware_facts import boot_parts, ramdisk_entries
from ota_run_outputs import output_prefix, reserve_outputs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name',help='Unique evidence suffix; existing probe reports are preserved')
    args=parser.parse_args()
    try:
        prefix=output_prefix('ota-allocated-exit-probe',args.run_name)
        reserve_outputs(ROOT/'logs',prefix,['.json'])
    except (ValueError,FileExistsError) as error:
        parser.error(str(error))
    ref=json.loads((ROOT/'logs/zip-engine-allocated-finish.json').read_text())
    engine=ref['engine'];image=Path(ref['image'])
    assert sha(image)==ref['image_sha256']
    adapter=ROOT/'logs/zip-engine-allocated-adapter.cpp'
    adapter_text=adapter.read_text()
    old='void Cleanup() override { printf("BOUNDARY Cleanup file model\\n"); }'
    new='''void Cleanup() override {
        if (allocated_control) {
            allocated_control->Cleanup();
            allocated_control.reset();
            puts("MODEL released controller during Cleanup");
        }
        puts("BOUNDARY Cleanup file model");fflush(stdout);
    }'''
    assert adapter_text.count(old)==1
    adapter_text=adapter_text.replace(old,new)
    fixture=ROOT/'tests/ota_allocated_exit_probe.cpp'
    with tempfile.TemporaryDirectory(prefix='allocated-exit-',dir=ROOT/'logs') as tmp:
        work=Path(tmp);combined=work/'probe.cpp'
        combined.write_text(adapter_text+'\n'+fixture.read_text())
        support=ROOT/'logs/zip-engine-allocated-support.inc'
        shutil.copyfile(support,work/'snapshot_init_support.inc')
        command=engine['compile_command'].copy();command.insert(1,'-I'+str(work))
        command[command.index('-o')+1]=str(work/'adapter.o');command[command.index('-MF')+1]=str(work/'probe.d');command[-1]=str(combined);build(command)
        link=[a for a in engine['link_command'] if '/obj/system/update_engine/' not in a or a.endswith('/aosp/logging_android.o')]
        link[link.index(next(a for a in link if a.endswith('/adapter.o')))]=str(work/'adapter.o');link[link.index('-o')+1]=str(work/'probe');build(link)
        sources={str(p):sha(p) for p in [Path(__file__),fixture,adapter,support,ROOT/'tests/ota_run_outputs.py',ROOT/'tests/ota_vabc_session.py',ROOT/'tests/ota_snapshot_allocate.py',ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py']}
        for name in shlex.split((work/'probe.d').read_text().replace('\\\n',' ').split(':',1)[1]):
            dep=ANDROID/name
            if dep.is_file() and not dep.is_relative_to(work):sources[str(dep)]=sha(dep)
        qemu=ROOT/'tools/qemu-user/qemu-aarch64';assert sha(qemu)==json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
        dependencies={str(qemu):sha(qemu)}
        for name in link:
            dep=ANDROID/name
            if dep.is_file() and not dep.is_relative_to(work):dependencies[str(dep)]=sha(dep)
        jail=work/'jail';entries={}
        for name,mode,*rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name=='system/bin/linker64' or name.startswith('system/lib64/') and name.endswith('.so')):
                p=jail/'android'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(rest[-1]);p.chmod(mode&0o777);entries[name]=hashlib.sha256(rest[-1]).hexdigest()
        (jail/'dev').mkdir();(jail/'dev/null').touch()
        for name,path in [('qemu',qemu),('probe',work/'probe')]:shutil.copyfile(path,jail/name);(jail/name).chmod(0o755)
        def isolate():os.chroot(jail);os.chdir('/')
        rows=[]
        for name in ['static','scoped']:
            shutil.rmtree(jail/'work',ignore_errors=True);(jail/'work').mkdir();shutil.copyfile(ROOT/'firmware/samples/os4-stable/payload-manifest.pb',jail/'work/manifest.pb')
            child=subprocess.run(['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64','/android/system/bin/linker64','/probe',name],preexec_fn=isolate,capture_output=True,text=True,timeout=30)
            expected=child.returncode==0 if name=='scoped' else child.returncode!=0 and 'Fatal signal 11 (SIGSEGV)' in child.stderr
            ok=expected and 'PROBE main completed' in child.stdout
            rows.append(dict(name=name,status='PASS' if ok else 'FAIL',returncode=child.returncode,stdout=child.stdout,stderr=child.stderr));print(rows[-1]['status'],name,child.returncode,flush=True)
        r=dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,sources=sources,dependencies=dependencies,image_sha256=sha(image),image_entries=entries,compile_command=command,link_command=link,fixture_sha256=sha(work/'probe'),adapter_sha256=hashlib.sha256(adapter_text.encode()).hexdigest(),full_run_report_sha256=sha(ROOT/'logs/zip-engine-allocated-finish.json'),cases=rows,production_changes=False,new_build=False,full_ota_install=False)
        (ROOT/'logs'/(prefix+'.json')).write_text(json.dumps(r,indent=2)+'\n');return 0 if r['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
