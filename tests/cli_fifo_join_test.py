#!/usr/bin/env python3
"""Join original CLI main to original listener with private host FIFOs/processes.

Real open/read/write/stdio/select/fork/exec/wait and executor execute. ORS command
execution, settings/console mirror and partition work are fixtures. Compare exact
CLI output over read-buffer boundaries; no real command, GUI or device operation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from nested_partition_path_test import ROOT, SRC, method


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--client-source', type=Path, default=SRC/'orscmd/orscmd.cpp')
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    backend = SRC/'gui2/backend/twrp_background_backend.cpp'
    harness = ROOT/'tests/cli_fifo_test.cpp'
    original = backend.read_text()
    for include in ['twrp_background_backend.h','data.hpp','openrecoveryscript.hpp','orscmd/orscmd.h','partitions.hpp','twcommon.h','twrp_operation.h']:
        original = original.replace('#include "'+include+'"','')
    server = harness.read_text().split('int main(int argc,char**argv)')[0]
    start = server.index(' static int Run_CLI_Command(')
    end = server.index('\n};',start)
    server = server[:start]+''' static int Run_CLI_Command(const char* text){executed=text;++executions;
 std::string bytes;size_t size=std::strtoul(std::getenv("CLI_RESPONSE_BYTES"),nullptr,10);
 for(size_t i=0;i<size;++i)bytes.push_back('A'+i%26);
 assert(mirrored);assert(fwrite(bytes.data(),1,bytes.size(),mirrored)==bytes.size());if(callback)callback();return 0;}
'''+server[end:]
    server += r'''
int main(int argc,char**argv){
 assert(argc==4);signal(SIGPIPE,SIG_IGN);input=std::string(argv[1])+"/orsin";output=std::string(argv[1])+"/orsout";
 gui2_backend::twrp_background_backend backend;backend.start();
 if(std::string(argv[3])=="busy")busy=1;
 if(std::string(argv[3])=="shutdown")assert(twrp_operation_executor::instance().reserve_shutdown());
 {FILE* ready=fopen((std::string(argv[1])+"/ready").c_str(),"w");assert(ready);fclose(ready);}
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(8);
 while(access((std::string(argv[1])+"/stop").c_str(),F_OK)!=0){tick(backend);assert(std::chrono::steady_clock::now()<deadline);usleep(1000);}
 backend.stop();bool reject=std::string(argv[3])!="normal";
 assert(executions==(reject?0:1));if(!reject)assert(executed==argv[2]);
 puts("original_cli_listener_joined_exact_command=1");
}
'''
    client = r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>
#define ORS_INPUT_FILE "orsin"
#define ORS_OUTPUT_FILE "orsout"
void print_usage(){}void print_version(){}int do_setcap(const char*,const char*){return 0;}int do_getcap(const char*){return 0;}
// MAIN
'''.replace('// MAIN',method(args.client_source.read_text(),'int main('))
    cases = [('ordinary',['print','hello'],20,'normal'),('arguments',['set','name','value with spaces'],30,'normal'),
        ('max-command',['x'*1023],31,'normal'),('busy',['print','hello'],0,'busy'),
        ('unsupported',['reloadtheme'],0,'unsupported'),('shutdown',['print','hello'],0,'shutdown')]
    cases += [('output-'+str(n),['print','fixture'],n,'normal') for n in [509,510,511,512,513,1024,2049]]
    rows = []
    with tempfile.TemporaryDirectory(prefix='cli-fifo-joined-') as tmp:
        work=Path(tmp);(work/'backend.inc').write_text(original);(work/'server.cpp').write_text(server);(work/'client.cpp').write_text(client)
        common=['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie']
        subprocess.run(common+[str(work/'client.cpp'),'-o',str(work/'client')],check=True)
        subprocess.run(common+['-I'+str(work),'-I'+str(SRC/'gui2'),'-I'+str(SRC),str(work/'server.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-pthread','-o',str(work/'server')],check=True)
        import os
        for name,params,size,mode in cases:
            folder=work/name;folder.mkdir();env=os.environ.copy();env['CLI_RESPONSE_BYTES']=str(size)
            listener=subprocess.Popen([str(work/'server'),str(folder),' '.join(params),mode],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            deadline=time.monotonic()+5
            while not(folder/'ready').exists() and time.monotonic()<deadline and listener.poll() is None:time.sleep(.005)
            if not(folder/'ready').exists():
                listener.kill();out,err=listener.communicate();raise RuntimeError((out+err).decode(errors='replace'))
            try:
                run=subprocess.run([str(work/'client'),*params],cwd=folder,capture_output=True,timeout=5)
                expected=(b'Failed, operation in progress\n' if mode=='busy' else b'Failed, not supported\n' if mode=='unsupported' else b'Failed, shutdown in progress\n' if mode=='shutdown' else bytes(65+i%26 for i in range(size)))
                (folder/'stop').touch();out,err=listener.communicate(timeout=5)
                passed=run.returncode==0 and listener.returncode==0 and run.stdout==expected
                rows.append(dict(case=name,status='PASS' if passed else 'FAIL',client_returncode=run.returncode,listener_returncode=listener.returncode,expected_bytes=len(expected),actual_bytes=len(run.stdout),output_sha256=hashlib.sha256(run.stdout).hexdigest(),expected_sha256=hashlib.sha256(expected).hexdigest(),output=(out+err+run.stderr).decode(errors='replace')))
                print(rows[-1]['status'],name,flush=True)
            finally:
                if listener.poll() is None:listener.kill();listener.communicate()
    sources=[args.client_source,backend,harness,Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py',SRC/'gui2/backend/twrp_background_backend.h',SRC/'gui2/backend/background_backend.h',SRC/'twrp_operation_executor.h',SRC/'twrp_operation_executor.cpp']
    report=dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,cases=rows,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'


if __name__=='__main__':
    raise SystemExit(main())
