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
    parser.add_argument('--ordered', action='store_true', help='COPY/XOR/read-ahead cases through the handler fixture')
    parser.add_argument('--handler', action='store_true', help='Actual client/server COW handler lifecycle with dm-user socket endpoint')
    parser.add_argument('--server-source', type=Path, help='Original TU override for negative comparison')
    parser.add_argument('--report', type=Path, default=ROOT/'logs/ota-snapuserd-server.json')
    args = parser.parse_args()
    if args.ordered: args.handler = True
    fixture = ROOT/("tests/ota_snapuserd_handler.cpp" if args.handler else "tests/ota_snapuserd_server.cpp")
    if args.handler and args.server_source: parser.error("handler mode does not use old-source overrides")
    if args.handler and args.report == ROOT/"logs/ota-snapuserd-server.json":
        args.report = ROOT/("logs/ota-snapuserd-ordered.json" if args.ordered else "logs/ota-snapuserd-handler.json")
    qemu = ROOT/'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    lines = subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja', '-f',
        'out/combined-twrp_dijun.ninja', '-t', 'commands', TARGET], cwd=ANDROID, text=True).splitlines()
    row = next(row for row in lines if row.endswith(' '+SERVER))
    template = shlex.split(row)
    if template[0].startswith('PWD='): template.pop(0)
    link_template = shlex.split(next(row for row in lines if 'clang++ ' in row and ' -o '+TARGET+' ' in row))
    sources = {str(p): sha(p) for p in [Path(__file__), fixture,
               ROOT/'tests/ota_vabc_session.py', ANDROID/SERVER]}
    if args.handler:
        base = ANDROID/'system/core/fs_mgr/libsnapshot'
        for path in [base/'snapuserd/snapuserd_client.cpp',
                     base/'snapuserd/dm_user_block_server.cpp',
                     *[base/'snapuserd/user-space-merge'/name for name in
                       ['handler_manager.cpp', 'snapuserd_core.cpp', 'worker.cpp', 'read_worker.cpp',
                        'merge_worker.cpp', 'snapuserd_transitions.cpp', 'snapuserd_readahead.cpp']],
                     base/'Android.bp', base/'snapuserd/Android.bp']:
            sources[str(path)] = sha(path)
    deps = {str(qemu): sha(qemu), str(qemu.with_name('source.json')): sha(qemu.with_name('source.json'))}
    with tempfile.TemporaryDirectory(prefix='snapuserd-server-') as temp:
        work = Path(temp)
        commands = []
        for tag, source in [('fixture', fixture),
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
        if args.handler:
            link.extend(['-Wl,--wrap=open', '-Wl,--wrap=__open_2', '-Wl,--wrap=get_block_device_size', '-Wl,--wrap=pwrite', '-Wl,--wrap=fsync'])
        build(link)
        elf = (work/'test').read_bytes()
        assert elf[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', elf, 18)[0] == 183
        jail = work/'jail'
        (jail/'dev/socket').mkdir(parents=True); (jail/'dev/null').touch()
        (jail/'work').mkdir()
        shutil.copyfile(qemu, jail/'qemu'); (jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'test', jail/'test'); (jail/'test').chmod(0o755)
        def isolate():
            os.chroot(jail); os.chdir('/')
        cases = []
        names = ['init-delete', 'active-read-delete', 'corrupt-cow', 'missing-control', 'reinitialize', 'merge-readback', 'merge-write-error', 'merge-sync-error'] if args.handler else CASES
        if args.ordered: names = ['ordered-copy', 'ordered-xor', 'ordered-mixed', 'ordered-scratch', 'ordered-write-error', 'ordered-sync-error']
        for name in names:
            shutil.rmtree(jail/'work'); (jail/'work').mkdir()
            (jail/'dev/socket/offline-snapuserd').unlink(missing_ok=True)
            result = subprocess.run(['/qemu', '/test', name], preexec_fn=isolate,
                                    capture_output=True, text=True, timeout=15)
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                              returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',
            scope=("Actual ARM64 client/server/handler ReadWorker + ReadAhead + ordered COPY/XOR MergeWorker, cyclic sources and XOR offset21; replace/zero mixed and scratch-space case. Real COW, ordinary-file base, socketpair dm-user endpoint/size doubles. Independent whole-file content, persisted COW progress and ordered write/fsync errors. No kernel mappings, process-death resume, io_uring or full OTA." if args.ordered else "Actual ARM64 SnapuserdClient Connect/query/init/start/delete and original server/handler/COW/ReadWorker. Base size and dm-user open are explicit ordinary-file/socket doubles. Real AF_UNIX, COW writer/reader, decompression, worker exit/delete/reinitialize, replace/zero merge and whole-base readback; injected base pwrite/fsync errors. No kernel mapping, physical device, init properties, COPY/XOR/RA or persistent merge resume." if args.handler else __doc__), sources=sources, dependencies=deps, fixture_elf_machine=183,
            fixture_sha256=hashlib.sha256(elf).hexdigest(), compile_commands=commands,
            link_command=link, server_override=str(args.server_source) if args.server_source else None,
            real_server=True, real_unix_stream=True, kernel_mapping=False, snapshot_handlers=args.handler, actual_merge_worker=args.handler,
            original_daemon_main=False, ordered_copy_xor=args.ordered, actual_readahead=args.ordered, actual_client=args.handler, handler_lifecycle=args.handler, cases=cases)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'], len(cases), 'cases;', sum(c['status']=='FAIL' for c in cases), 'failures')
        return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
