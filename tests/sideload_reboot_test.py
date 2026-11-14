#!/usr/bin/env python3
"""Native sideload reboot COMD -> actual core/GUI or ORS -> GUI poll -> final router.

Real private processes/socket/epoll. Properties, USB/FUSE/MTP and DataManager,
capabilities, sync and final TwReboot are explicit doubles; no real reboot,
phone, bootloader/BCB or GUI rendering. Reuses audited lifecycle fixture preamble.
"""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
from nested_partition_path_test import ROOT,SRC,method

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--before',action='store_true');ap.add_argument('--source',type=Path,default=SRC);ap.add_argument('--cases',nargs='*');ap.add_argument('--report',type=Path,default=ROOT/'logs/sideload-reboot.json');args=ap.parse_args()
 files=['twrpinstall/adb_install.cpp','gui2/backend/twrp_sideload_backend.cpp','openrecoveryscript.cpp','gui2/backend/twrp_reboot_backend.cpp','gui2/gui2.cpp']
 paths={p:(ROOT/'logs/sideload-reboot-before'/p if args.before else args.source/p if (args.source/p).exists() else SRC/p) for p in files}
 core=paths[files[0]];backend=paths[files[1]];ors=paths[files[2]];reboot=paths[files[3]];gui=paths[files[4]]
 android=SRC.parents[1];clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++';host=android/'out/host/linux-x86/lib64'
 header=args.source/'twrpinstall/include/twinstall/adb_install.h'
 if not header.exists():header=SRC/'twrpinstall/include/twinstall/adb_install.h'
 rheader=SRC/'gui2/backend/twrp_reboot_backend.h'
 # The old implementation lacks handoff API; test-only no-op stubs let the same
 # behavioral assertions show the missing behavior, without implementing it.
 preamble=(ROOT/'tests/sideload_lifecycle_test.cpp').read_text().split('static void pipe_handler')[0]
 preamble=preamble.replace('static std::map<std::string,int> values;','static std::map<std::string,int> values;\nstatic std::string reboot_arg;')
 preamble=preamble.replace('static void SetValue(const std::string& k,int v)', 'static int SetValue(const std::string& k,const std::string& v){if(k=="tw_reboot_arg"){if(scenario=="write-fail"||scenario=="write-retry"||scenario=="write-cancel")return -1;reboot_arg=v;}return 0;}\n static void GetValue(const std::string& k,std::string& v){v=GetStrValue(k);}\n static void SetValue(const std::string& k,int v)')
 preamble=preamble.replace('static void SetValue(const std::string& k,const char* v){SetValue(k,std::atoi(v));}', 'static int SetValue(const std::string& k,const char* v){return SetValue(k,std::string(v));}')
 preamble=preamble.replace('return std::to_string(GetIntValue(k));','return k=="tw_reboot_arg"?reboot_arg:std::to_string(GetIntValue(k));')
 preamble=preamble.replace('return !(scenario=="usb-fail"&&value=="sideload");','return !(scenario=="usb-fail"&&value=="sideload")&&!(scenario=="restore-fail"&&value=="adb");')
 preamble=preamble.replace('scenario=="buffered-close"&&value=="sideload"','(scenario=="buffered-close"||scenario=="ack-fail")&&value=="sideload"')
 preamble=preamble.replace('struct PartitionManagerFixture {','struct PartitionManagerFixture {void UnlockBlockPartitions(){}void UpdateSystemDetails(){}')
 preamble=preamble.replace('namespace gui2_console {','namespace gui2_console {std::string text(const std::string& s){return s;}')
 code='#include "twrp_operation_executor.h"\n'+preamble+(ROOT/'tests/sideload_reboot_test.cpp').read_text()
 code=code.replace('// FIXED','#define FIXED_CORE 1').replace('// CORE_HEADER','\n'.join(x for x in header.read_text().splitlines() if not x.startswith('#include')))
 code=code.replace('// CORE',core.read_text()[core.read_text().index('using CommandFunction'):]).replace('// BACKEND_HEADER','\n'.join(x for x in (SRC/'gui2/backend/twrp_sideload_backend.h').read_text().splitlines() if not x.startswith('#include')))
 code=code.replace('// BACKEND',backend.read_text()[backend.read_text().index('namespace gui2_backend'):])
 code=code.replace('// REBOOT_HEADER','#include "twrp_operation_executor.h"\n#include "twrp_reboot_backend.h"')
 rmethods='\n'.join(method(reboot.read_text(),s) for s in ['bool twrp_reboot_backend::is_supported(', 'const char* twrp_reboot_backend::reboot_argument(', 'bool twrp_reboot_backend::request_reboot('])
 rmethods+='\ntwrp_reboot_backend::twrp_reboot_backend() = default;\n'
 if args.before:rmethods+='bool twrp_reboot_backend::take_external_reboot(){return false;}'
 else:rmethods+=method(reboot.read_text(),'bool twrp_reboot_backend::take_external_reboot(')
 code=code.replace('// REBOOT_METHODS',rmethods)
 code=code.replace('// GUI_METHODS', ('static void poll_external_reboot(){}\n' if args.before else method(gui.read_text(),'static void poll_external_reboot('))+'\n'+method(gui.read_text(),'static bool gui2_loop_should_exit('))
 code=code.replace('// FINAL_REBOOT',method((SRC/'twrp.cpp').read_text(),'static void Reboot('))
 branch=method(ors.read_text(),'else if (strcmp(command, "sideload") == 0)');code=code.replace('// ORS_BRANCH',branch[branch.index('{')+1:-1])
 code=code.replace('static int script_sideload(){','static int property_set(const char*,const char*);\nstatic int script_sideload(){')
 if args.before:code=code.replace('static int syncs=0,','bool TakeMiniAdbdRebootAction(Device::BuiltinAction*){return false;}\nstatic int syncs=0,')
 cases=['system','bootloader','fastboot','recovery','ors-system','ors-bootloader','ors-fastboot','ors-recovery','rescue','ack-fail','restore-fail','startup-gate','background-gate','worker-gate','unsupported-target','write-fail','wrong-token','pending-blocks-session','cancel-pending','storage-gate','write-retry','write-cancel','unsupported-retry']
 if args.cases:cases=args.cases
 # cancelled-token lifetime and completion cancellation are exercised directly
 # below using the core; GUI normal destructor must not cancel a finished job.
 rows=[]
 with tempfile.TemporaryDirectory(prefix='sideload-reboot-') as tmp:
  p=Path(tmp);(p/'test.cpp').write_text(code);exe=p/'test'
  cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-D__unused=__attribute__((unused))','-I'+str(SRC),'-I'+str(SRC/'minadbd/include'),'-I'+str(SRC/'gui2/backend'),'-I'+str(android/'system/libbase/include'),'-I'+str(android/'system/logging/liblog/include'),str(p/'test.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-L'+str(host),'-Wl,-rpath,'+str(host),'-Wl,--wrap=socketpair','-lbase','-llog','-lpthread','-o',str(exe)]
  subprocess.run(cmd,check=True);deps={str(clang):sha(clang)}
  for line in subprocess.check_output(['ldd',str(exe)],text=True).splitlines():
   match=re.search(r'(/[^\s()]+)',line)
   if match:dep=Path(match[1]);deps[str(dep)]=sha(dep)
  for name in cases:
   run=subprocess.run([str(exe),name],capture_output=True,text=True,timeout=12);row=dict(case=name,status='PASS' if run.returncode==0 else 'FAIL',exit=run.returncode,output=run.stdout+run.stderr);rows.append(row);print(row['status'],name,flush=True)
   if run.returncode:print(row['output'][-1200:],flush=True)
 bound=[*paths.values(),header,rheader,SRC/'gui2/backend/reboot_backend.h',SRC/'twrp_operation_executor.h',SRC/'twrp_operation_executor.cpp',SRC/'twrp.cpp',ROOT/'tests/sideload_lifecycle_test.cpp',Path(__file__).resolve(),ROOT/'tests/sideload_reboot_test.cpp']
 result=dict(status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',scope=__doc__,cases=rows,sources={str(p):sha(p) for p in bound},binary_dependencies=deps)
 destination=args.report
 if args.before and destination==ROOT/'logs/sideload-reboot.json':
  destination=ROOT/'logs/sideload-reboot-before.json'
 destination.write_text(json.dumps(result,indent=2)+'\n');return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
