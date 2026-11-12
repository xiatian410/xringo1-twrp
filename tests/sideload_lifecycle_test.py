#!/usr/bin/env python3
"""Original sideload core + GUI backend with private native minadbd subprocesses.

Real socketpair/fork/exec/epoll/send/kill/wait; USB properties, FUSE stat,
TWinstall_zip, MTP/cache/DataManager/operation feedback are explicit doubles.
Syscall wrappers inject errors and forbid signalling non-owned PIDs. No phone,
USB endpoint, ZIP updater, physical storage, reboot or GUI clicks execute.
"""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
from nested_partition_path_test import ROOT,SRC

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def body(p,start):return p.read_text()[p.read_text().index(start):]
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--before',action='store_true');ap.add_argument('--report',type=Path,default=ROOT/'logs/sideload-lifecycle.json');args=ap.parse_args()
 core=SRC/'twrpinstall/adb_install.cpp';backend=SRC/'gui2/backend/twrp_sideload_backend.cpp';header=SRC/'gui2/backend/twrp_sideload_backend.h'
 if args.before:
  core=ROOT/'logs/sideload-before/adb_install.cpp';backend=ROOT/'logs/sideload-before/twrp_sideload_backend.cpp';header=ROOT/'logs/sideload-before/twrp_sideload_backend.h'
 core_header=ROOT/'logs/sideload-before/adb_install.h' if args.before else SRC/'twrpinstall/include/twinstall/adb_install.h'
 android=SRC.parents[1];clang=android/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang++';host=android/'out/host/linux-x86/lib64'
 cases=['install-success','install-fail','fuse-missing','fuse-error','fork-fail','socket-fail','usb-fail','property-fail','exec-fail','wait-eintr','epoll-create-fail','epoll-add-fail','epoll-wait-fail','epoll-timeout','malformed','short-command','unsupported','reboot-command','buffered-close','cancel','cancel-before-spawn','destructor','reuse','busy','foreign-cancel','signal-preserved','broken-status','parser-short','parser-long','status-eintr','status-partial','status-zero','status-error']
 if args.before:cases=[c for c in cases if c not in ['status-zero','status-error']]
 code=(ROOT/'tests/sideload_lifecycle_test.cpp').read_text()
 code=code.replace('// CORE_HEADER','\n'.join(x for x in core_header.read_text().splitlines() if not x.startswith('#include')))
 code=code.replace('// CORE',body(core,'using CommandFunction'))
 code=code.replace('// BACKEND_HEADER','\n'.join(x for x in header.read_text().splitlines() if not x.startswith('#include')))
 code=code.replace('// BACKEND',body(backend,'namespace gui2_backend'))
 code=code.replace('// FIXED', '#define FIXED_CORE 1' if not args.before else '')
 reports=[]
 with tempfile.TemporaryDirectory(prefix='sideload-lifecycle-') as tmp:
  work=Path(tmp);(work/'test.cpp').write_text(code);exe=work/'test'
  cmd=[str(clang),'-std=c++23','-stdlib=libc++','-O1','-g','-D__unused=__attribute__((unused))','-I'+str(SRC/'minadbd/include'),'-I'+str(SRC/'gui2/backend'),'-I'+str(android/'system/libbase/include'),'-I'+str(android/'system/logging/liblog/include'),str(work/'test.cpp'),'-L'+str(host),'-Wl,-rpath,'+str(host),'-Wl,--wrap=socketpair','-lbase','-llog','-lpthread','-o',str(exe)]
  subprocess.run(cmd,check=True)
  dependencies={}
  for line in subprocess.check_output(['ldd',str(exe)],text=True).splitlines():
   match=re.search(r'(/[^\s()]+)',line)
   if match:dep=Path(match[1]);dependencies[str(dep)]=sha(dep)
  for name in cases:
   run=subprocess.run([str(exe),name],capture_output=True,text=True,timeout=12)
   row=dict(case=name,status='PASS' if run.returncode==0 else 'FAIL',exit=run.returncode,output=run.stdout+run.stderr);reports.append(row);print(row['status'],name,flush=True)
   if run.returncode:print(row['output'][-1500:],flush=True)
 bound=[core,core_header,backend,header,SRC/'gui2/backend/sideload_backend.h',SRC/'minadbd/include/minadbd/types.h',Path(__file__).resolve(),ROOT/'tests/sideload_lifecycle_test.cpp',ROOT/'tests/nested_partition_path_test.py']
 bound+=list((android/'system/libbase/include/android-base').glob('*.h'))
 result=dict(status='PASS' if all(r['status']=='PASS' for r in reports) else 'FAIL',scope=__doc__,cases=reports,sources={str(p):sha(p) for p in bound},binary_dependencies={str(clang):sha(clang),**dependencies})
 args.report.write_text(json.dumps(result,indent=2)+'\n');return result['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
