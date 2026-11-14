#!/usr/bin/env python3
"""Run production restore-session planning, raw transfer and backup digests.

Actual manager methods, raw-copy methods and complete digest sources execute.
Ordinary files emulate block targets; mount/UI/default metadata and file-archive
extraction are substitutes. Real BoringSSL hashes and host file I/O are used.
No physical block device or Android service is accessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
ANDROID=SRC.parents[1]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def method(text,signature):
    a=text.index(signature);b=text.index('{',a)+1;depth=1
    while depth:
        depth+=(text[b]=='{')-(text[b]=='}');b+=1
    return text[a:b]

CASES=['normal','after-cancel','unknown-first','unknown-last','empty-selection','no-delimiter',
       'list-fifo','list-split-fifo','list-directory','list-symlink','list-empty','list-gap',
       'list-encrypted-thread','list-normal','list-split',
       'duplicates','parent-child','parent-child-selected','child-filesystem','child-bad-digest',
       'second-bad-digest','second-missing','missing-without-digest','child-removed','child-readonly',
       'second-readonly','second-absent','second-oversized','target-missing','target-ordinary',
       'target-ioctl-error','source-empty','source-symlink','source-directory','source-fifo',
       'invalid-filesystem','split-raw','traversal-name','size-overflow','stale-open','bad-open',
       'mount-failure','restore-failure','cancel-preflight','cancel-between','cancel-last',
       'manifest-incomplete','manifest-mismatch',
       'split-normal','split-threaded','split-bad-thread','split-missing-first','split-gap',
       'split-thread-gap','split-ambiguous','split-unsupported-thread','split-long-index',
       'digest-missing-file','digest-no-sidecar','digest-malformed','digest-wrong-name',
       'digest-uppercase','digest-md5','make-threaded','make-missing',
       'digest-fifo','digest-fifo-sha256','digest-fifo-md5','digest-fifo-md5sum',
       'digest-directory','digest-oversized','digest-limit','digest-symlink',
       'second-fifo-sidecar','second-oversized-sidecar']

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SRC)
    ap.add_argument('--report',type=Path,default=ROOT/'logs/restore-session.json')
    ap.add_argument('--cases',nargs='+',choices=CASES,help='Run only a named regression subset')
    args=ap.parse_args()
    manager=args.source/'partitionmanager.cpp'
    pm=manager.read_text();part=(SRC/'partition.cpp').read_text()
    signatures=['bool TWPartitionManager::RestorePartition(', 'int TWPartitionManager::RunRestore(',
                'void TWPartitionManager::SetRestoreFiles(', 'int TWPartitionManager::CheckBackupCancel(']
    code='\n'.join(method(pm,s) for s in signatures)
    code+='\n'+'\n'.join(method(part,s) for s in ['bool TWPartition::RawReadWrite(',
                  'bool TWPartition::RestoreImage(', 'std::string TWPartition::GetRestoreFileSystem('])
    fs_start=part.index('constexpr std::array fs_list =')
    code+='\n'+part[fs_start:part.index('\n}',fs_start)+3]
    code+='\n'+method(part,'bool TWPartition::IsFileSystem(')
    crypto=ANDROID/'out/soong/.intermediates/external/boringssl/libcrypto/linux_glibc_x86_64_static/libcrypto.a'
    with tempfile.TemporaryDirectory(prefix='dijun-restore-session-',dir='/tmp') as temp:
        temp=Path(temp)
        (temp/'gui2/console').mkdir(parents=True)
        (temp/'data.hpp').write_text('''#pragma once
#include <string>
class DataManager {public:
 static void SetValue(const std::string&,const std::string&);
 static void SetValue(const std::string&,int);
 static void GetValue(const std::string&,std::string&);
 static void GetValue(const std::string&,int&);
 static void SetProgress(double);
};
''')
        (temp/'twcommon.h').write_text('#pragma once\n#include <cstdio>\n#define LOGINFO(...) printf(__VA_ARGS__)\n#define LOGERR(...) printf(__VA_ARGS__)\n')
        (temp/'set_metadata.h').write_text('#pragma once\nint tw_set_default_metadata(const char*);\nint tw_get_default_metadata(const char*);\n')
        (temp/'twrp_functions.hpp').write_text('''#pragma once
#include <string>
#include <vector>
namespace TWFunc {
 std::string GetFilename(const std::string&);
 bool IsPathExists(const std::string&);
 bool WriteToFile(const std::string&,const std::string&);
 std::vector<std::string> SplitString(const std::string&,char,bool);
 uint64_t GetFileSize(const std::string&);
 int GetFileType(const std::string&);
 void SetPerformanceMode(bool);
 template<class...T> void GuiOperationText(T&&...) {}
}
''')
        (temp/'gui2/console/stdio_adapter.h').write_text('''#pragma once
#include <string>
void console_event(const std::string&);
namespace gui2_console {
 template<class...T> void info(const std::string& k,T&&...) {console_event(k);}
 template<class...T> void warning(const std::string& k,T&&...) {console_event(k);}
 template<class...T> void log_error(const std::string& k,T&&...) {console_event(k);}
 template<class...T> void highlight(const std::string& k,T&&...) {console_event(k);}
 inline std::string text(const std::string& s) {return s;}
}
''')
        harness=(ROOT/'tests/restore_session_test.cpp').read_text()
        file_type=method((SRC/'twrp_functions.cpp').read_text(),'ArchiveType TWFunc::GetFileType(')
        harness=harness.replace('// FILE_TYPE_METHOD',file_type.replace('ArchiveType TWFunc::','int '))
        const=' const' if 'RunRestore(const std::string& restore_name) const' in pm else ''
        harness=harness.replace('// RUN_RESTORE_DECL','int RunRestore(const std::string&)'+const+';')
        harness=harness.replace('// PRODUCTION_METHODS',code)
        (temp/'test.cpp').write_text(harness)
        digest=args.source/'digest'
        cmd=['g++','-std=c++23','-O1','-g','-pthread','-Wall','-Wextra','-Wno-unused-parameter',
             '-Wno-missing-field-initializers','-fsanitize=address,undefined','-fno-sanitize-recover=all',
             '-fno-omit-frame-pointer','-no-pie','-I'+str(temp),'-I'+str(digest),'-I'+str(SRC/'digest'),
             '-I'+str(SRC),'-I'+str(ANDROID/'system/libbase/include'),
             '-I'+str(ANDROID/'external/boringssl/src/include'),str(temp/'test.cpp'),
             str(digest/'twrp_digest_driver.cpp'),str(SRC/'digest/twrp_digest.cpp'),str(crypto),
             '-Wl,--wrap=sync','-o',str(temp/'test')]
        subprocess.run(cmd,check=True)
        results=[]
        for case in args.cases or CASES:
            wd=temp/case;wd.mkdir();(wd/'.fixture').touch()
            try:
                r=subprocess.run([str(temp/'test'),case],cwd=wd,capture_output=True,text=True,timeout=10)
            except subprocess.TimeoutExpired as error:
                r=subprocess.CompletedProcess([],124,stdout='',stderr='Timed out (blocked fixture I/O): '+str(error))
            results.append(dict(case=case,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr))
            print(results[-1]['status'],case,flush=True)
        sources=[manager,digest/'twrp_digest_driver.cpp',digest/'twrp_digest_driver.hpp']
        shared=[SRC/'backup_manifest.hpp',SRC/'partition.cpp',SRC/'twrp_functions.cpp', SRC/'digest/twrp_digest.cpp',SRC/'digest/twrp_digest.hpp',SRC/'variables.h',
                SRC/'twrp_operation_executor.h',crypto]
        shared+=list((ANDROID/'external/boringssl/src/include/openssl').glob('*.h'))
        shared+=list((ANDROID/'system/libbase/include/android-base').glob('*.h'))
        report=dict(status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',scope=__doc__.strip(),
                    sources={str(p):sha(p) for p in sources},shared_sources={str(p):sha(p) for p in shared},
                    test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/restore_session_test.cpp']},
                    cases=results,compile_command=cmd,
                    boundaries=['Does not execute tar decompression/extraction, hardware partition mounting or encryption.',
                                'Digest sources and BoringSSL are real; libbase string/read helpers and GUI/default metadata are substitutes.',
                                'Uses actual raw-copy body with file-backed block metadata/ioctl substitutes; cannot prove rollback or concurrent media stability.',
                                'No backup cancel-worker or full GUI start/acknowledge lifecycle execution.'])
        args.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
