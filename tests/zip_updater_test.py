#!/usr/bin/env python3
"""Execute production ZIP updater command, fork/exec pipe parser and child wait.

The compiled host updater only emits protocol/creates a private marker. Real
fork, execve, pipe, stdio and waitpid execute; pipe/fork/fdopen failure injection
is explicit. Progress sink is checked, logs are captured. No package extraction,
ZIP signature/digest verification, payload/OTA engine, device or USB execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import method,ROOT,SRC

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SRC/'twrpinstall/twinstall.cpp')
    ap.add_argument('--report',type=Path,default=ROOT/'logs/zip-updater.json')
    args=ap.parse_args()
    text=args.source.read_text()
    bodies=[]
    if 'static bool ParseUpdaterFraction(' in text:
        bodies+=[method(text,'static bool ParseUpdaterFraction('),method(text,'static bool ParseUpdaterSeconds(')]
    bodies += [method(text,'static int Run_Update_Binary('),
               method((SRC/'twrpinstall/installcommand.cpp').read_text(),'int\nupdate_binary_command('),
               method((SRC/'twrp_functions.cpp').read_text(),'int TWFunc::WaitForChild(')]
    # C++ declarations mirror public production call signatures; full methods unchanged.
    declarations='int update_binary_command(const char*,int,int,std::vector<std::string>*);\n'
    names=['normal','signed-progress','empty','missing-fraction','missing-seconds','missing-set','nan',
           'infinite','negative','too-large','bad-number','bad-seconds','negative-seconds','huge-seconds',
           'log-empty','exit-error','signal','missing-executable','pipe-error','fork-error','fdopen-error','unknown-type']
    results=[]
    with tempfile.TemporaryDirectory(prefix='zip-updater-') as temp:
        work=Path(temp);harness=work/'test.cpp'
        harness.write_text((ROOT/'tests/zip_updater_test.cpp').read_text().replace('// PRODUCTION_METHODS',declarations+'\n'.join(bodies)))
        cmd=['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-no-pie',
             str(harness),*['-Wl,--wrap='+n for n in ['pipe','fork','fdopen']],'-o',str(work/'test')]
        subprocess.run(cmd,check=True)
        subprocess.run(['g++','-std=c++23','-O1',str(ROOT/'tests/zip_updater_fixture.cpp'),'-o',str(work/'updater')],check=True)
        for name in names:
            wd=work/name;wd.mkdir();(wd/'package.fixture').write_text(name)
            if name!='missing-executable':(wd/'updater').symlink_to(work/'updater')
            try:
                run=subprocess.run([str(work/'test'),name,str(int(name in ['normal','signed-progress','empty','log-empty']))],
                                   cwd=wd,capture_output=True,text=True,timeout=10)
                row=dict(case=name,status='PASS' if run.returncode==0 else 'FAIL',exit=run.returncode,output=run.stdout+run.stderr)
            except subprocess.TimeoutExpired as e:
                row=dict(case=name,status='FAIL',exit='timeout',output=str(e))
            results.append(row);print(row['status'],name,flush=True)
    bound=[args.source,SRC/'twrpinstall/installcommand.cpp',SRC/'twrp_functions.cpp',Path(__file__).resolve(),ROOT/'tests/zip_updater_test.cpp',ROOT/'tests/zip_updater_fixture.cpp',ROOT/'tests/nested_partition_path_test.py']
    report=dict(status='PASS' if all(c['status']=='PASS' for c in results) else 'FAIL',scope=__doc__,cases=results,
                sources={str(p):sha(p) for p in bound},compile_command=cmd)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
