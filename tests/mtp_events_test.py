#!/usr/bin/env python3
"""Production native/compat FunctionFS event lifecycle, host pipes and AIO fault boundaries."""
import argparse,hashlib,json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery'); AOSP=REC.parents[1]
CASES=['ordered','copy-buffer','zero','negative','null','oversize','before-start','after-close','double-close','blocked-close','blocked-destructor','bounded-queue','concurrent','close-race','reconnect','disconnect','submit-eintr','submit-eagain','submit-error','short-completion','error-completion','cancel-pending','setup-error','fcntl-error','cancel-async','cancel-completed','event-timeout','start-twice','completion-eintr','completion-eagain','backpressure-resume']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--source',type=Path,default=REC);ap.add_argument('--report',type=Path,default=ROOT/'logs/mtp-events.json');ap.add_argument('--cases',nargs='*');a=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='dijun-mtp-events-') as d:
        d=Path(d);inc=d/'include';(inc/'android-base').mkdir(parents=True);(inc/'sys').mkdir()
        (inc/'sys/endian.h').write_text('#include <endian.h>\n')
        (inc/'android-base/properties.h').write_text('''#pragma once
#include <map>
#include <mutex>
#include <string>
namespace android::base {
inline std::mutex property_mutex;
inline std::map<std::string,std::string> properties;
inline bool GetBoolProperty(const std::string&,bool d){return d;}
template<class T> T GetIntProperty(const std::string&,T d){return d;}
inline bool SetProperty(const std::string& k,const std::string& v){std::lock_guard<std::mutex> l(property_mutex);properties[k]=v;return true;}
inline std::string GetProperty(const std::string& k,const std::string& d){std::lock_guard<std::mutex> l(property_mutex);auto i=properties.find(k);return i==properties.end()?d:i->second;}
}
''')
        (inc/'android-base/logging.h').write_text('#pragma once\n#include <cassert>\n#include <iostream>\n#define LOG(x) std::cerr\n#define PLOG(x) std::cerr\n#define CHECK(x) assert(x)\n')
        source=a.source/'mtp'
        names=['MtpFfsHandle.cpp','MtpFfsCompatHandle.cpp','MtpDescriptors.cpp','PosixAsyncIO.cpp']
        files=[source/n for n in names]+[AOSP/'system/core/libasyncio/AsyncIO.cpp',ROOT/'tests/mtp_events_test.cpp']
        cmd=['g++','-std=gnu++17','-O1','-g','-pthread','-fno-pie','-no-pie','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-include','unistd.h',*[f'-Wl,--wrap={n}' for n in ['io_submit','io_getevents','io_cancel','io_destroy','io_setup','fcntl']],*[f'-I{p}' for p in [inc,source,AOSP/'system/libbase/include',AOSP/'system/core/libasyncio/include']],*[str(p) for p in files],'-o',str(d/'test')]
        subprocess.run(cmd,check=True)
        cases=[]
        for mode in ['native','compat']:
            for case in a.cases or CASES:
                try:
                    r=subprocess.run([str(d/'test'),mode,case],capture_output=True,text=True,timeout=5,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1'))
                    code=r.returncode;out=r.stdout+r.stderr
                except subprocess.TimeoutExpired as e:code=124;out=str(e)
                cases.append(dict(case=f'{mode}/{case}',status='PASS' if code==0 else 'FAIL',returncode=code,output=out));print(cases[-1]['status'],cases[-1]['case'],flush=True)
        sources={str(p):sha(p) for p in source.glob('*') if p.suffix in ['.cpp','.h']}
        shared={str(p):sha(p) for base in [AOSP/'system/libbase/include',AOSP/'system/core/libasyncio'] for p in base.rglob('*') if p.suffix in ['.cpp','.h']}
        report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,sources=sources,shared_sources=shared,test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/mtp_events_test.cpp']},cases=cases,compile_command=cmd,sanitizer='ASan/UBSan/LSan',boundaries=['Production FunctionFS lifecycle and worker; host pipes for descriptors/interrupt endpoints, real kernel AIO for normal writes.','Only targeted event AIO errors, queued completion/cancellation and fcntl are injected; no UDC, phone or Windows enumeration.'])
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
