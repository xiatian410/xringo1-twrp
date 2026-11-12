#!/usr/bin/env python3
"""Run actual image-install worker/thread -> manager -> partition -> libsparse.

Uses production public backend header, lifecycle, filename routing, manager
target lookup and slot override. Real sparse parser/writer and private file
contents execute. DataManager, progress/console, source mounts, target capacity,
partition size/device resolution and UpdateSystemDetails are explicit doubles.
No ZIP, raw transfer, repacker, GUI widgets, boot-control service, physical block
device, USB, target ARM64 or power-loss execution. A/B resolution is a fixture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from nested_partition_path_test import method,ROOT,SRC

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,default=ROOT/'logs/image-install-chain.json')
    args=ap.parse_args()
    extract={
      'partition.cpp':['bool TWPartition::FlashImage(','bool TWPartition::IsSparseImage(',
                       'bool TWPartition::FlashSparseImage(','bool TWPartition::IsSlotSelect('],
      'partitionmanager.cpp':['bool TWPartitionManager::FlashImage(', 'bool TWPartitionManager::MatchesPath(',
                             'TWPartition* TWPartitionManager::FindPartitionByPath(',
                             'void TWPartitionManager::OverrideActiveSlot(',
                             'std::string TWPartitionManager::GetActiveSlotDisplay(',
                             'std::string TWPartitionManager::GetActiveSlotSuffix('],
      'twrp_functions.cpp':['std::string TWFunc::GetRootPath('],
      'gui2/backend/twrp_install_backend.cpp':['twrp_install_backend::~twrp_install_backend(',
         'void twrp_install_backend::join_finished_thread(', 'bool twrp_install_backend::start_image(',
         'void twrp_install_backend::run_image(', 'install_status twrp_install_backend::status(',
         'void twrp_install_backend::acknowledge(', 'std::vector<image_target> twrp_install_backend::image_targets(',
         'std::string twrp_install_backend::image_target_for(']}
    bodies=[]
    for name,signatures in extract.items():
        text=(SRC/name).read_text();body='\n'.join(method(text,sig) for sig in signatures)
        if name.startswith('gui2/'):body='namespace gui2_backend {\n'+body+'\n}'
        bodies.append(body)
    base=SRC.parents[1]/'system/libbase';sparse=SRC.parents[1]/'system/core/libsparse'
    library=[sparse/(n+'.cpp') for n in ['backed_block','output_file','sparse','sparse_crc32','sparse_err','sparse_read']]
    library += [base/'mapped_file.cpp',base/'stringprintf.cpp']
    cases=[];commands=[]
    names=['normal','dual','initial-B','nonslot','busy','first-write-error','second-write-error',
           'second-sync-error','second-close-error','second-small','unknown-target','multiple-targets',
           'empty-target','missing-source','disabled','files-target','size-unknown','expanded-oversize',
           'route-names','list-unavailable']
    with tempfile.TemporaryDirectory(prefix='image-install-chain-') as temp:
        work=Path(temp);harness=work/'test.cpp'
        harness.write_text((ROOT/'tests/image_install_chain_test.cpp').read_text().replace('// PRODUCTION_METHODS','\n'.join(bodies)))
        for ab in [True,False]:
            exe=work/('ab' if ab else 'non-ab')
            cmd=['g++','-std=c++23','-O1','-g','-pthread','-fsanitize=address,undefined',
                 '-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie',
                 '-I'+str(SRC/'gui2/backend'),'-I'+str(SRC),'-I'+str(base/'include'),
                 '-I'+str(sparse/'include'),'-I'+str(sparse),str(harness),*map(str,library),'-lz',
                 *['-Wl,--wrap='+n for n in ['fstat','ioctl','write','fsync','close','ftruncate64']],'-o',str(exe)]
            if ab:cmd.insert(1,'-DAB_OTA_UPDATER')
            subprocess.run(cmd,check=True);commands.append(cmd)
            for name in names:
                wd=work/(name+('-ab' if ab else '-non-ab'));wd.mkdir()
                raw=bytes((i*43+17)%251 for i in range(4096));fill=struct.pack('<I',0x12345678)
                def chunk(kind,blocks,payload):return struct.pack('<HHII',kind,0,blocks,len(payload)+12)+payload
                blocks=16 if name=='expanded-oversize' else 2
                chunks=chunk(0xcac2,blocks,fill) if name=='expanded-oversize' else chunk(0xcac1,1,raw)+chunk(0xcac2,1,fill)
                (wd/'input.sparse').write_bytes(struct.pack('<IHHHHIIII',0xed26ff3a,1,0,28,12,4096,blocks,1 if blocks==16 else 2,0)+chunks)
                before={n:bytes([v])*32768 for n,v in [('boot_a',0xa1),('boot_b',0xb2),('recovery',0xc3)]}
                for n,data in before.items():(wd/(n+'.bin')).write_bytes(data)
                run=subprocess.run([str(exe),name],cwd=wd,capture_output=True,text=True,timeout=20)
                expected=[]
                if name in ['normal','busy'] or (not ab and name.startswith('second-')):expected=['boot_a']
                if name in ['dual']:expected=['boot_a','boot_b'] if ab else ['boot_a']
                if name=='initial-B':expected=['boot_b','boot_a'] if ab else ['boot_b']
                if name=='nonslot':expected=['recovery']
                if ab and name in ['second-write-error','second-small']:expected=['boot_a']
                if ab and name in ['second-sync-error','second-close-error']:expected=['boot_a','boot_b']
                content_ok=True;outputs={}
                for n,data in before.items():
                    after=(wd/(n+'.bin')).read_bytes()
                    content_ok &= after==(raw+fill*1024+data[8192:] if n in expected else data)
                    outputs[n]=sha(wd/(n+'.bin'))
                events=[s[6:] for s in run.stdout.splitlines() if s.startswith('EVENT ')]
                resolves=[e[8:-4] for e in events if e.startswith('resolve:')]
                # Assert order as well as resulting bytes for both-slot operations.
                order_ok=True
                if name in ['dual','initial-B']:
                    order_ok=resolves==expected
                    overrides=[e for e in events if e.startswith('override:')]
                    order_ok &= overrides==(['override:'+('A' if name=='initial-B' else 'B'),
                                             'override:'+('B' if name=='initial-B' else 'A')] if ab else [])
                passed=run.returncode==0 and content_ok and order_ok
                cases.append(dict(case=name,ab_build=ab,status='PASS' if passed else 'FAIL',exit=run.returncode,
                                  content_ok=bool(content_ok),order_ok=bool(order_ok),expected_written=expected,
                                  output_hashes=outputs,events=events,output=run.stdout+run.stderr))
                print(cases[-1]['status'],name,'ab='+str(ab),flush=True)
    bound=[SRC/n for n in extract]+library+[Path(__file__).resolve(),ROOT/'tests/image_install_chain_test.cpp',
          ROOT/'tests/nested_partition_path_test.py',SRC/'gui2/backend/twrp_install_backend.h',SRC/'gui2/backend/install_backend.h',SRC/'twrp_operation_executor.h']
    bound+=list(sparse.glob('*.h'))+list((sparse/'include').rglob('*.h'))
    bound+=[base/'include/android-base'/n for n in ['unique_fd.h','scopeguard.h','mapped_file.h','stringprintf.h']]
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,
                cases=cases,sources={str(p):sha(p) for p in bound},compile_commands=commands)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':raise SystemExit(main())
