#!/usr/bin/env python3
"""Original A/B metadata/package/ZIP command preparation -> fork/pipe/wait.

A harmless native executable replaces update_engine_sideload only at execve.
It verifies argv and actual bytes at the ZIP payload offset, reports progress,
and never installs a payload. Android properties/progress are explicit doubles.
No real updater, partition writes, signature validation, GUI, ARM64 or device.
"""
import argparse,hashlib,io,json,re,shutil,struct,subprocess,tempfile,zipfile
from pathlib import Path
from nested_partition_path_test import ROOT,SRC,method

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--before',action='store_true');args=ap.parse_args()
 android=SRC.parents[1];source=ROOT/'logs/ab-command-before' if args.before else SRC/'twrpinstall'
 commands=source/'installcommand.cpp';installer=source/'twinstall.cpp'
 c=re.sub(r'^\s*//[^\n]*','',commands.read_text(),flags=re.M);t=installer.read_text();body=[]
 for sig in ['static int parse_build_number(', 'bool read_metadata_from_package(', 'void read_source_target_build(', 'static int check_newer_ab_build(', 'int\nabupdate_binary_command(']:body.append(method(c,sig))
 for sig in ['static bool ParseUpdaterFraction(', 'static bool ParseUpdaterSeconds(', 'static int Run_Update_Binary(']:body.append(method(t,sig))
 body.append(method((SRC/'twrp_functions.cpp').read_text(),'int TWFunc::WaitForChild('))
 host=android/'out/host/linux-x86/lib64';base=android/'system/libbase';archive=android/'system/libziparchive'
 library=[archive/n for n in ['zip_archive.cc','zip_archive_stream_entry.cc','zip_cd_entry_map.cc','zip_error.cpp']]+[SRC/n for n in ['twrpinstall/package.cpp','otautil/sysutil.cpp','otautil/rangeset.cpp']]
 names=['stored','properties-deflated','payload-deflated','properties-corrupt','properties-missing','command-reuse-rejection','properties-empty','properties-nul','payload-missing','payload-empty','metadata-missing','device-mismatch','serial-mismatch','incremental-mismatch','fingerprint-mismatch','ota-type-mismatch','invalid-zip','missing-package','engine-nonzero','engine-protocol-error','empty-command']
 cases=[]
 with tempfile.TemporaryDirectory(prefix='ab-command-chain-') as tmp:
  w=Path(tmp);cpp=w/'test.cpp';cpp.write_text((ROOT/'tests/ab_command_chain_test.cpp').read_text().replace('// PRODUCTION_METHODS','\n'.join(body)))
  clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++'
  cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-DINCFS_SUPPORT_DISABLED=1','-DZLIB_CONST','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(SRC/'twrpinstall/include'),'-I'+str(SRC/'otautil/include'),'-I'+str(android/'external/boringssl/src/include'),'-I'+str(android/'system/core/libcutils/include'),'-I'+str(base/'include'),'-I'+str(archive/'include'),'-I'+str(archive/'incfs_support/include'),'-I'+str(android/'system/logging/liblog/include'),str(cpp),*map(str,library),'-L'+str(host),'-Wl,-rpath,'+str(host),'-lbase','-llog','-lz','-ldl','-pthread','-o',str(w/'test')]
  subprocess.run(cmd,check=True)
  deps=[]
  for line in subprocess.check_output(['ldd',str(w/'test')],text=True).splitlines():
   m=re.search(r'(/[\w/+.\-]+)',line)
   if m:deps.append(Path(m[1]))
  payload=b'CrAU'+bytes(range(256))*8
  props=b'FILE_HASH=fixture\nFILE_SIZE='+str(len(payload)).encode()+b'\nMETADATA_HASH=fixture\nMETADATA_SIZE=24\n'
  for name in names:
   jail=w/name;jail.mkdir();(jail/'packages').mkdir()
   for dep in deps:
    p=jail/dep.relative_to('/');p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dep,p);p.chmod(0o755)
   shutil.copyfile(w/'test',jail/'test');(jail/'test').chmod(0o755)
   metadata=b'pre-device=dijun\nota-type=AB\npost-build-incremental=123\n'
   values={'device-mismatch':b'pre-device=other\nota-type=AB\n','serial-mismatch':metadata+b'serialno=other\n','incremental-mismatch':metadata+b'pre-build-incremental=other\n','fingerprint-mismatch':metadata+b'pre-build=other\n','ota-type-mismatch':b'pre-device=dijun\nota-type=BLOCK\n'}
   b=io.BytesIO()
   with zipfile.ZipFile(b,'w') as z:
    if name!='metadata-missing':z.writestr('META-INF/com/android/metadata',values.get(name,metadata))
    if name not in ['properties-missing','command-reuse-rejection']:
     data=b'' if name=='properties-empty' else props+b'\0HIDDEN=1\n' if name=='properties-nul' else props
     z.writestr('payload_properties.txt',data,compress_type=zipfile.ZIP_DEFLATED if name in ['properties-deflated','properties-corrupt'] else zipfile.ZIP_STORED)
    if name!='payload-missing':z.writestr('payload.bin',b'' if name=='payload-empty' else payload,compress_type=zipfile.ZIP_DEFLATED if name=='payload-deflated' else zipfile.ZIP_STORED)
   data=b.getvalue()
   if name=='properties-corrupt':
    with zipfile.ZipFile(io.BytesIO(data)) as z:i=z.getinfo('payload_properties.txt')
    offset=i.header_offset+30+len(i.filename.encode())+len(i.extra)
    data=data[:offset]+b'\xff'*i.compress_size+data[offset+i.compress_size:]
   package=jail/'packages/test.zip'
   if name!='missing-package':package.write_bytes(b'not a zip archive' if name=='invalid-zip' else data)
   if name=='empty-command': # explicit failed-generator boundary; other cases use original command builder
    expected=False
   else:expected=name in ['stored','properties-deflated']
   r=subprocess.run(['chroot',str(jail),'/test',name,str(int(expected))],capture_output=True,text=True,timeout=15)
   marker=jail/'packages/engine-entered.txt';entered=marker.exists();should_enter=name in ['stored','properties-deflated','engine-nonzero','engine-protocol-error']
   ok=r.returncode==0 and entered==should_enter
   cases.append(dict(case=name,status='PASS' if ok else 'FAIL',exit=r.returncode,engine_entered=entered,expected_engine=should_enter,output=r.stdout+r.stderr))
   print(cases[-1]['status'],name,flush=True)
 files=[commands,installer,SRC/'twrp_functions.cpp',*library,Path(__file__).resolve(),ROOT/'tests/ab_command_chain_test.cpp',ROOT/'tests/nested_partition_path_test.py',SRC/'twrpinstall/include/twinstall/package.h',SRC/'twrpinstall/include/twinstall/verifier.h',archive/'include/ziparchive/zip_archive.h',clang,*deps]
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,compile_command=cmd,sources={str(p):sha(p) for p in files})
 (ROOT/('logs/ab-command-before.json' if args.before else 'logs/ab-command-chain.json')).write_text(json.dumps(report,indent=2)+'\n')
 return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
