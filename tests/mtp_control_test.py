#!/usr/bin/env python3
"""Production FunctionFS SETUP/status and event framing; emulated ep0 I/O, no UDC."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REC = Path('/root/AAA/twrp/bootable/recovery')
AOSP = REC.parents[1]
CASES = [f'status-{n}' for n in [0, 1, 2, 3, 4, 7, 8, 65535]] + [
    f'canceled-{n}' for n in [0, 2, 4, 6, 8, 64]] + ['header-then-full'] + [
    'write-eintr', 'write-short', 'write-error', 'write-again', 'write-superseded',
    'descriptor-eintr', 'descriptor-error', 'descriptor-zero', 'descriptor-direction',
    'descriptor-reserved', 'descriptor-type', 'descriptor-class',
    'reject-status-out', 'reject-recipient', 'reject-vendor', 'reject-interface',
    'reject-interface-high', 'reject-value', 'reject-extended', 'reject-unknown-in',
    'reject-unknown-out', 'reject-cancel-in', 'reject-cancel-size', 'reject-reset-in',
    'reject-reset-size', 'stall-failure', 'stall-superseded',
    'cancel-valid', 'cancel-short', 'cancel-code', 'cancel-error', 'cancel-eintr',
    'cancel-superseded', 'reset-valid', 'reset-error', 'reset-eintr',
    'events-eof', 'events-error', 'events-again', 'events-superseded', 'events-short',
    'events-lifecycle', 'events-eintr', 'events-disable-enable', 'events-unbind-enable',
    'events-unknown-enable', 'events-status-enable', 'events-cancel-enable',
    'events-cancel-disable', 'events-disable-status', 'events-stall-enable']
CASES += ['transaction-idle', 'transaction-mismatch', 'transaction-finished',
          'transaction-next-command', 'transaction-zero', 'transaction-max',
          'transaction-max-mismatch']
CASES += ['reset-session-signal', 'reset-status-busy', 'reset-clears-cancel',
          'reset-failed-no-signal', 'reset-superseded-no-signal', 'cancel-no-reset']
CASES += ['events-reset-disable']

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=REC)
    ap.add_argument('--report', type=Path, default=ROOT/'logs/mtp-control.json')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='dijun-mtp-control-') as tmp:
        tmp = Path(tmp)
        inc = tmp/'include'
        (inc/'android-base').mkdir(parents=True)
        (inc/'sys').mkdir()
        (inc/'sys/endian.h').write_text('#include <endian.h>\n')
        (inc/'android-base/properties.h').write_text('''#pragma once
#include <string>
namespace android::base {
inline bool GetBoolProperty(const std::string&,bool d){return d;}
template<class T> T GetIntProperty(const std::string&,T d){return d;}
inline bool SetProperty(const std::string&,const std::string&){return true;}
}
''')
        (inc/'android-base/logging.h').write_text('#pragma once\n#include <cassert>\n#include <iostream>\n#define LOG(x) std::cerr\n#define PLOG(x) std::cerr\n#define CHECK(x) assert(x)\n')
        source = a.source/'mtp'
        tracking = 'virtual void beginTransaction' in (source/'IMtpHandle.h').read_text()
        files = [source/n for n in ['MtpFfsHandle.cpp','MtpFfsCompatHandle.cpp','MtpDescriptors.cpp','PosixAsyncIO.cpp']]
        files += [AOSP/'system/core/libasyncio/AsyncIO.cpp', ROOT/'tests/mtp_control_test.cpp']
        cmd = ['g++','-std=gnu++17','-O1','-g','-pthread','-fno-pie','-no-pie',
               '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
               '-include','unistd.h', *[f'-Wl,--wrap={n}' for n in ['read','write','ioctl']],
               *[f'-I{p}' for p in [inc,source,AOSP/'system/libbase/include',AOSP/'system/core/libasyncio/include']],
               *map(str,files),'-o',str(tmp/'test')]
        if tracking:
            cmd.insert(1, '-DMTP_TRANSACTION_TRACKING')
        if 'virtual bool consumeReset' in (source/'IMtpHandle.h').read_text():
            cmd.insert(1, '-DMTP_RESET_SIGNAL')
        subprocess.run(cmd, check=True)
        cases = []
        for case in CASES:
            try:
                r = subprocess.run([str(tmp/'test'),case],capture_output=True,text=True,errors='replace',timeout=5,
                                   env=dict(os.environ,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1'))
                code,out = r.returncode,r.stdout+r.stderr
            except subprocess.TimeoutExpired as e:
                code,out = 124,str(e)
            cases.append(dict(case=case,status='PASS' if code==0 else 'FAIL',returncode=code,output=out))
            print(cases[-1]['status'],case,flush=True)
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,
            sources={str(p):sha(p) for p in source.glob('*') if p.suffix in ['.cpp','.h']},
            shared_sources={str(p):sha(p) for base in [AOSP/'system/libbase/include',AOSP/'system/core/libasyncio'] for p in base.rglob('*') if p.suffix in ['.cpp','.h']},
            test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/mtp_control_test.cpp']},
            cases=cases,compile_command=cmd,sanitizer='ASan/UBSan/LSan',
            boundaries=['Actual handleControlRequest/handleEvent; FunctionFS SETUP/data/stall semantics emulated at read/write/ioctl.',
                        'Cancel transaction matching and Reset signal/status cover the control boundary; actual server cleanup is tested separately. Bulk AIO cancellation/drain and compat ep0 dispatch remain pending.',
                        'No phone, real UDC, Windows enumeration or proof of physical endpoint halt/clear timing.'])
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'

if __name__=='__main__':
    raise SystemExit(main())
