#!/usr/bin/env python3
"""Build an independent static ARM64 Android diagnostic from current bionic."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANDROID = Path('/root/AAA/twrp')
CLANG = ANDROID / 'prebuilts/clang/host/linux-x86/clang-r547379'
HERE = Path(__file__).resolve().parent


def main():
    compiler = CLANG / 'bin/clang'
    libc = ANDROID / 'out/soong/.intermediates/bionic/libc'
    begin = libc / 'crtbegin_static/android_recovery_arm64_armv8-a/crtbegin_static.o'
    end = libc / 'crtend_android/android_recovery_arm64_armv8-a/crtend_android.o'
    library = libc / 'libc/android_recovery_arm64_armv8-a_static/libc.a'
    builtins = CLANG / 'lib/clang/20/lib/linux/libclang_rt.builtins-aarch64-android.a'
    output = HERE / 'haptics-diagnostic-arm64'
    with tempfile.TemporaryDirectory(prefix='dijun-haptics-diagnostic-') as temp:
        obj = Path(temp) / 'diagnostic.o'
        command = [str(compiler), '--target=aarch64-linux-android35', '-std=c11',
                   '-Wall', '-Wextra', '-Werror', '-fPIE', '-nostdinc']
        for include in [ANDROID / 'bionic/libc/include', CLANG / 'lib/clang/20/include',
                        ANDROID / 'bionic/libc/kernel/uapi',
                        ANDROID / 'bionic/libc/kernel/uapi/asm-arm64',
                        ANDROID / 'bionic/libc/kernel/android/uapi']:
            command += ['-isystem', str(include)]
        subprocess.run(command + ['-c', str(HERE / 'haptics-diagnostic.c'), '-o', str(obj)], check=True)
        subprocess.run([str(compiler), '--target=aarch64-linux-android35', '-fuse-ld=lld',
                        '-nostdlib', '-static', '-Wl,--gc-sections', '-Wl,--build-id=sha1',
                        str(begin), str(obj), '-Wl,--start-group', str(library), str(builtins),
                        '-Wl,--end-group', str(end), '-o', str(output)], check=True)
    inputs = [Path(__file__).resolve(), HERE / 'haptics-diagnostic.c', compiler.resolve(),
              CLANG / 'bin/ld.lld', begin, end, library, builtins]
    record = dict(binary=str(output.relative_to(ROOT)),
                  sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  scope='Independent static Android ARM64 diagnostic; not executed on a device, not part of recovery image. Existing bionic artifacts are build inputs, not a fresh Android rebuild.',
                  inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs})
    output.with_suffix('.json').write_text(json.dumps(record, indent=2) + '\n')
    print('Built', output, record['sha256'])


if __name__ == '__main__':
    main()
