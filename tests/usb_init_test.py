#!/usr/bin/env python3
"""Execute production Android init parser/action scheduling with configfs/service boundaries."""
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];AOSP=Path('/root/AAA/twrp');REC=AOSP/'bootable/recovery';INIT=AOSP/'system/core/init';TREE=ROOT/'dtsrc/O1_asic_dual'
CASES=['adb-first','mtp-first','both-ready','rapid-none-mtp','disable-mtp','mtp-ready-lost','bind-error','link-error','fastboot','sideload','mtp-only','repeat-ready','mtp-ready-restored','adb-ready-lost','adb-service-died','owner-swap','rapid-flips','delayed-stop','start-error','stop-error','attribute-error','unbind-error','unlink-error','read-error','readback-error','publish-error','unknown-config','unknown-controller','extra-link','request-during-bind','readiness-during-bind','unmanaged-adb','adb-service-restarting','upstream-unbind','invalid-id','missing-id','configured-id','none-ack-stop','sideload-busy','sideload-early-ready','sideload-lost-ready','sideload-return']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def body(text,signature):
 a=text.index(signature)
 # The production function closes at column zero; preserve its bytes exactly.
 return text[a:text.index('\n}',a)+2]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--baseline',action='store_true');ap.add_argument('--report',type=Path,default=ROOT/'logs/usb-init.json');ap.add_argument('--cases',nargs='*');a=ap.parse_args()
 with tempfile.TemporaryDirectory(prefix='dijun-usb-init-') as tmp:
  tmp=Path(tmp);stage=tmp/'init';stage.mkdir();inc=tmp/'include';(inc/'android-base').mkdir(parents=True)
  names=['action.cpp','action_manager.cpp','action_parser.cpp','parser.cpp','tokenizer.cpp','import_parser.cpp']
  for p in INIT.glob('*.h'):shutil.copy2(p,stage/p.name)
  for n in names:shutil.copy2(INIT/n,stage/n)
  (stage/'subcontext.h').write_text('''#pragma once
#include "builtins.h"
namespace android::init {
inline constexpr const char kInitContext[]="u:r:init:s0";
class Subcontext { public:
Result<void> Execute(const std::vector<std::string>&){return Error()<<"unexpected subcontext";}
Result<std::vector<std::string>> ExpandArgs(const std::vector<std::string>&){return Error()<<"unexpected subcontext";}
const std::string& context()const{static std::string s;return s;}
bool PathMatchesSubcontext(const std::string&)const{return false;}
}; }
''')
  (inc/'android-base/properties.h').write_text('''#pragma once
#include <string>
namespace android::base {
std::string GetProperty(const std::string&,const std::string&);
bool SetProperty(const std::string&,const std::string&);
inline bool GetBoolProperty(const std::string& k,bool d){auto s=GetProperty(k,"");return s.empty()?d:s=="1"||s=="true";}
}
''')
  (inc/'android-base/logging.h').write_text('''#pragma once
#include <cassert>
#include <iostream>
#define LOG(x) std::cerr
#define PLOG(x) std::cerr
#define CHECK(x) assert(x)
namespace android::base {enum LogSeverity {VERBOSE,DEBUG,INFO,WARNING,ERROR,FATAL};inline LogSeverity GetMinimumLogSeverity(){return ERROR;}}
''')
  expand=body((INIT/'util.cpp').read_text(),'Result<std::string> ExpandProps(')
  (stage/'expand.cpp').write_text('#include <cstring>\n#include <android-base/properties.h>\n#include <android-base/logging.h>\n#include "util.h"\n#include "host_init_stubs.h"\nnamespace android::init {\n'+expand+'\n}\n')
  includes=[inc,stage,TREE/'profiles/runtime',AOSP/'system/libbase/include',AOSP/'external/fmtlib/include']
  files=[TREE/'profiles/runtime/usb_config.cpp']+[stage/n for n in names]+[stage/'expand.cpp',ROOT/'tests/usb_init_test.cpp']+[AOSP/'system/libbase'/n for n in ['chrono_utils.cpp','strings.cpp','stringprintf.cpp','errors_unix.cpp']]
  cmd=['g++','-std=c++23','-O1','-g','-pthread','-Wno-attributes','-DFMT_HEADER_ONLY','-DDIJUN_USB_CONFIG_TEST','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-include','algorithm','-include','cstring','-include','climits',*[f'-I{p}' for p in includes],*[str(p) for p in files],'-o',str(tmp/'test')]
  subprocess.run(cmd,check=True)
  common=ROOT/'backups/mtp-configfs-pre-fix/init.rc' if a.baseline else REC/'etc/init.rc'
  device=ROOT/'backups/mtp-configfs-pre-fix/init.recovery.usb.rc' if a.baseline else TREE/'recovery/root/init.recovery.usb.rc'
  cases=[]
  for case in a.cases or CASES:
   wd=tmp/case;wd.mkdir();shutil.copy2(common,wd/'init.rc');shutil.copy2(device,wd/'init.recovery.usb.rc');shutil.copy2(TREE/'recovery/root/init.recovery.O1_asic.rc',wd/'init.recovery.O1_asic.rc')
   # Another device using the common fallback does not import dijun's manager.
   if case=='unmanaged-adb':(wd/'init.recovery.usb.rc').write_text('')
   for n in ['init.recovery.logd.rc','init.recovery.ldconfig.rc','init.recovery.mksh.rc']:(wd/n).touch()
   r=subprocess.run([str(tmp/'test'),case],cwd=wd,capture_output=True,text=True,timeout=10)
   cases.append(dict(case=case,status='PASS' if r.returncode==0 else 'FAIL',returncode=r.returncode,output=r.stdout+r.stderr));print(cases[-1]['status'],case,flush=True)
  sources={str(p):sha(p) for p in [common,device,TREE/'recovery/root/init.recovery.O1_asic.rc',TREE/'profiles/runtime/usb_config.cpp',TREE/'profiles/runtime/usb_config.hpp']}
  shared={str(p):sha(p) for folder in [INIT,AOSP/'system/libbase/include',AOSP/'external/fmtlib/include'] for p in folder.rglob('*') if p.suffix in ['.cpp','.h']}
  for p in files:
   if p.is_relative_to(AOSP):shared[str(p)]=sha(p)
  report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,sources=sources,shared_sources=shared,test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/usb_init_test.cpp']},cases=cases,compile_command=cmd,boundaries=['Actual parser/tokenizer/import/action/property-trigger evaluation/command ordering and ExpandProps from current AOSP.','USB configfs, properties, service startup and irrelevant non-USB builtins are host boundaries; optional logd/ldconfig/mksh imports empty. No full init boot or physical UDC.'])
  a.report.write_text(json.dumps(report,indent=2)+'\n')
 return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
