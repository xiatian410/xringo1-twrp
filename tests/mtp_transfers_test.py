#!/usr/bin/env python3
"""Run production MTP server/database/packet/storage code with a memory USB peer.

Real private host files, inotify and threads; no phone or physical USB/configfs.
"""
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery')
AOSP=REC.parents[1]
CASES=['copy-file', 'copy-directory', 'copy-within', 'copy-collision', 'copy-directory-collision', 'copy-subtree-cycle', 'copy-invalid-parent', 'copy-parent-other-storage', 'copy-invalid-storage', 'copy-invalid-object', 'copy-root', 'copy-short-sendfile', 'copy-eintr', 'copy-zero-sendfile', 'copy-enospc', 'copy-fsync-fail', 'copy-symlink', 'copy-fifo', 'copy-max-size', 'copy-directory-max-size', 'move-file', 'move-directory', 'move-cross-storage', 'move-cross-filesystem', 'move-directory-cross-filesystem', 'move-same-parent', 'move-collision', 'move-subtree-cycle', 'move-unlink-fail', 'move-directory-unlink-fail', 'move-rename-fail', 'move-cross-max-size', 'move-watch-after', 'rescan-metadata', 'rescan-missing', 'rescan-wrong-path', 'overflow-add-delete', 'overflow-cached-subtree', 'root-removed', 'parent-symlink-replacement', 'move-max-size', 'move-directory-max-size', 'copy-directory-enospc', 'copy-directory-symlink', 'copy-directory-empty', 'move-uid-stable', 'copy-parent-fsync-fail', 'copy-close-fail']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=REC)
    ap.add_argument('--report',type=Path,default=ROOT/'logs/mtp-transfers.json')
    ap.add_argument('--cases',nargs='*')
    a=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix='dijun-mtp-transfers-') as tmp:
        tmp=Path(tmp);stage=tmp/'mtp';shutil.copytree(a.source/'mtp',stage)
        inc=tmp/'include'
        for folder in ['android-base','log','sys']:(inc/folder).mkdir(parents=True,exist_ok=True)
        (inc/'sys/endian.h').write_text('#include <endian.h>\n')
        (inc/'log/log.h').write_text('''#pragma once
#include <cstdio>
#define ALOGV(...) ((void)0)
#define ALOGD(...) ((void)0)
#define ALOGI(...) ((void)0)
#define ALOGW(...) ((void)0)
#define ALOGE(...) ((void)0)
inline int android_errorWriteWithInfoLog(int,const char*,int,const char*,size_t){return 0;}
''')
        (inc/'android-base/logging.h').write_text('''#pragma once
#include <cassert>
#include <iostream>
#define LOG(x) std::cerr
#define PLOG(x) std::cerr
#define CHECK(x) assert(x)
''')
        (inc/'android-base/properties.h').write_text('''#pragma once
#include <string>
namespace android::base {
inline bool GetBoolProperty(const std::string&,bool d){return d;}
inline std::string GetProperty(const std::string&,const std::string& d){return d;}
}
''')
        (inc/'android-base/strings.h').write_text('''#pragma once
#include <string>
namespace android::base {
template<class T> inline std::string Trim(const T& v){std::string s(v);auto a=s.find_first_not_of(" \\t\\r\\n");if(a==s.npos)return {};return s.substr(a,s.find_last_not_of(" \\t\\r\\n")-a+1);}
}
''')
        # Replace only USB constructors/transport; server requests and filesystem
        # helpers execute unchanged. The host cannot access physical USB nodes.
        for cls in ['MtpDevHandle','MtpFfsHandle','MtpFfsCompatHandle']:
            base='MtpFfsHandle' if cls=='MtpFfsCompatHandle' else 'FixtureHandle'
            header='MtpFfsHandle.h' if cls=='MtpFfsCompatHandle' else 'mtp_objects_peer.hpp'
            (stage/(cls+'.h')).write_text(f'#pragma once\n#include "{header}"\nnamespace android {{ class {cls} : public {base} {{ public: using {base}::{base}; }}; }}\n')
        names=['MtpServer.cpp','MtpPacket.cpp','MtpDataPacket.cpp','MtpRequestPacket.cpp',
               'MtpResponsePacket.cpp','MtpEventPacket.cpp','MtpStringBuffer.cpp',
               'MtpObjectInfo.cpp','MtpProperty.cpp','MtpStorage.cpp','MtpUtils.cpp','MtpDebug.cpp',
               'twrp/TwrpMtpDatabase.cpp','twrp/TwrpMtpStorage.cpp']
        sources={str(p):sha(p) for p in (a.source/'mtp').rglob('*') if p.suffix in ['.cpp','.h','.hpp','.bp']}
        includes=[inc,stage,ROOT/'tests',AOSP/'system/libbase/include',
                  AOSP/'system/core/libusbhost/include',AOSP/'system/core/libcutils/include']
        cmd=['g++','-std=c++23','-O1','-g','-pthread','-DMTP_DEVICE','-fno-pie','-no-pie',
             '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
             '-include','unistd.h','-include','ctime','-include','cstring','-include','climits','-include','cstdint','-include','chrono','-include','cstdarg','-Wl,--wrap=unlink','-Wl,--wrap=unlinkat','-Wl,--wrap=write','-Wl,--wrap=fsync','-Wl,--wrap=mkdir','-Wl,--wrap=sendfile','-Wl,--wrap=syscall','-Wl,--wrap=inotify_init','-Wl,--wrap=read','-Wl,--wrap=close',*[f'-I{p}' for p in includes],
             *[str(stage/n) for n in names],str(ROOT/'tests/mtp_transfers_test.cpp'),'-o',str(tmp/'test')]
        subprocess.run(cmd,check=True)
        results=[]
        for case in a.cases or CASES:
            wd=tmp/case;wd.mkdir();(wd/'.fixture').touch()
            try:
                result=subprocess.run([str(tmp/'test'),case],cwd=wd,capture_output=True,text=True,
                                      timeout=8,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'))
                code=result.returncode;out=result.stdout+result.stderr
            except subprocess.TimeoutExpired as e:code=124;out=str(e)
            results.append(dict(case=case,status='PASS' if code==0 else 'FAIL',returncode=code,output=out))
            print(results[-1]['status'],case,flush=True)
        shared={str(p):sha(p) for base in [AOSP/'system/libbase/include', AOSP/'system/core/libusbhost/include', AOSP/'system/core/libcutils/include'] for p in base.rglob('*.h')}
        reference=AOSP/'frameworks/base/media/java/android/mtp/MtpStorageManager.java'
        shared[str(reference)]=sha(reference)
        reference=reference.with_name('MtpDatabase.java');shared[str(reference)]=sha(reference)
        report=dict(status='PASS' if all(x['status']=='PASS' for x in results) else 'FAIL',
                    scope=__doc__.strip(),sources=sources,shared_sources=shared,sanitizer='ASan/UBSan; LSan cannot inspect /proc in private chroot and is disabled',
                    test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/mtp_transfers_test.cpp',ROOT/'tests/mtp_objects_peer.hpp']},
                    cases=results,compile_command=cmd,
                    boundaries=['Private chroot with actual files/inotify/threads; USB transport and properties/logging are substitutes.',
                                'Packet server and database are production code. No Android init/configfs, ARM64 or Windows enumeration.'])
        a.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
