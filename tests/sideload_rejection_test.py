#!/usr/bin/env python3
"""Original sideload ApplyUpdatePayload rejection/loop boundary with explicit service doubles.

Runs original header parsing and error publication. Boot control, hardware,
attempter scheduling and message loop are doubles; no actual OTA writes occur.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
from nested_partition_path_test import ROOT,method
from haptics_ui_test import sha
ENGINE=Path('/root/AAA/twrp/system/update_engine')
HARNESS=r'''
#include <cassert>
#include <map>
#include <memory>
#include <ostream>
#include <string>
#include <vector>
#include "update_engine/common/error.h"
using std::string;using std::vector;
struct Sink {template<class T>Sink&operator<<(const T&){return *this;}};
#define LOG(x) Sink()
static bool boot_ok=true,hardware_ok=true;static unsigned loops=0,applies=0,inits=0;
namespace brillo {
struct BaseMessageLoop{void SetAsCurrent(){}void Run(){++loops;}};
struct AsynchronousSignalHandler{void Init(){}};
struct FileStream{static int FromFileDescriptor(int64_t,bool,void*){return 0;}};
namespace string_utils {bool SplitAtFirst(const string&s,const string&at,string*a,string*b,bool){auto n=s.find(at);if(n==string::npos)return false;*a=s.substr(0,n);*b=s.substr(n+at.size());return true;}}
}
namespace chromeos_update_engine {
struct Subprocess{void Init(brillo::AsynchronousSignalHandler*){}};
struct MemoryPrefs{};struct BootControlInterface{};struct HardwareInterface{};
namespace boot_control {std::unique_ptr<BootControlInterface>CreateBootControl(){return boot_ok?std::make_unique<BootControlInterface>():nullptr;}}
namespace hardware {std::unique_ptr<HardwareInterface>CreateHardware(){return hardware_ok?std::make_unique<HardwareInterface>():nullptr;}}
// ORIGINAL_PARSER
struct SideloadDaemonState{explicit SideloadDaemonState(int){}ErrorCode error_code(){return ErrorCode::kSuccess;}};
struct UpdateAttempterAndroid {
 UpdateAttempterAndroid(SideloadDaemonState*,MemoryPrefs*,BootControlInterface*,HardwareInterface*,void*){}
 void Init(){++inits;}
 bool ApplyPayload(const string&,int64_t,int64_t,const vector<string>&headers,Error*error){
  ++applies;std::map<string,string> parsed;
  if(!ParseKeyValuePairHeaders(headers,&parsed,error))return false;
  if(parsed.count("REJECT")){if(error)error->error_code=ErrorCode::kUpdateProcessing;return false;}
  if(parsed.count("REJECT_UNSET"))return false;
  return true;
 }
};
// ORIGINAL_SIDELOAD
}
int main(int argc,char**argv){
 using namespace chromeos_update_engine;assert(argc==2);string label=argv[1];vector<string> headers;
 ErrorCode expected=ErrorCode::kSuccess;
 if(label=="accepted")headers={"FILE_SIZE=1"};
 else if(label=="malformed"){headers={"invalid"};expected=ErrorCode::kError;}
 else if(label=="duplicate"){headers={"FILE_SIZE=1","FILE_SIZE=2"};expected=ErrorCode::kError;}
 else if(label=="rejected"){headers={"REJECT=1"};expected=ErrorCode::kUpdateProcessing;}
 else if(label=="rejected-unset"){headers={"REJECT_UNSET=1"};expected=ErrorCode::kError;}
 else if(label=="no-boot-control"){boot_ok=false;expected=ErrorCode::kError;}
 else if(label=="no-hardware"){hardware_ok=false;expected=ErrorCode::kError;}
 else assert(false);
 auto code=ApplyUpdatePayload("file:///fixture/never-open",0,1,headers,-1);
 assert(code==expected);assert(loops==(label=="accepted"?1u:0u));
 assert(applies==((boot_ok&&hardware_ok)?1u:0u));
 printf("PASS %s code=%d loops=%u applies=%u\n",argv[1],static_cast<int>(code),loops,applies);
}
'''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ENGINE/'aosp/sideload_main.cc');ap.add_argument('--report',type=Path,default=ROOT/'logs/sideload-rejection.json');args=ap.parse_args()
 parser=ENGINE/'aosp/update_attempter_android.cc';text=parser.read_text()
 methods='\n\n'.join(method(text,s) for s in ['bool LogAndSetGenericError(', 'bool ParseKeyValuePairHeaders('])
 code=HARNESS.replace('// ORIGINAL_PARSER',methods).replace('// ORIGINAL_SIDELOAD',method(args.source.read_text(),'ErrorCode ApplyUpdatePayload('))
 with tempfile.TemporaryDirectory(prefix='sideload-reject-') as tmp:
  p=Path(tmp);(p/'test.cpp').write_text(code);subprocess.run(['g++','-std=c++20','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(ENGINE.parent),str(p/'test.cpp'),'-o',str(p/'test')],check=True);cases=[]
  for label in ['accepted','malformed','duplicate','rejected','rejected-unset','no-boot-control','no-hardware']:
   r=subprocess.run([str(p/'test'),label],capture_output=True,text=True,timeout=5);cases.append(dict(case=label,status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr));print(cases[-1],flush=True)
 paths=[args.source,parser,ENGINE/'common/error.h',ENGINE/'common/error_code.h',Path(__file__),ROOT/'tests/nested_partition_path_test.py',ROOT/'tests/haptics_ui_test.py'];report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in paths});args.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
