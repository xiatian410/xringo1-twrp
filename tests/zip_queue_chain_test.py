#!/usr/bin/env python3
"""Original public ZIP backend/worker -> real ZIP/digest/extraction/fork/exec.

Private chroots and harmless native updaters only. DataManager, progress,
mounts, cache wiping, block unlocking, size refresh, operation feedback and
performance are explicit doubles. Signature rejection without keys executes;
cryptographic acceptance is covered separately by zip_install_chain_test.py.
No GUI pointer events, AB payload, OZIP, ARM updater, phone or block device run.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile
from nested_partition_path_test import method,ROOT,SRC

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source',type=Path,default=SRC/'gui2/backend/twrp_install_backend.cpp')
 ap.add_argument('--report',type=Path,default=ROOT/'logs/zip-queue-chain.json')
 args=ap.parse_args();android=SRC.parents[1]
 clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++'
 host=android/'out/host/linux-x86/lib64';base=android/'system/libbase';archive=android/'system/libziparchive'
 crypto=android/'out/soong/.intermediates/external/boringssl/libcrypto/linux_glibc_x86_64_static/libcrypto.a'
 installer=SRC/'twrpinstall/twinstall.cpp';commands=SRC/'twrpinstall/installcommand.cpp';functions=SRC/'twrp_functions.cpp';digest=SRC/'digest/twrp_digest_driver.cpp'
 bodies=[method(installer.read_text(),s) for s in ['static bool FindUpdaterBinary(', 'static int Prepare_Update_Binary(',
  'static bool ParseUpdaterFraction(', 'static bool ParseUpdaterSeconds(', 'static int Run_Update_Binary(', 'bool isUpdatePkg(', 'int TWinstall_zip(']]
 bodies += [method(commands.read_text(),'int\nupdate_binary_command('),method(commands.read_text(),'bool verify_package_compatibility(')]
 bodies += [method(functions.read_text(),s) for s in ['int TWFunc::WaitForChild(', 'static std::vector<std::string> SplitByCharset(',
  'std::vector<std::string> TWFunc::SplitString(const std::string& in, const char']]
 text=digest.read_text();a=text.index('namespace {');b=text.index('} // namespace',a)+len('} // namespace')
 bodies += [text[a:b],method(text,'bool TwrpDigestDriver::CheckFileDigest('),method(text,'bool TwrpDigestDriver::StreamFileToDigest(')]
 text=args.source.read_text()
 bodies += ['namespace gui2_backend {\n'+ '\n'.join(method(text,s) for s in ['int flash_zip(',
  'twrp_install_backend::~twrp_install_backend(', 'void twrp_install_backend::join_finished_thread(',
  'bool twrp_install_backend::start_zip(', 'void twrp_install_backend::run_zip(',
  'install_status twrp_install_backend::status(', 'void twrp_install_backend::acknowledge('])+'\n}']
 library=[archive/n for n in ['zip_archive.cc','zip_archive_stream_entry.cc','zip_cd_entry_map.cc','zip_error.cpp']]
 library += [SRC/n for n in ['twrpinstall/package.cpp','twrpinstall/verifier.cpp','twrpinstall/asn1_decoder.cpp','otautil/sysutil.cpp','otautil/rangeset.cpp','digest/twrp_digest.cpp']]
 modes={
  'single-clean':['clean'],'single-wipe':['wipe'],'two-clean':['clean','clean'],
  'wipe-first':['wipe','clean'],'wipe-last':['clean','wipe'],'wipe-both':['wipe','wipe'],
  'wipe-first-then-fail':['wipe','fail'],'wipe-failing':['wipe-fail'],
  'wipe-first-badprogress':['wipe','badprogress'],'wipe-first-missing':['wipe','missing-updater'],
  'cache-error':['wipe'],'cache-error-after-queue':['wipe','clean'],'missing-first':['missing'],
  'empty-item':['clean'],'digest-reject':['clean'],'digest-skip':['clean'],
  'updater-fail':['fail'],'protocol-error':['badprogress'],'signature-reject':['clean'],
  'busy':['hold','clean'],'reuse':['fail','clean'],'empty-queue':['clean'],
  'destructor-join':['clean','clean']}
 cases=[]
 with tempfile.TemporaryDirectory(prefix='zip-queue-chain-') as tmp:
  work=Path(tmp);code=work/'test.cpp';code.write_text((ROOT/'tests/zip_queue_chain_test.cpp').read_text().replace('// PRODUCTION_METHODS','\n'.join(bodies)))
  exe=work/'queue-test'
  cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-Wno-deprecated-declarations',
   '-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DINCFS_SUPPORT_DISABLED=1','-DZLIB_CONST',
   '-I'+str(SRC/'twrpinstall/include'),'-I'+str(SRC/'otautil/include'),'-I'+str(SRC/'digest'),'-I'+str(SRC/'gui2/backend'),
   '-I'+str(base/'include'),'-I'+str(android/'external/boringssl/src/include'),'-I'+str(archive/'include'),'-I'+str(archive/'incfs_support/include'),
   '-I'+str(android/'system/logging/liblog/include'),'-I'+str(android/'system/core/libcutils/include'),'-I'+str(android/'external/googletest/googletest/include'),
   str(code),*map(str,library),str(crypto),'-L'+str(host),'-Wl,-rpath,'+str(host),'-lbase','-llog','-lz','-ldl','-lpthread','-o',str(exe)]
  subprocess.run(cmd,check=True);binaries={}
  for mode in ['clean','wipe','fail','wipe-fail','badprogress','hold']:
   binary=work/('fixture-'+mode)
   subprocess.run(['g++','-std=c++23','-O1','-static','-pthread','-DQUEUE_MODE="'+mode+'"',str(ROOT/'tests/zip_queue_fixture.cpp'),'-o',str(binary)],check=True)
   binaries[mode]=binary.read_bytes()
  dependencies={}
  for line in subprocess.check_output(['ldd',str(exe)],text=True).splitlines():
   match=re.search(r'(/[^\s()]+)',line)
   if match:p=Path(match[1]);dependencies[str(p)]=sha(p)
  for name,queue in modes.items():
   jail=work/name;jail.mkdir()
   for dep in dependencies:
    dest=jail/Path(dep).relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dep,dest);dest.chmod(0o755)
   shutil.copyfile(exe,jail/'test');(jail/'test').chmod(0o755)
   (jail/'tmp').mkdir();(jail/'packages').mkdir();inputs={}
   for index,mode in enumerate(queue):
    path=jail/'packages'/(['first.zip','second.zip'][index])
    if mode=='missing':continue
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
     def put(entry,data):
      info=zipfile.ZipInfo(entry,(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
      z.writestr(info,data)
     if mode!='missing-updater':put('META-INF/com/google/android/update-binary',binaries[mode])
     put('fixture.txt',b'private queue test data')
    path.write_bytes(buf.getvalue());inputs[path.name]=sha(path)
    if name in ['digest-reject','digest-skip']:path.with_suffix('.zip.sha256').write_text('0'*64+'  '+path.name+'\n')
   run=subprocess.run(['chroot',str(jail),'/test',name],capture_output=True,text=True,timeout=15)
   trace=(jail/'packages/executed').read_text().splitlines() if (jail/'packages/executed').exists() else []
   expected=[]
   for index,mode in enumerate(queue):
    if name in ['empty-item','empty-queue','digest-reject','signature-reject'] or mode in ['missing','missing-updater']:break
    expected.append('/packages/'+['first.zip','second.zip'][index]+' '+mode)
    if mode in ['fail','wipe-fail','badprogress'] and name!='reuse':break
   if name=='reuse':expected.append('/packages/second.zip clean') if len(expected)==1 else None
   content_ok=trace==expected
   cases.append(dict(case=name,status='PASS' if run.returncode==0 and content_ok else 'FAIL',exit=run.returncode,
    content_ok=content_ok,executed=trace,expected=expected,input_sha256=inputs,cache_marker=(jail/'packages/cache-cleared').exists(),output=run.stdout+run.stderr))
   print(cases[-1]['status'],name,flush=True)
   if cases[-1]['status']=='FAIL':print((run.stdout+run.stderr)[-1200:],trace,expected,flush=True)
 bound=[args.source,installer,commands,functions,digest,Path(__file__).resolve(),ROOT/'tests/zip_queue_chain_test.cpp',ROOT/'tests/zip_queue_fixture.cpp',ROOT/'tests/nested_partition_path_test.py',*library]
 bound+=list((SRC/'twrpinstall/include').rglob('*.h'))+list((SRC/'otautil/include').rglob('*.h'))+list((SRC/'digest').glob('*.hpp'))
 bound+=[SRC/'gui2/backend/install_backend.h',SRC/'gui2/backend/twrp_install_backend.h']
 bound+=list(archive.glob('*.h'))+list((archive/'include').rglob('*.h'))+list((archive/'incfs_support/include').rglob('*.h'))
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in bound},binary_dependencies={str(crypto):sha(crypto),str(clang):sha(clang),**dependencies},compile_command=cmd)
 args.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
