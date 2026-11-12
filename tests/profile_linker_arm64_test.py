#!/usr/bin/env python3
"""Execute image linker/dependency listing plus isolated relocation controls.

QEMU user mode, absolute temporary library paths and fallback namespace config.
Security services run with --list ONLY: no constructors, main, Binder or TEE.
Android --list skips relocations; a separate tiny target tests actual relocation
and constructor/main execution. These are different evidence scopes.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from verify_devicefix import entries

ANDROID = Path('/root/AAA/twrp')
CLANG = ANDROID/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang'
QEMU = ROOT/'tools/qemu-user/qemu-aarch64'
IMAGE = ROOT/'imgs/built/recovery-dijun-unified-module-state.img'
SERVICES = ['vendor/bin/tee-supplicant',
            'vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee',
            'vendor/bin/hw/android.hardware.gatekeeper-service.mitee']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=IMAGE)
    args = parser.parse_args()
    image, archive = entries(args.image)
    qemu_source = json.loads((QEMU.parent/'source.json').read_text())
    assert sha(QEMU.read_bytes()) == qemu_source['binary_sha256']
    cases, bound, controls = [], {}, []
    env = {k:v for k,v in os.environ.items() if not k.startswith(('LD_', 'QEMU_'))}

    def get(name):
        row = archive[name]
        assert stat.S_ISREG(row[1]), name
        bound[name] = sha(row[11])
        return row[11]

    def write(prefix, name, data, mode=0o644):
        target = prefix/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(mode)
        return target

    with tempfile.TemporaryDirectory(prefix='dijun-linker-arm64-') as tmp:
        base = Path(tmp)
        common = base/'common'
        linker = write(common, 'system/bin/linker64', get('system/bin/linker64'), 0o755)
        for name, row in archive.items():
            if name.startswith('system/lib64/') and name.count('/') == 2 and name.endswith('.so') and stat.S_ISREG(row[1]):
                write(common, name, get(name))

        def run(prefix, program, listing=True, libraries=None):
            search = libraries or [prefix/'system/lib64/mitee', common/'system/lib64']
            command = [str(QEMU), '-L', str(prefix), '-E',
                       'LD_LIBRARY_PATH='+':'.join(map(str, search)), str(linker)]
            return subprocess.run(command + (['--list'] if listing else []) + [str(program)],
                                  env=env, text=True, capture_output=True, timeout=20)

        profiles = sorted({n.split('/')[4] for n in archive
                           if n.startswith('system/etc/dijun/profiles/') and n.endswith('/runtime-files.list')})
        assert len(profiles) == 6
        for profile in profiles:
            prefix = base/profile
            inventory = get(f'system/etc/dijun/profiles/{profile}/runtime-files.list').decode()
            for line in inventory.splitlines():
                digest, mode, path = line.split()
                if path.startswith(('/system/lib64/mitee/', '/vendor/bin/')):
                    data = get('system/etc/dijun/blobs/'+digest)
                    assert sha(data) == digest
                    write(prefix, path.lstrip('/'), data, int(mode, 8))
            for service in SERVICES:
                result = run(prefix, prefix/service)
                assert result.returncode == 0, (profile, service, result.stderr)
                libraries = re.findall(r'^\s*(\S+) => (\S+) \(', result.stdout, re.M)
                assert libraries, (profile, result.stdout)
                loaded = {}
                for soname, path in libraries:
                    if path == '[vdso]':
                        assert soname == 'linux-vdso.so.1'
                        continue
                    actual = Path(path)
                    assert actual.is_relative_to(prefix) or actual.is_relative_to(common), path
                    loaded[soname] = {'origin': 'profile' if actual.is_relative_to(prefix) else 'recovery',
                                      'sha256': sha(actual.read_bytes())}
                    if (prefix/'system/lib64/mitee'/soname).exists():
                        assert loaded[soname]['origin'] == 'profile', (profile, soname)
                cases.append({'profile': profile, 'service': service, 'case': 'dependency-list',
                              'status': 'PASS', 'libraries': loaded,
                              'stderr': result.stderr.replace(str(base), '$STAGE')})
            unique = prefix/'system/lib64/mitee/libteecli.so'
            assert unique.is_file() and not (common/'system/lib64/libteecli.so').exists()
            unique.rename(unique.with_suffix('.hidden'))
            result = run(prefix, prefix/SERVICES[0])
            assert result.returncode != 0 and 'libteecli.so' in result.stderr and 'not found' in result.stderr
            cases.append({'profile': profile, 'service': SERVICES[0], 'case': 'missing-tee-library',
                          'status': 'PASS', 'returncode': result.returncode,
                          'stderr': result.stderr.replace(str(base), '$STAGE')})

        # A real undefined-symbol negative control demonstrates --list's limit.
        libc_dir = ANDROID/'out/soong/.intermediates/bionic/libc'
        begin = libc_dir/'crtbegin_dynamic/android_recovery_arm64_armv8-a/crtbegin_dynamic.o'
        end = libc_dir/'crtend_android/android_recovery_arm64_armv8-a/crtend_android.o'
        flags = [str(CLANG), '--target=aarch64-linux-android35', '-fuse-ld=lld', '-nostdlib', '-fPIE']
        for label, source in [
            ('valid', 'extern long write(int,const void*,unsigned long); static int ready; '
             '__attribute__((constructor)) static void init(void){ready=41;} '
             'int main(void){if(ready!=41)return 7;return write(1,"ARM64_DYNAMIC_MAIN_OK\\n",22)==22?0:8;}'),
            ('undefined', 'extern int dijun_fixture_missing_symbol(void); '
             'int main(void){return dijun_fixture_missing_symbol();}')]:
            code = base/(label+'.c'); code.write_text(source)
            target = base/label
            subprocess.run(flags + ['-pie', '-Wl,--unresolved-symbols=ignore-all',
                '-Wl,--dynamic-linker=/system/bin/linker64', str(begin), str(code),
                '-Wl,--no-as-needed', str(common/'system/lib64/libc.so'), str(end),
                '-o', str(target)], check=True, capture_output=True)
            for listing in (True, False):
                result = run(common, target, listing=listing, libraries=[common/'system/lib64'])
                if label == 'undefined' and not listing:
                    assert result.returncode != 0 and 'cannot locate symbol "dijun_fixture_missing_symbol"' in result.stderr, result.stderr
                else:
                    assert result.returncode == 0, (label, listing, result.stderr)
                    if not listing:
                        assert result.stdout == 'ARM64_DYNAMIC_MAIN_OK\n', repr(result.stdout)
                controls.append({'case': label, 'listing': listing, 'returncode': result.returncode,
                                 'stdout': result.stdout, 'stderr': result.stderr.replace(str(base), '$STAGE'),
                                 'source': source, 'binary_sha256': sha(target.read_bytes())})
        build_inputs = {str(p):sha(p.read_bytes()) for p in [CLANG.resolve(), CLANG.parent/'ld.lld', begin, end]}
    files = [Path(__file__).resolve(), QEMU, QEMU.parent/'source.json',
             ANDROID/'bionic/linker/linker_relocate.cpp', ANDROID/'bionic/linker/linker_main.cpp']
    report = {'status': 'PASS', 'scope': __doc__.strip(), 'image': str(args.image), 'image_sha256': sha(image),
              'image_entries': bound, 'count': len(cases)+len(controls), 'cases': cases,
              'relocation_controls': controls, 'build_inputs': build_inputs,
              'sources': {str(p):sha(p.read_bytes()) for p in files}}
    (ROOT/'logs/profile-linker-arm64.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS:',len(cases),'dependency-list cases and',len(controls),'actual linker controls')


if __name__ == '__main__':
    main()
