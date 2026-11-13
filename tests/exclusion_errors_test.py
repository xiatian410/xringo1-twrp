#!/usr/bin/env python3
"""Execute production size walks with directory/stat I/O faults on private files.

Real libc walks and ASan/UBSan; wrappers inject only named failures. Old API is
invoked unchanged with completion initially true to expose missing error status.
No manager/mount/fscrypt/device or allocated-block estimate.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from backup_session_test import ROOT, SRC, method

CASES = ['normal', 'empty', 'missing-exclusion', 'missing-root', 'root-open',
         'nested-open', 'stat', 'read', 'close', 'excluded-open', 'excluded-stat',
         'excluded-read', 'excluded-close', 'cancel', 'excluded-cancel', 'stale-errno']
MAIN = r'''
#include "twrp_functions.hpp"
#include "exclude.hpp"
#include <fstream>
#include <map>
#include <unistd.h>
namespace fs=std::filesystem;
std::string fault, base;
bool fired=false;
std::map<DIR*,std::string> dirs;
extern "C" DIR* __real_opendir(const char*);
extern "C" dirent* __real_readdir(DIR*);
extern "C" int __real_closedir(DIR*);
extern "C" int __real_lstat(const char*,struct stat*);
bool trigger(const std::string& op,const std::string& p) {
 if(fired)return false;
 bool match=(fault=="root-open"&&op=="open"&&p==base)||
  (fault=="nested-open"&&op=="open"&&p==base+"/sub")||
  (fault=="stat"&&op=="stat"&&p==base+"/sub/file")||
  (fault=="read"&&op=="read"&&p==base)||
  (fault=="close"&&op=="close"&&p==base)||
  (fault=="excluded-open"&&op=="open"&&p==base+"/sub")||
  (fault=="excluded-stat"&&op=="stat"&&p==base+"/sub/file")||
  (fault=="excluded-read"&&op=="read"&&p==base+"/sub")||
  (fault=="excluded-close"&&op=="close"&&p==base+"/sub");
 if(match){fired=true;errno=EIO;}return match;
}
extern "C" DIR* __wrap_opendir(const char*p){if(trigger("open",p))return nullptr;auto*d=__real_opendir(p);if(d)dirs[d]=p;return d;}
extern "C" dirent* __wrap_readdir(DIR*d){if(trigger("read",dirs[d]))return nullptr;auto*e=__real_readdir(d);if(e&&fault=="stale-errno")errno=EIO;return e;}
extern "C" int __wrap_closedir(DIR*d){bool fail=trigger("close",dirs[d]);dirs.erase(d);int r=__real_closedir(d);if(fail){errno=EIO;return -1;}return r;}
extern "C" int __wrap_lstat(const char*p,struct stat*s){if(trigger("stat",p))return -1;return __real_lstat(p,s);}
// HELPER
int main(int argc,char**argv){
 fault=argv[1];base=argv[2];fs::create_directories(base+"/sub");
 if(fault!="empty") {std::ofstream(base+"/keep")<<"1234567";std::ofstream(base+"/sub/file")<<"1234567890123";}
 TWExclude e;std::atomic<bool> cancel{fault=="cancel"||fault=="excluded-cancel"};
 bool excluded=fault.starts_with("excluded-")||fault=="missing-exclusion";
 if(excluded)e.add_absolute_dir(base+(fault=="missing-exclusion"?"/absent":"/sub"));
 bool complete=true;errno=0;
 uint64_t n;
 if(excluded)n=EXCLUDED_CALL;
 else n=FOLDER_CALL;
 int error=errno;
 bool fail=!(fault=="normal"||fault=="empty"||fault=="missing-exclusion"||fault=="stale-errno");
 if(complete==fail||!dirs.empty()||(fail&&n!=0))return 1;
 if(fail&&error!=(cancel?ECANCELED:(fault=="missing-root"?ENOENT:EIO)))return 2;
 if(!fail&&n!=((fault=="empty"||fault=="missing-exclusion")?0:20))return 3;
 if(fail&&!cancel&&fault!="missing-root"&&!fired)return 4;
 puts("complete_status=1 no_partial_publication=1 directories_closed=1");return 0;
}
'''

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source',type=Path,default=SRC)
 ap.add_argument('--report',type=Path,default=ROOT/'logs/exclusion-errors.json')
 a=ap.parse_args(); rows=[]
 with tempfile.TemporaryDirectory(prefix='exclusion-errors-') as tmp:
  w=Path(tmp)
  for n in ['exclude.cpp','exclude.hpp']:(w/n).write_bytes((a.source/n).read_bytes())
  # Keep the same narrow include substitutes as the existing walk fixture.
  includes={'libtar/libtar.h':'','twcommon.h':'#define LOGINFO(...) ((void)0)\n',
    'gui2/console/stdio_adapter.h':'namespace gui2_console {template<class... T>void log_error(T...) {}}\n',
    'twrp_functions.hpp':'#include <cstring>\n#include <string>\n#include <filesystem>\n#include <dirent.h>\n#include <sys/stat.h>\nclass TWFunc {public:static std::string RemoveTrailingSlashes(const std::string&,bool=false);};\n'}
  for n,t in includes.items():p=w/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
  modern='bool* complete' in (a.source/'exclude.hpp').read_text()
  helper=method((SRC/'twrp_functions.cpp').read_text(),'std::string TWFunc::RemoveTrailingSlashes(')
  h=MAIN.replace('// HELPER',helper).replace('EXCLUDED_CALL','e.Get_Exclusions_Folder_Size(&cancel'+(', &complete' if modern else '')+')').replace('FOLDER_CALL','e.Get_Folder_Size(base+(fault=="missing-root"?"/absent":""),false,&cancel'+(', &complete' if modern else '')+')')
  (w/'main.cpp').write_text(h)
  cmd=['g++','-std=c++23','-O1','-g','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-I'+str(w),str(w/'exclude.cpp'),str(w/'main.cpp'),'-o',str(w/'test'),*['-Wl,--wrap='+f for f in ['opendir','readdir','closedir','lstat']]]
  subprocess.run(cmd,check=True)
  for name in CASES:
   r=subprocess.run([str(w/'test'),name,str(w/name)],capture_output=True,text=True,timeout=10)
   rows.append(dict(case=name,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr));print(name,rows[-1]['status'],flush=True)
 paths=[a.source/'exclude.cpp',a.source/'exclude.hpp',SRC/'twrp_functions.cpp',Path(__file__).resolve(),ROOT/'tests/backup_session_test.py']
 result=dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,cases=rows,sources={str(p):sha(p) for p in paths},compile_command=cmd)
 a.report.write_text(json.dumps(result,indent=2)+'\n');return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
