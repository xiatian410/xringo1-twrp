#!/usr/bin/env python3
"""Run the production libtar C sources with ASan/UBSan in disposable directories.

Uses real host files, modes, ownership, hard/symbolic links and Android xattrs.
Only writes/closes for controlled restore files are fault-injected. The fscrypt
kernel/vold provider normally reports no policy; one synthetic v2 policy checks
ordering (set policy before creating cache children), with no real encryption.
This does not execute twrpTar's compression, split/fork, raw-image or GUI paths.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = Path('/root/AAA/twrp')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ANDROID/'bootable/recovery/libtar')
parser.add_argument('--report', type=Path, default=ROOT/'logs/archive-restore.json')
args = parser.parse_args()
names = re.findall(r'"([\w]+\.c)"', (args.source/'Android.bp').read_text())
assert len(names) == 15
cases = ['roundtrip-metadata', 'symlink', 'hardlink-short', 'hardlink-long',
         'hardlink-null-prefix', 'hardlink-missing', 'short-write', 'interrupted-write',
         'zero-write', 'full-disk', 'close-error', 'truncated-header', 'truncated-data',
         'missing-eot', 'single-eot', 'bad-checksum', 'empty-archive', 'android-xattrs',
         'existing-dir-xattrs', 'sparse-content', 'eot-corrupt', 'ignore-eot',
         'android-xattr-write-error', 'encrypted-dir-order', 'metadata-length',
         'metadata-short-cap', 'metadata-short-policy', 'metadata-no-newline',
         'metadata-unknown-tag', 'gnu-name-block-boundary']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='dijun-archive-', dir='/tmp') as tmp:
    tmp = Path(tmp)
    compat = tmp/'host.h'
    compat.write_text('#include <stdint.h>\n#include <stdio.h>\n#include <sys/types.h>\n#include <linux/fscrypt.h>\n#define __unused __attribute__((unused))\n')
    cmd = ['gcc', '-std=gnu11', '-g', '-O1', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
           '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
           '-D_GNU_SOURCE', '-D_FILE_OFFSET_BITS=64', '-DUSE_FSCRYPT',
           '-include', str(compat), '-I'+str(args.source),
           '-I'+str(ANDROID/'external/libcap/libcap/include'),
           '-I'+str(ANDROID/'external/selinux/libselinux/include'),
           '-I'+str(ANDROID/'system/vold'), '-I'+str(ANDROID/'system/core/libcutils/include'),
           *[str(args.source/n) for n in names], str(args.source/'strlcpy.c'),
           str(ROOT/'tests/archive_restore_test.c'),
           '-Wl,--wrap=write', '-Wl,--wrap=close', '-Wl,--wrap=setxattr', '-l:libselinux.so.1', '-o', str(tmp/'test')]
    subprocess.run(cmd,check=True)
    results=[]
    for case in cases:
        directory=tmp/case; directory.mkdir(); (directory/'.fixture').touch()
        # Legacy append leaks extension buffers; unrelated ownership cleanup is
        # recorded separately, not silently treated as a leak-sanitizer pass.
        env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1')
        run=subprocess.run([str(tmp/'test'),case],cwd=directory,env=env,capture_output=True,text=True,timeout=10)
        results.append(dict(case=case,status='PASS' if run.returncode==0 else 'FAIL',returncode=run.returncode,output=run.stdout+run.stderr))
        print(results[-1]['status'],case,flush=True)
    sources={str(p):sha(p) for p in sorted(args.source.iterdir()) if p.suffix in ('.c','.h','.go','.bp')}
    for p in [ANDROID/'system/vold/fscrypt_policy.h',ANDROID/'system/core/libcutils/include/cutils/multiuser.h',ANDROID/'external/libcap/libcap/include/sys/capability.h',ANDROID/'external/selinux/libselinux/include/selinux/selinux.h']:
        sources[str(p)]=sha(p)
    report=dict(status='PASS' if all(x['returncode']==0 for x in results) else 'FAIL',scope=__doc__.strip(),
                compile_command=cmd,compiler=subprocess.check_output(['gcc','--version'],text=True).splitlines()[0],
                sanitizer='ASan + UBSan; leak detection disabled',cases=results,sources=sources,
                tests={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/archive_restore_test.c']})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
