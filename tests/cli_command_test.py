#!/usr/bin/env python3
"""Execute original CLI main command assembly under ASan/UBSan.

FIFO open/read/write, capability commands and version/usage are fixtures. No
phone, actual FIFO, shell or command execution. Assert exact fixed record bytes,
zero padding and rejection before opening FIFOs for oversized argv.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from nested_partition_path_test import ROOT, SRC, method


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC/'orscmd/orscmd.cpp')
    ap.add_argument('--report', type=Path, required=True)
    args = ap.parse_args()
    body = method(args.source.read_text(), 'int main(').replace('int main(', 'int cli_main(', 1)
    code = r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <unistd.h>
#include <fcntl.h>
#include <cerrno>
#define ORS_INPUT_FILE "input"
#define ORS_OUTPUT_FILE "output"
static int opens=0,writes=0,closes=0;
static std::vector<unsigned char> sent;
static int fake_open(const char*,int){return ++opens;}
static ssize_t fake_write(int,const void* data,size_t n){++writes;sent.assign((const unsigned char*)data,(const unsigned char*)data+n);return n;}
static ssize_t fake_read(int,void*,size_t){return 0;}
static int fake_close(int){++closes;return 0;}
void print_usage(){}void print_version(){}int do_setcap(const char*,const char*){return 0;}int do_getcap(const char*){return 0;}
#define open fake_open
#define read fake_read
#define write fake_write
#define close fake_close
// MAIN
int main(int argc,char**argv){
 assert(argc>=2);std::string expected;std::vector<char*> params;params.push_back(argv[0]);
 for(int i=1;i<argc;i++){if(i>1)expected+=' ';expected+=argv[i];params.push_back(argv[i]);}
 params.push_back(nullptr);
 int result=cli_main(argc,params.data());
 if(expected.size()>1023){assert(result!=0);assert(opens==0&&writes==0&&closes==0);}
 else {
  assert(result==0);assert(opens==2&&writes==1&&closes==2);assert(sent.size()==1024);
  assert(memcmp(sent.data(),expected.data(),expected.size())==0);
  for(size_t i=expected.size();i<sent.size();i++)assert(sent[i]==0);
 }
 puts("cli_exact_zero_padded_record_or_reject_before_fifo=1");
}
'''.replace('// MAIN', body)
    cases = [
        ('single', ['wipe']), ('multiple', ['wipe','cache']),
        ('empty-argument', ['set','name','','value']),
        ('spaces-unicode', ['print','路径 with spaces']),
        ('max-single', ['x'*1023]), ('max-joined', ['print','x'*1017]),
        ('max-empty-final', ['x'*1022,'']),
        ('oversized-single', ['x'*1024]), ('oversized-joined', ['print','x'*1018]),
        ('separator-overflow', ['x'*1023,'']),
        ('many-args', ['x']*600), ('huge-arg', ['x'*8192]),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='cli-command-') as tmp:
        work = Path(tmp)
        (work/'test.cpp').write_text(code)
        command = ['g++','-std=c++23','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-pie','-no-pie',str(work/'test.cpp'),'-o',str(work/'test')]
        subprocess.run(command, check=True)
        for name, params in cases:
            run = subprocess.run([str(work/'test'),*params],capture_output=True,text=True,timeout=5)
            rows.append(dict(case=name,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr))
            print(rows[-1]['status'],name,flush=True)
    sources = [args.source,Path(__file__).resolve(),ROOT/'tests/nested_partition_path_test.py']
    report = dict(status='PASS' if all(c['status']=='PASS' for c in rows) else 'FAIL',scope=__doc__,cases=rows,
        sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},compile_command=command)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report['status']!='PASS'


if __name__ == '__main__':
    raise SystemExit(main())
