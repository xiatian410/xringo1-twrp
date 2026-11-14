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
    ap.add_argument('--ors', action='store_true', help='Join actual CLI wrapper/parser to the FIFO listener')
    args = ap.parse_args()
    backend = SRC/'gui2/backend/twrp_background_backend.cpp'
    harness = ROOT/'tests/cli_fifo_test.cpp'
    original = backend.read_text()
    for include in ['twrp_background_backend.h','data.hpp','openrecoveryscript.hpp','orscmd/orscmd.h','partitions.hpp','twcommon.h','twrp_operation.h']:
        original = original.replace('#include "'+include+'"','')
    if args.ors:
        return run_ors(args, original, backend)
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


def run_ors(args, original, backend):
    """Reuse the existing CLI/parser fixture and replace only its listener sink."""
    rows=[]
    with tempfile.TemporaryDirectory(prefix='cli-ors-joined-') as tmp:
        work=Path(tmp)
        subprocess.run(['python3',str(ROOT/'tests/ors_results_test.py'),'--cli','--emit-fixture',str(work/'fixture.cpp'),'--report',str(work/'unused.json')],check=True)
        source=(work/'fixture.cpp').read_text()
        source=source[:source.index('static std::atomic<bool> command_active=true;')]
        source=source.replace('#define gui_print(...) ((void)0)', '''
static FILE* mirrored=nullptr;
static void fixture_print(const char* format,...){if(!mirrored)return;va_list args;va_start(args,format);vfprintf(mirrored,format,args);va_end(args);}
#define gui_print fixture_print
''')
        source=source.replace('#include <atomic>','#include <cstdarg>\n#include <chrono>\n#include <thread>\n#include <fcntl.h>\n#include <sys/stat.h>\n#include "backend/twrp_background_backend.h"\n#include <atomic>',1)
        source=source.replace('struct DataManager {','struct DataManager {\n static int GetIntValue(const char*){return 0;}')
        source=source.replace('struct TWPartitionManager {','''struct TWPartitionManager {
 struct {int fd=-1;} uevent_pfd;
 void ProcessPendingUeventDevices(){}void RefreshPartitionListSnapshots(){}void ResetPendingUeventDevices(){}
 void ReadUevent(bool){}void ProcessAsyncDataSize(){}uint64_t PartitionListRevision(const string&){return 0;}
''')
        source=source.replace('static inline void(*call_after_cli_command)()=nullptr;', 'static inline void(*call_after_cli_command)()=nullptr;\n static void Call_After_CLI_Command(void(*fn)()){call_after_cli_command=fn;}')
        source=source.replace('static int callbacks=0, completions=0, completion=-1, decrypt_code=0, decrypt_calls=0, lookup_code=0;', 'static int callbacks=0, decrypt_code=0, decrypt_calls=0, lookup_code=0;static std::atomic<int> completions=0,completion=-1;')
        source += r'''
static void gui_set_FILE(FILE* fp){mirrored=fp;}
static void operation_start(const char*){}
static void operation_end(int status){completion=status;++completions;}
#define ORS_INPUT_FILE "orsin"
#define ORS_OUTPUT_FILE "orsout"
#include "backend.inc"
int main(int argc,char**argv){
 assert(argc==2);signal(SIGPIPE,SIG_IGN);string label=argv[1];expected_operation="wipe:/cache";succeeds=label!="wipe-failure"&&label!="script-failure";
 if(label=="script-success"||label=="script-failure"){ofstream script("source.txt");script<<"wipe cache\n";}
 if(label=="append-failure")filesystem::create_directory(SCRIPT_FILE_TMP);
 if(label=="decrypt-failure")decrypt_code=1;
 gui2_backend::twrp_background_backend backend;backend.start();
 {ofstream ready("ready");}
 auto end=std::chrono::steady_clock::now()+std::chrono::seconds(8);
 while(!filesystem::exists("stop")){
  auto start=std::chrono::steady_clock::now();backend.poll();
  assert(std::chrono::steady_clock::now()-start<std::chrono::milliseconds(200));
  assert(std::chrono::steady_clock::now()<end);
  if(completions==1&&!backend.command_running()&&!filesystem::exists("first-done")){
   bool failed=label=="wipe-failure"||label=="script-failure"||label=="unknown"||label=="decrypt-failure"||label=="missing-script"||label=="append-failure"||label=="long-command";
   assert(completion==(failed?1:0));
   if(label=="append-failure")filesystem::remove(SCRIPT_FILE_TMP);
   {ofstream ready("first-done");}
  }
  usleep(1000);
 }
 backend.stop();assert(completions==2&&completion==0);
 assert(!filesystem::exists(SCRIPT_FILE_TMP));
 puts("original_client_fifo_wrapper_parser_retry=1");
}
'''
        client=r'''
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>
#define ORS_INPUT_FILE "orsin"
#define ORS_OUTPUT_FILE "orsout"
void print_usage(){}void print_version(){}int do_setcap(const char*,const char*){return 0;}int do_getcap(const char*){return 0;}
'''+method(args.client_source.read_text(),'int main(')
        (work/'backend.inc').write_text(original);(work/'server.cpp').write_text(source);(work/'client.cpp').write_text(client)
        common=['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie']
        subprocess.run(common+[str(work/'client.cpp'),'-o',str(work/'client')],check=True)
        subprocess.run(common+['-I'+str(work),'-I'+str(SRC/'gui2'),'-I'+str(SRC),str(work/'server.cpp'),str(SRC/'twrp_operation_executor.cpp'),'-pthread','-o',str(work/'server')],check=True)
        cases=[('print',['print','first'],'first\n'),('wipe-success',['wipe','cache'],''),('wipe-failure',['wipe','cache'],''),('unknown',['unknown'],"command is: 'unknown' and there is no value\n"),('script-success',['runscript','source.txt'],''),('script-failure',['runscript','source.txt'],''),('decrypt-failure',['decrypt','fixture'],''),('missing-script',['runscript'],''),('append-failure',['wipe','cache'],''),('long-command',['print','x'*600],'')]
        for name,params,expected in cases:
            folder=work/name;folder.mkdir();listener=subprocess.Popen([str(work/'server'),name],cwd=folder,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                wait_file(folder/'ready',listener)
                first=subprocess.run([str(work/'client'),*params],cwd=folder,capture_output=True,timeout=5)
                wait_file(folder/'first-done',listener)
                second=subprocess.run([str(work/'client'),'print','after'],cwd=folder,capture_output=True,timeout=5)
                (folder/'stop').touch();out,err=listener.communicate(timeout=5)
                passed=first.returncode==0 and second.returncode==0 and listener.returncode==0 and first.stdout==expected.encode() and second.stdout==b'after\n'
                rows.append(dict(case=name,status='PASS' if passed else 'FAIL',client_returncodes=[first.returncode,second.returncode],listener_returncode=listener.returncode,first_stdout=first.stdout.decode(errors='replace'),retry_stdout=second.stdout.decode(errors='replace'),output=(out+err+first.stderr+second.stderr).decode(errors='replace')))
            finally:
                if listener.poll() is None:listener.kill();listener.communicate()
            print(rows[-1]['status'],name,flush=True)
    sources=[args.client_source,backend,ROOT/'tests/ors_results_test.py',Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py',SRC/'openrecoveryscript.cpp',SRC/'openrecoveryscript.hpp',SRC/'twrp_functions.cpp',SRC/'gui2/backend/twrp_background_backend.h',SRC/'gui2/backend/background_backend.h',SRC/'twrp_operation_executor.h',SRC/'twrp_operation_executor.cpp']
    scope='Original CLI main -> private real FIFO -> original listener/twcmd -> original CLI wrapper/append/parser and callback/listener reset, then a second client command in same server. Host ASan/UBSan. Copy/cache discovery/get/decrypt/partition/shell/console mirror/completion sink fixtures. Tests ten first-command cases plus retry; failed remote command still yields client0 under unchanged text protocol. No ARM64/full GUI/device, real partition/decryption or concurrent staging proof.'
    report=dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=scope,cases=rows,sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'


def wait_file(path,process):
    end=time.monotonic()+5
    while not path.exists() and time.monotonic()<end and process.poll() is None:time.sleep(.005)
    if not path.exists():
        if process.poll() is None:process.kill()
        out,err=process.communicate()
        raise RuntimeError((out+err).decode(errors='replace') or 'listener did not publish '+path.name)


if __name__=='__main__':
    raise SystemExit(main())
