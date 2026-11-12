#!/usr/bin/env python3
"""Execute actual digest driver/hash and BackupPartition caller on private files.

BoringSSL, serialization, ordinary file I/O, rename, fork and process exit run.
Mounts/UI/partition data creation/Android metadata/libbase helpers are fixtures.
Syscall-boundary failures and process exits do not simulate target power loss.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery')
ANDROID=REC.parents[1]
CASES=['plain-new','replace','long-name','short-write','eintr-write','zero-write','partial-write-error',
       'file-sync','file-sync-eintr','close','rename','dir-sync','dir-sync-eintr','create','dir-open','symlink','target-dir',
       'source-missing','crash-stage','crash-synced-stage','crash-rename','split-normal','split-failure',
       'caller-normal','caller-digest-failure','caller-cancel-after-digest','retry']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def method(text,signature):
 a=text.index(signature);b=text.index('{',a)+1;depth=1
 while depth:
  depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--source',type=Path,default=REC/'digest')
 parser.add_argument('--output',type=Path,required=True)
 args=parser.parse_args()
 crypto=ANDROID/'out/soong/.intermediates/external/boringssl/libcrypto/linux_glibc_x86_64_static/libcrypto.a'
 with tempfile.TemporaryDirectory(prefix='digest-publication-') as td:
  temp=Path(td);(temp/'gui2/console').mkdir(parents=True)
  headers={
   'data.hpp':'#pragma once\n#include <string>\nclass DataManager {public:static void GetValue(const std::string&,int&);};\n',
   'twcommon.h':'#pragma once\n#include <cstdio>\n#define LOGINFO(...) printf(__VA_ARGS__)\n#define LOGERR(...) fprintf(stderr,__VA_ARGS__)\n',
   'set_metadata.h':'#pragma once\nint tw_set_default_metadata(const char*);\n',
   'twrp_functions.hpp':'''#pragma once
#include <string>
namespace TWFunc {
std::string GetFilename(const std::string&);bool WriteToFile(const std::string&,const std::string&);
void SetPerformanceMode(bool);template<class...T>void GuiOperationText(T&&...){}
}
''',
   'gui2/console/stdio_adapter.h':'''#pragma once
#include <string>
void console_event(const std::string&);
namespace gui2_console {
template<class...T>void info(const std::string& s,T&&...){console_event(s);}
template<class...T>void warning(const std::string& s,T&&...){console_event(s);}
template<class...T>void log_error(const std::string& s,T&&...){console_event(s);}
inline std::string text(const std::string& s){return s;}
}
'''}
  for name,body in headers.items():(temp/name).write_text(body)
  caller=method((REC/'partitionmanager.cpp').read_text(),'bool TWPartitionManager::BackupPartition(')
  harness=(ROOT/'tests/digest_publication_test.cpp').read_text().replace('// PRODUCTION_BACKUP_PARTITION',caller)
  (temp/'test.cpp').write_text(harness)
  cmd=['g++','-std=c++23','-O1','-g','-Wall','-Wextra','-fsanitize=address,undefined',
       '-fno-sanitize-recover=all','-fno-omit-frame-pointer','-no-pie',
       '-I'+str(temp),'-I'+str(args.source),'-I'+str(REC/'digest'),'-I'+str(REC),
       '-I'+str(ANDROID/'system/libbase/include'),'-I'+str(ANDROID/'external/boringssl/src/include'),
       str(temp/'test.cpp'),str(args.source/'twrp_digest_driver.cpp'),str(REC/'digest/twrp_digest.cpp'),
       str(crypto),*['-Wl,--wrap='+f for f in ['open','mkostemp','write','fsync','close','rename']],'-o',str(temp/'test')]
  subprocess.run(cmd,check=True)
  cases=[]
  data=bytes(range(256))*2049+b'backup\x00payload\n'
  for algorithm in ['md5','sha256']:
   for case in CASES:
    cwd=temp/(algorithm+'-'+case);(cwd/'backup').mkdir(parents=True);(cwd/'.fixture').touch()
    (cwd/'backup/data.ext4.win').write_bytes(data)
    run=subprocess.run([str(temp/'test'),case,algorithm,hashlib.new(algorithm,data).hexdigest()],cwd=cwd,text=True,capture_output=True,timeout=15)
    cases.append(dict(algorithm=algorithm,case=case,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr))
    print(cases[-1]['status'],algorithm,case,flush=True)
  files=[args.source/'twrp_digest_driver.cpp',args.source/'twrp_digest_driver.hpp',REC/'digest/twrp_digest.cpp',REC/'digest/twrp_digest.hpp',REC/'partitionmanager.cpp',REC/'variables.h',crypto]
  files+=list((ANDROID/'system/libbase/include/android-base').glob('*.h'))
  files+=list((ANDROID/'external/boringssl/src/include/openssl').glob('*.h'))
  report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,
              sources={str(p):sha(p) for p in files},test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/digest_publication_test.cpp']},compile_command=cmd,
              boundaries=['No target power-loss, actual partition backup, complete RunBackup/GUI workflow, or Android metadata/SELinux execution.',
                          'BackupPartition body is original; part.Backup supplies fixture archive bytes, cancellation/settings/progress remain fixtures.',
                          'Directory-sync failure after rename keeps a complete new sidecar visible and returns failure; no rollback assertion.',
                          'Split publication is per file; earlier parts remain committed if a later part fails. No whole-backup atomicity claim.'])
  args.output.write_text(json.dumps(report,indent=2)+'\n')
 return 0 if report['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
