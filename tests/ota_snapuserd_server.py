#!/usr/bin/env python3
"""Execute original ARM64 snapuserd Start/Run over private AF_UNIX sockets.

Only daemon main is replaced. No Initialize, block factory, snapshot handlers,
mapper, mount, device nodes, property service or phone. Static production server
and its libraries execute under pinned QEMU in a private chroot.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import tempfile

from ota_vabc_session import ROOT, ANDROID, build

SERVER = 'system/core/fs_mgr/libsnapshot/snapuserd/user-space-merge/snapuserd_server.cpp'
TARGET = 'out/soong/.intermediates/system/core/fs_mgr/libsnapshot/snapuserd/snapuserd/android_recovery_arm64_armv8-a/unstripped/snapuserd'
CASES = ['normal-query', 'empty-half-close', 'query-then-half-close',
         'buffered-query-half-close', 'close-client', 'unknown-command', 'malformed-delete', 'supports']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server-source', type=Path, help='Original TU override for negative comparison')
    parser.add_argument('--report', type=Path, default=ROOT/'logs/ota-snapuserd-server.json')
    args = parser.parse_args()
    qemu = ROOT/'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    lines = subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja', '-f',
        'out/combined-twrp_dijun.ninja', '-t', 'commands', TARGET], cwd=ANDROID, text=True).splitlines()
    row = next(row for row in lines if row.endswith(' '+SERVER))
    template = shlex.split(row)
    if template[0].startswith('PWD='): template.pop(0)
    link_template = shlex.split(next(row for row in lines if 'clang++ ' in row and ' -o '+TARGET+' ' in row))
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_snapuserd_server.cpp',
               ROOT/'tests/ota_vabc_session.py', ANDROID/SERVER]}
    deps = {str(qemu): sha(qemu), str(qemu.with_name('source.json')): sha(qemu.with_name('source.json'))}
    with tempfile.TemporaryDirectory(prefix='snapuserd-server-') as temp:
        work = Path(temp)
        commands = []
        for tag, source in [('fixture', ROOT/'tests/ota_snapuserd_server.cpp'),
                            ('server', args.server_source.resolve() if args.server_source else ANDROID/SERVER)]:
            sources[str(source)] = sha(source)
            command = [a for a in template if a != '-DNDEBUG']
            command[1:1] = ['-UNDEBUG', '-I'+str((ANDROID/SERVER).parent)]
            command[command.index('-o')+1] = str(work/(tag+'.o'))
            command[command.index('-MF')+1] = str(work/(tag+'.d'))
            command[-1] = str(source)
            build(command); commands.append(command)
            for name in shlex.split((work/(tag+'.d')).read_text().replace('\\\n', ' ').split(':', 1)[1]):
                path = ANDROID/name
                if path.is_file(): sources[str(path)] = sha(path)
        link = []
        for arg in link_template:
            link.extend(shlex.split((ANDROID/arg[1:]).read_text()) if arg.startswith('@') else [arg])
        main_obj = next(a for a in link if a.endswith('/snapuserd_daemon.o'))
        server_obj = next(a for a in link if a.endswith('/snapuserd_server.o'))
        link[link.index(main_obj)] = str(work/'fixture.o')
        link[link.index(server_obj)] = str(work/'server.o')
        link[link.index('-o')+1] = str(work/'test')
        for arg in link:
            if arg.endswith(('.a', '.o')) and (ANDROID/arg).is_file() and not str(work) in arg:
                deps[str(ANDROID/arg)] = sha(ANDROID/arg)
        deps[str(ANDROID/link[0])] = sha(ANDROID/link[0])
        build(link)
        elf = (work/'test').read_bytes()
        assert elf[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', elf, 18)[0] == 183
        jail = work/'jail'
        (jail/'dev/socket').mkdir(parents=True); (jail/'dev/null').touch()
        shutil.copyfile(qemu, jail/'qemu'); (jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'test', jail/'test'); (jail/'test').chmod(0o755)
        def isolate():
            os.chroot(jail); os.chdir('/')
        cases = []
        for name in CASES:
            (jail/'dev/socket/offline-snapuserd').unlink(missing_ok=True)
            result = subprocess.run(['/qemu', '/test', name], preexec_fn=isolate,
                                    capture_output=True, text=True, timeout=15)
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                              returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
            scope=__doc__, sources=sources, dependencies=deps, fixture_elf_machine=183,
            fixture_sha256=hashlib.sha256(elf).hexdigest(), compile_commands=commands,
            link_command=link, server_override=str(args.server_source) if args.server_source else None,
            real_server=True, real_unix_stream=True, kernel_mapping=False, snapshot_handlers=False,
            original_daemon_main=False, cases=cases)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'], len(cases), 'cases;', sum(c['status']=='FAIL' for c in cases), 'failures')
        return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
