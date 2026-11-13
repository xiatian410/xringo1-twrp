#!/usr/bin/env python3
"""Production tar + pigz + OAES roundtrips inside disposable chroots.

Whole tar/codec/exclusion/InfoManager sources and all libtar sources run. Only
Android UI/progress, fscrypt provider and small libbase helpers are substitutes.
Split threshold is 64 KiB in the fixture, not the shipped 1.5 GiB setting.
"""
import argparse,ctypes,hashlib,json,os,re,shutil,signal,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=Path('/root/AAA/twrp/bootable/recovery');ANDROID=SRC.parents[1]
CASES=['plain','gzip','aes','both','plain-split','gzip-split','aes-split','both-split',
 'gzip-bad-crc','gzip-truncated','aes-truncated','both-bad-crc','aes-wrong-password','both-wrong-password',
 'gzip-no-codec','both-no-codec','plain-missing-source','gzip-missing-source','aes-missing-source',
 'plain-empty','gzip-empty','aes-empty','both-empty','aes-thread-gap','mixed','mixed-gzip','mixed-split','mixed-gzip-split',
 'aes-random-missing','both-random-short','plain-volume-limit','gzip-volume-limit',
 'plain-split-percent','aes-percent','aes-extra-invalid',
 'plain-extra-invalid','wait-eintr','wait-not-child','wait-invalid-pid','wait-signalled','wait-nonzero','buffer-parallel','read-fragmented','read-eintr','read-truncated','read-invalid-fd']
CASES += [kind+'-sparse' for kind in ['plain','gzip','aes','both']]
CASES += [kind+'-security-'+case for kind in ['plain','gzip','aes','both']
          for case in ['success','label-error','cap-error']]
