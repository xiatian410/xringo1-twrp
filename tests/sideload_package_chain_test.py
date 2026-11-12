#!/usr/bin/env python3
"""Actual sideload core/backend or ORS branch -> ZIP/digest/extract/updater.

Real private chroot files, native minadbd stand-in via socketpair/fork/exec/epoll,
production ZIP/package/verifier/digest/protocol, harmless native updater. FUSE
is a symlink publication/stat fixture; properties, mounts/cache/Dalvik/MTP,
DataManager, performance and operation feedback are doubles. No USB, actual
minadbd/FUSE driver, ARM updater, AB payload, GUI input or physical writes.
"""
import argparse,hashlib,io,json,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from nested_partition_path_test import method,ROOT,SRC

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--before',action='store_true');ap.add_argument('--report',type=Path,default=ROOT/'logs/sideload-package-chain.json');args=ap.parse_args()
 android=SRC.parents[1];clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++';host=android/'out/host/linux-x86/lib64';base=android/'system/libbase';archive=android/'system/libziparchive'
 crypto=android/'out/soong/.intermediates/external/boringssl/libcrypto/linux_glibc_x86_64_static/libcrypto.a'
 installer=SRC/'twrpinstall/twinstall.cpp';commands=SRC/'twrpinstall/installcommand.cpp';functions=SRC/'twrp_functions.cpp';digest=SRC/'digest/twrp_digest_driver.cpp'
 core=SRC/'twrpinstall/adb_install.cpp';backend=SRC/'gui2/backend/twrp_sideload_backend.cpp';ors=SRC/'openrecoveryscript.cpp'
 if args.before:core=ROOT/'logs/sideload-completion-before/adb_install.cpp';backend=ROOT/'logs/sideload-completion-before/twrp_sideload_backend.cpp';ors=ROOT/'logs/sideload-completion-before/openrecoveryscript.cpp'
 bodies=[method(installer.read_text(),s) for s in ['static bool FindUpdaterBinary(', 'static int Prepare_Update_Binary(', 'static bool ParseUpdaterFraction(', 'static bool ParseUpdaterSeconds(', 'static int Run_Update_Binary(', 'bool isUpdatePkg(', 'int TWinstall_zip(']]
 bodies += [method(commands.read_text(),'int\nupdate_binary_command('),method(commands.read_text(),'bool verify_package_compatibility(')]
 bodies += [method(functions.read_text(),s) for s in ['int TWFunc::WaitForChild(', 'static std::vector<std::string> SplitByCharset(', 'std::vector<std::string> TWFunc::SplitString(const std::string& in, const char']]
 text=digest.read_text();a=text.index('namespace {');b=text.index('} // namespace',a)+len('} // namespace')
 bodies += [text[a:b],method(text,'bool TwrpDigestDriver::CheckFileDigest('),method(text,'bool TwrpDigestDriver::StreamFileToDigest(')]
 template=(ROOT/'tests/sideload_package_chain_test.cpp').read_text();header=SRC/'twrpinstall/include/twinstall/adb_install.h'
 template=template.replace('// CORE_HEADER','\n'.join(x for x in header.read_text().splitlines() if not x.startswith('#include')))
 template=template.replace('// ZIP_METHODS','\n'.join(bodies)).replace('// SIDELOAD_CORE',core.read_text()[core.read_text().index('using CommandFunction'):])
 template=template.replace('// SIDELOAD_BACKEND',backend.read_text()[backend.read_text().index('namespace gui2_backend'):])
 branch=method(ors.read_text(),'else if (strcmp(command, "sideload") == 0)');branch=branch[branch.index('{')+1:-1]
 template=template.replace('// ORS_BRANCH',branch)
 library=[archive/n for n in ['zip_archive.cc','zip_archive_stream_entry.cc','zip_cd_entry_map.cc','zip_error.cpp']]+[SRC/n for n in ['twrpinstall/package.cpp','twrpinstall/verifier.cpp','twrpinstall/asn1_decoder.cpp','otautil/sysutil.cpp','otautil/rangeset.cpp','digest/twrp_digest.cpp']]
 modes={
  'clean':['clean'],'package-wipe':['wipe'],'package-wipe-fail':['wipe-fail'],'package-cache-error':['wipe'],
  'wipe-first':['wipe','clean'],'wipe-last':['clean','wipe'],'wipe-twice':['wipe','wipe'],'wipe-then-fail':['wipe','fail'],
  'cache-error-first':['wipe','clean'],'updater-fail':['fail'],'wipe-second-fail':['wipe-fail','clean'],'wipe-badprogress':['wipe','badprogress'],'wipe-missing-updater':['wipe','missing-updater'],'badprogress':['badprogress'],'missing-updater':['missing-updater'],
  'signature-reject':['clean'],
  'user-cache':['clean'],'user-cache-error':['clean'],'package-and-user-cache':['wipe'],'user-dalvik':['clean'],'user-dalvik-error':['clean'],
  'both-cleanup-errors':['clean'],'script-clean':['clean'],'script-package-wipe':['wipe'],'script-cache-error':['wipe'],
  'script-updater-fail':['fail'],'script-wipe-fail':['wipe-fail']}
 reports=[]
 with tempfile.TemporaryDirectory(prefix='sideload-package-') as tmp:
  work=Path(tmp);code=work/'test.cpp';code.write_text(template);exe=work/'test'
  cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-Wno-deprecated-declarations','-D__unused=__attribute__((unused))','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DINCFS_SUPPORT_DISABLED=1','-DZLIB_CONST',
   '-I'+str(SRC/'twrpinstall/include'),'-I'+str(SRC/'otautil/include'),'-I'+str(SRC/'digest'),'-I'+str(SRC/'gui2/backend'),'-I'+str(SRC/'minadbd/include'),
   '-I'+str(base/'include'),'-I'+str(android/'external/boringssl/src/include'),'-I'+str(archive/'include'),'-I'+str(archive/'incfs_support/include'),'-I'+str(android/'system/logging/liblog/include'),'-I'+str(android/'system/core/libcutils/include'),'-I'+str(android/'external/googletest/googletest/include'),
   str(code),*map(str,library),str(crypto),'-L'+str(host),'-Wl,-rpath,'+str(host),'-lbase','-llog','-lz','-ldl','-lpthread','-o',str(exe)]
  subprocess.run(cmd,check=True);binaries={}
  for mode in ['clean','wipe','fail','wipe-fail','badprogress']:
   binary=work/('fixture-'+mode);subprocess.run(['g++','-std=c++23','-O1','-static','-pthread','-DQUEUE_MODE="'+mode+'"',str(ROOT/'tests/zip_queue_fixture.cpp'),'-o',str(binary)],check=True);binaries[mode]=binary.read_bytes()
  minadbd=work/'minadbd';subprocess.run(['g++','-std=c++23','-O1','-static',str(ROOT/'tests/sideload_package_fixture.cpp'),'-o',str(minadbd)],check=True)
  dependencies={}
  for line in subprocess.check_output(['ldd',str(exe)],text=True).splitlines():
   match=re.search(r'(/[^\s()]+)',line)
   if match:p=Path(match[1]);dependencies[str(p)]=sha(p)
  for name,queue in modes.items():
   jail=work/name;jail.mkdir()
   for dep in dependencies:
    dest=jail/Path(dep).relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dep,dest);dest.chmod(0o755)
   shutil.copyfile(exe,jail/'test');(jail/'test').chmod(0o755)
   for directory in ['tmp','packages','sideload','system/bin']:(jail/directory).mkdir(parents=True,exist_ok=True)
   shutil.copyfile(minadbd,jail/'system/bin/minadbd');(jail/'system/bin/minadbd').chmod(0o755);inputs={}
   for i,mode in enumerate(queue):
    path=jail/f'packages/{i}.zip';buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
     def put(entry,data):
      info=zipfile.ZipInfo(entry,(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
     if mode!='missing-updater':put('META-INF/com/google/android/update-binary',binaries[mode])
     put('fixture.txt',b'private sideload ZIP bytes')
    path.write_bytes(buf.getvalue());inputs[path.name]=sha(path)
    if name in ['digest-reject','digest-skip']:path.with_suffix('.zip.sha256').write_text('0'*64+'  '+path.name+'\n')
   fail=name in ['wipe-second-fail','wipe-badprogress','wipe-missing-updater','package-wipe-fail','package-cache-error','wipe-then-fail','cache-error-first','updater-fail','badprogress','missing-updater','digest-reject','signature-reject','user-cache-error','user-dalvik-error','both-cleanup-errors','script-cache-error','script-updater-fail','script-wipe-fail']
   run=subprocess.run(['chroot',str(jail),'/test',name,'fail' if fail else 'success'],env={**__import__('os').environ,'SIDELOAD_PACKAGES':str(len(queue))},capture_output=True,text=True,timeout=15)
   trace=(jail/'packages/executed').read_text().splitlines() if (jail/'packages/executed').exists() else []
   statuses=(jail/'packages/statuses').read_text().splitlines() if (jail/'packages/statuses').exists() else []
   expected_trace=[];expected_status=[];wipes=0
   for mode in queue:
    bad=mode in ['fail','wipe-fail','badprogress','missing-updater'] or name in ['digest-reject','signature-reject']
    if mode!='missing-updater' and name not in ['digest-reject','signature-reject']:expected_trace.append('/sideload/package.zip '+mode)
    if mode in ['wipe','wipe-fail']:
     wipes+=1
     if 'cache-error' in name:bad=True
    expected_status.append('1' if bad else '0')
    if bad:break
   if name in ['user-cache','user-cache-error','package-and-user-cache','both-cleanup-errors']:wipes+=1
   acknowledgements=(jail/'packages/cache-at-ack').read_text().splitlines() if (jail/'packages/cache-at-ack').exists() else []
   expected_ack=[];attempts=0
   for i,status in enumerate(expected_status):
    if queue[i] in ['wipe','wipe-fail']:attempts+=1
    expected_ack.append(str(attempts))
   counts=(jail/'packages/counts').read_text().strip() if (jail/'packages/counts').exists() else ''
   content_ok=trace==expected_trace and statuses==expected_status and counts.startswith(f'wipes={wipes} ') and acknowledgements==expected_ack
   reports.append(dict(case=name,status='PASS' if run.returncode==0 and content_ok else 'FAIL',exit=run.returncode,content_ok=content_ok,input_sha256=inputs,executed=trace,expected_executed=expected_trace,statuses=statuses,expected_statuses=expected_status,expected_wipes=wipes,acknowledged_cache_attempts=acknowledgements,expected_cache_attempts_at_ack=expected_ack,counts=counts,output=run.stdout+run.stderr))
   print(reports[-1]['status'],name,flush=True)
   if reports[-1]['status']=='FAIL':print((run.stdout+run.stderr)[-1000:],trace,expected_trace,statuses,expected_status,counts,flush=True)
 bound=[core,backend,ors,header,installer,commands,functions,digest,Path(__file__).resolve(),ROOT/'tests/sideload_package_chain_test.cpp',ROOT/'tests/sideload_package_fixture.cpp',ROOT/'tests/zip_queue_fixture.cpp',ROOT/'tests/nested_partition_path_test.py',*library]
 bound+=list((SRC/'twrpinstall/include').rglob('*.h'))+list((SRC/'otautil/include').rglob('*.h'))+list((SRC/'digest').glob('*.hpp'))+[SRC/'minadbd/include/minadbd/types.h',SRC/'gui2/backend/twrp_sideload_backend.h',SRC/'gui2/backend/sideload_backend.h']
 bound+=list(archive.glob('*.h'))+list((archive/'include').rglob('*.h'))+list((archive/'incfs_support/include').rglob('*.h'))
 report=dict(status='PASS' if all(c['status']=='PASS' for c in reports) else 'FAIL',scope=__doc__,cases=reports,sources={str(p):sha(p) for p in bound},binary_dependencies={str(crypto):sha(crypto),str(clang):sha(clang),**dependencies})
 args.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