CASES += [kind+'-dirtime'+suffix for kind in ['plain','gzip','aes','both','mixed','mixed-gzip'] for suffix in ['', '-split']]
CASES += [kind+'-dirtime-error' for kind in ['plain','gzip','aes','both']]
CASES += ['gzip-dirtime-bad-crc','both-dirtime-truncated']
CASES += [kind+'-dirtime-'+fault for kind in ['plain','aes'] for fault in ['symlink','replace']]
CASES += [kind+'-xattr'+suffix for kind in ['plain','gzip','aes','both','mixed','mixed-gzip'] for suffix in ['', '-split']]
CASES += [kind+'-xattr-'+fault for kind in ['plain','gzip','aes','both'] for fault in ['write-error','read-error']]
CASES += [kind+'-path'+suffix for kind in ['plain','gzip','aes','both'] for suffix in ['', '-split']]
CASES += [kind+'-path-symlink'+suffix for kind in ['plain','aes'] for suffix in ['', '-split']]
CASES += [kind+'-special-'+node for kind in ['plain','gzip','aes','both'] for node in ['char','block']]
CASES += [kind+'-source-read-'+fault for kind in ['plain','gzip','aes','both'] for fault in ['eof','short','interrupted','io-error']]
CASES += [kind+'-source-key-'+fault for kind in ['plain','gzip','aes','both'] for fault in ['enokey','revoked','denied']]
WALK_CASES = [kind+'-walk-'+fault for kind in ['plain','gzip','aes','both','mixed'] for fault in ['nested-read','nested-open','stale-errno']]
WALK_CASES += [kind+'-walk-'+phase+'-'+fault for kind in ['aes','both','mixed'] for phase in ['top-first','top-second'] for fault in ['read','close']]
WALK_CASES += [kind+'-walk-nested-close' for kind in ['plain','gzip','aes','both','mixed']]
WALK_CASES += [kind+'-walk-size-'+fault for kind in ['aes','mixed'] for fault in ['read','close']]
CASES += WALK_CASES
TYPE_CASES = [kind+'-types-'+fault for kind in ['plain','gzip','aes','both','mixed'] for fault in ['nested-unknown','top-unknown','nested-stat-io','nested-stat-missing']]
TYPE_CASES += [kind+'-types-'+phase+'-stat-'+error for kind in ['aes','both','mixed'] for phase in ['top-first','top-second'] for error in ['io','missing']]
CASES += TYPE_CASES
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=SRC)
 ap.add_argument('--libtar-source',type=Path,default=SRC/'libtar')
 ap.add_argument('--report',type=Path,default=ROOT/'logs/archive-pipeline.json');ap.add_argument('--cases',nargs='*')
 args=ap.parse_args();cases=args.cases or CASES;libtar=args.libtar_source.resolve()
 with tempfile.TemporaryDirectory(prefix='dijun-archive-pipeline-',dir='/tmp') as tmp:
  tmp=Path(tmp);stage=tmp/'src';stage.mkdir();sources={};shared={}
  names=['twrpTar.cpp','twrpTar.hpp','tarWrite.cpp','tarWrite.hpp','exclude.cpp','exclude.hpp',
   'infomanager.cpp','infomanager.hpp','backup_process.hpp','oaes/oaes.cpp','oaes/oaes.hpp']
  for name in names:
   p=args.source/name
   if p.exists():sources[str(p)]=sha(p)
   else:p=SRC/name;shared[str(p)]=sha(p)
   dest=stage/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
  # Boundary include resolution only. Production function bodies stay intact.
  (stage/'libtar').symlink_to(libtar)
  (stage/'gui2/console').mkdir(parents=True);(stage/'android-base').mkdir()
  stubs=json.loads((ROOT/'tests/archive_pipeline_stubs.json').read_text())
  for name,body in stubs.items():(stage/name).write_text(body)
  funcs=(args.source/'twrp_functions.cpp').read_text();funh=(stage/'twrp_functions.hpp').read_text()
  bool_api='bool TWFunc::AesEncryptStream' in funcs
  if bool_api:funh=funh.replace('void AesEncryptStream','bool AesEncryptStream').replace('void AesDecryptStream','bool AesDecryptStream')
  (stage/'twrp_functions.hpp').write_text(funh)
  functions_path=args.source/'twrp_functions.cpp';sources[str(functions_path)]=sha(functions_path)
  from backup_session_test import method
  extracted='\n'.join(method(funcs,s) for s in ['ArchiveType TWFunc::GetFileType(',
   'int TWFunc::TryDecryptingFile(',('bool' if bool_api else 'void')+' TWFunc::AesEncryptStream(',
   ('bool' if bool_api else 'void')+' TWFunc::AesDecryptStream(','int TWFunc::WaitForChild('])
  tar_source=(stage/'twrpTar.cpp').read_text()
  # Exercise the same callback body as the whole compiled tar source; the old
  # constructor used read directly. No replacement of the actual tar I/O.
  callback=method(tar_source,'ssize_t readArchive(') if 'tar_type.readfunc = readArchive;' in tar_source else '#define readArchive read'
  harness=(ROOT/'tests/archive_pipeline_test.cpp').read_text().replace('// PRODUCTION_FUNCTIONS',extracted+'\n'+callback)
  (stage/'test.cpp').write_text(harness)
  compat=stage/'host.h';compat.write_text('#include <stdint.h>\n#include <stdio.h>\n#include <limits.h>\n#include <sys/types.h>\n#include <linux/fscrypt.h>\n#define __unused __attribute__((unused))\n')
  inc=['-I'+str(stage),'-I'+str(libtar),'-I'+str(ANDROID/'external/libcap/libcap/include'),
   '-I'+str(ANDROID/'external/selinux/libselinux/include'),'-I'+str(ANDROID/'system/vold'),
   '-I'+str(ANDROID/'system/core/libcutils/include'),'-I'+str(ANDROID/'system/libbase/include'),
   '-I'+str(ANDROID/'external/boringssl/src/include')]
  common=['-g','-O1','-pthread','-fno-omit-frame-pointer','-fno-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all',
   '-DUSE_FSCRYPT','-DTW_INCLUDE_FBE','-include',str(compat),*inc]
  objects=[];commands=[]
  c_names=re.findall(r'"([\w]+\.c)"',(libtar/'Android.bp').read_text())+['strlcpy.c']
  for name in c_names:
   src=libtar/name;dest=tmp/(name+'.o');cmd=['gcc','-std=gnu11','-D_GNU_SOURCE',*common,'-c',str(src),'-o',str(dest)]
   subprocess.run(cmd,check=True);commands.append(cmd);objects.append(dest)
  crypto=ANDROID/'out/soong/.intermediates/external/boringssl/libcrypto/linux_glibc_x86_64_static/libcrypto.a'
  cpp=['twrpTar.cpp','tarWrite.cpp','exclude.cpp','infomanager.cpp','oaes/oaes.cpp','test.cpp']
  cmd=['g++','-std=c++23',*common,'-no-pie',*[str(stage/n) for n in cpp],*[str(p) for p in objects],str(crypto),
   '-Wl,--wrap=stat','-Wl,--wrap=lstat','-Wl,--wrap=opendir','-Wl,--wrap=readdir','-Wl,--wrap=closedir','-Wl,--wrap=read','-Wl,--wrap=mknod','-Wl,--wrap=llistxattr','-Wl,--wrap=lsetxattr','-Wl,--wrap=open','-Wl,--wrap=futimens','-Wl,--wrap=lgetfilecon','-Wl,--wrap=lsetfilecon','-Wl,--wrap=getxattr','-Wl,--wrap=setxattr',
   '-l:libselinux.so.1','-lz','-o',str(tmp/'test')]
  subprocess.run(cmd,check=True);commands.append(cmd)
  pigz=tmp/'pigz';cmd=['gcc','-O2','-static','-DNOZOPFLI',*[str(SRC/'pigz'/n) for n in ['pigz.c','yarn.c','try.c']],'-pthread','-lz','-lm','-o',str(pigz)]
  subprocess.run(cmd,check=True);commands.append(cmd)
  assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
  results=[]
  for case in cases:
   wd=tmp/case;wd.mkdir();(wd/'.fixture').touch();(wd/'bin').mkdir();(wd/'dev').mkdir()
   shutil.copy2(pigz,wd/'bin/pigz');(wd/'dev/urandom').write_bytes(os.urandom(4096))
   env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',PATH='/bin')
   with (wd/'output.log').open('w') as log:
    proc=subprocess.Popen([str(tmp/'test'),case],cwd=wd,stdout=log,stderr=log,env=env,start_new_session=True)
    try:code=proc.wait(timeout=8)
    except subprocess.TimeoutExpired:code=124
    for entry in Path('/proc').iterdir():
     if not entry.name.isdigit():continue
     fd=None
     try:
      fd=os.pidfd_open(int(entry.name))
      if (entry/'cwd').resolve(strict=True).is_relative_to(wd):signal.pidfd_send_signal(fd,signal.SIGKILL)
     except OSError:pass
     finally:
      if fd is not None:os.close(fd)
    proc.wait(timeout=2)
    until=time.monotonic()+1
    while time.monotonic()<until:
     try:
      if os.waitpid(-1,os.WNOHANG)[0]==0:time.sleep(.005)
     except ChildProcessError:break
   record=dict(case=case,status='PASS' if code==0 else 'FAIL',returncode=code,output=(wd/'output.log').read_text(errors='replace'))
   results.append(record);print(record['status'],case,flush=True)
  for folder in [libtar,SRC/'pigz']:
   for p in folder.iterdir():
    if p.suffix in ['.c','.h','.bp']:shared[str(p)]=sha(p)
  shared[str(crypto)]=sha(crypto)
  for folder in ['system/libbase/include/android-base','external/boringssl/src/include/openssl']:
   for p in (ANDROID/folder).glob('*.h'):shared[str(p)]=sha(p)
  report=dict(status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',scope=__doc__.strip(),
   sources=sources,shared_sources=shared,test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/archive_pipeline_test.cpp',ROOT/'tests/archive_pipeline_stubs.json',ROOT/'tests/backup_session_test.py']},
   cases=results,compile_commands=commands,sanitizer='ASan + UBSan; inherited libtar allocation leaks tracked separately, LSan disabled',
   split_threshold=65536,pigz_sha256=sha(pigz),boundaries=['Private host chroot; no phone, physical block device, mounts, real fscrypt or UI.',
   'BoringSSL and codecs execute natively on host; not ARM64 execution or hardware crypto.',
   'Archive restores reuse original fixture mount path, matching current split archive path convention.'])
  args.report.write_text(json.dumps(report,indent=2)+'\n')
 return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
