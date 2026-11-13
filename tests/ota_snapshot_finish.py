#!/usr/bin/env python3
"""Run original ARM64 SnapshotManager completion on private metadata files.

Actual protobuf, directory locks, indicator updates and atomic helper execute.
Device mapping, partition access, image management and slot effects are denied;
boot merge status is a recorded result boundary. fsync can fail for one file.
No snapshot data writing, real metadata mount, merge, reboot or full OTA.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import struct
import subprocess
import sys
import tempfile

from ota_vabc_session import ROOT, ANDROID, build
sys.path.insert(0, str(ROOT/'scripts'))
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--cancel', action='store_true', help='Execute original cancellation failure propagation')
    parser.add_argument('--snapshot-source', type=Path, help='Compile explicit snapshot TU for negative comparison')
    parser.add_argument('--postinstall', action='store_true', help='Join original controller/PostinstallRunnerAction with persisted-state retries')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--utility-source', type=Path, help='Compile an explicit helper source for old-source comparison only')
    args = parser.parse_args()
    if args.cancel and args.postinstall: parser.error('choose one mode')
    if args.snapshot_source and not args.cancel: parser.error('snapshot override is only supported for cancellation')
    if args.report is None:
        args.report = ROOT/('logs/ota-snapshot-cancel.json' if args.cancel else 'logs/ota-snapshot-postinstall.json' if args.postinstall else 'logs/ota-snapshot-finish.json')
    if args.postinstall and args.utility_source:
        parser.error('old-helper comparison is only supported for leaf cases')
    fixture = ROOT/('tests/ota_snapshot_cancel.cpp' if args.cancel else 'tests/ota_snapshot_postinstall.cpp' if args.postinstall else 'tests/ota_snapshot_finish.cpp')
    if args.image is not None:
        args.image = args.image.resolve()
    reference = json.loads((ROOT/'logs/ota-vabc-session.json').read_text())
    current = json.loads((ROOT/'simulation-report.json').read_text())
    image = args.image or Path(current['image'])
    if args.image is None:
        assert sha(image) == current['image_sha256']
    # Reuse resolved flags and paths, binding the CURRENT rebuilt link inputs.
    # Replace the stale fixture object explicitly; original static archives execute.
    dependencies = {name: sha(name) for name in reference['dependencies']}
    assert dependencies[str(ROOT/'tools/qemu-user/qemu-aarch64')] == reference['dependencies'][str(ROOT/'tools/qemu-user/qemu-aarch64')]
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_snapshot_finish.cpp',
        ROOT/'tests/ota_vabc_session.py', ANDROID/'system/core/fs_mgr/libsnapshot/snapshot.cpp',
        ANDROID/'system/core/fs_mgr/libsnapshot/utility.cpp', ROOT/'scripts/firmware_facts.py',
        ROOT/'scripts/acquire_firmware.py']}
    sources[str(fixture)] = sha(fixture)
    if args.postinstall or args.cancel:
        for path in [ANDROID/'system/update_engine/aosp/dynamic_partition_control_android.cc',
                     ANDROID/'system/update_engine/payload_consumer/postinstall_runner_action.cc']:
            sources[str(path)] = sha(path)
    with tempfile.TemporaryDirectory(prefix='ota-snapshot-finish-') as temp:
        work = Path(temp)
        obj = 'out/soong/.intermediates/system/update_engine/libupdate_engine_boot_control/android_recovery_arm64_armv8-a_static/obj/system/update_engine/aosp/dynamic_partition_control_android.o'
        ninja = subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja', '-f', 'out/combined-twrp_dijun.ninja', '-t', 'commands', obj], cwd=ANDROID, text=True)
        line = next(line for line in ninja.splitlines() if line.endswith(' system/update_engine/aosp/dynamic_partition_control_android.cc'))
        compile_args = shlex.split(line)[1:] if line.startswith('PWD=') else shlex.split(line)
        assert compile_args[-1] == 'system/update_engine/aosp/dynamic_partition_control_android.cc'
        command = [a for a in compile_args if a != '-DNDEBUG']
        command.insert(-1, '-UNDEBUG')
        command[command.index('-o')+1] = str(work/'fixture.o')
        command[command.index('-MF')+1] = str(work/'fixture.d')
        command[-1] = str(fixture)
        build(command)
        depfile = (work/'fixture.d').read_text().replace('\\\n', ' ')
        for name in shlex.split(depfile.split(':', 1)[1]):
            p = ANDROID/name
            if p.is_file(): sources[str(p)] = sha(p)
        link = reference['link_command'].copy()
        old_obj = next(a for a in link if a.endswith('/fixture.o'))
        link[link.index(old_obj):link.index(old_obj)+1] = [str(work/'fixture.o')]
        if args.utility_source is not None:
            utility = args.utility_source.resolve()
            sources[str(utility)] = sha(utility)
            helper_object = 'out/soong/.intermediates/system/core/fs_mgr/libsnapshot/libsnapshot_nobinder/android_recovery_arm64_armv8-a_static/obj/system/core/fs_mgr/libsnapshot/utility.o'
            helper_commands = subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja', '-f', 'out/combined-twrp_dijun.ninja', '-t', 'commands', helper_object], cwd=ANDROID, text=True)
            helper_line = next(line for line in helper_commands.splitlines() if line.endswith(' system/core/fs_mgr/libsnapshot/utility.cpp'))
            helper = shlex.split(helper_line)[1:] if helper_line.startswith('PWD=') else shlex.split(helper_line)
            helper[helper.index('-o')+1] = str(work/'utility.o')
            helper[helper.index('-MF')+1] = str(work/'utility.d')
            helper.insert(-1, '-I'+str(ANDROID/'system/core/fs_mgr/libsnapshot'))
            helper[-1] = str(utility)
            build(helper)
            for name in shlex.split((work/'utility.d').read_text().replace('\\\n', ' ').split(':', 1)[1]):
                path = ANDROID/name
                if path.is_file(): sources[str(path)] = sha(path)
            link.insert(link.index(str(work/'fixture.o'))+1, str(work/'utility.o'))
        if args.snapshot_source is not None:
            override = args.snapshot_source.resolve()
            sources[str(override)] = sha(override)
            object_name = 'out/soong/.intermediates/system/core/fs_mgr/libsnapshot/libsnapshot_nobinder/android_recovery_arm64_armv8-a_static/obj/system/core/fs_mgr/libsnapshot/snapshot.o'
            commands = subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja', '-f', 'out/combined-twrp_dijun.ninja', '-t', 'commands', object_name], cwd=ANDROID, text=True)
            row = next(row for row in commands.splitlines() if row.endswith(' system/core/fs_mgr/libsnapshot/snapshot.cpp'))
            compile_snapshot = shlex.split(row)[1:] if row.startswith('PWD=') else shlex.split(row)
            compile_snapshot[compile_snapshot.index('-o')+1] = str(work/'snapshot.o')
            compile_snapshot[compile_snapshot.index('-MF')+1] = str(work/'snapshot.d')
            compile_snapshot.insert(-1, '-I'+str(ANDROID/'system/core/fs_mgr/libsnapshot'))
            compile_snapshot[-1] = str(override)
            build(compile_snapshot)
            for name in shlex.split((work/'snapshot.d').read_text().replace('\\\n', ' ').split(':', 1)[1]):
                path = ANDROID/name
                if path.is_file(): sources[str(path)] = sha(path)
            link.insert(link.index(str(work/'fixture.o'))+1, str(work/'snapshot.o'))
        link[link.index('-o')+1] = str(work/'test')
        link.append('-Wl,--wrap=fsync')
        build(link)
        data = (work/'test').read_bytes()
        assert data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', data, 18)[0] == 183
        jail = work/'jail'
        entries = {}
        for name, mode, *rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name == 'system/bin/linker64' or
                (name.startswith('system/lib64/') and name.endswith('.so'))):
                p = jail/'android'/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(rest[-1]); p.chmod(mode & 0o777)
                entries[name] = hashlib.sha256(rest[-1]).hexdigest()
        (jail/'work').mkdir()
        (jail/'dev').mkdir(); (jail/'dev/null').touch()
        shutil.copyfile(ROOT/'tools/qemu-user/qemu-aarch64', jail/'qemu'); (jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'test', jail/'test'); (jail/'test').chmod(0o755)
        def isolate():
            os.chroot(jail); os.chdir('/')
        cases = []
        names = ['normal', 'wipe', 'idempotent', 'wrong-state', 'missing-metadata', 'missing-snapshots', 'invalid-snapshot', 'forward-write-error', 'rollback-remove-error', 'boot-rename-error', 'state-open-error', 'merge-status-error', 'boot-sync-error', 'state-sync-error', 'boot-sync-interrupted', 'state-sync-interrupted']
        if args.postinstall:
            names = ['normal', 'boot-sync-retry', 'state-sync-retry', 'state-open-retry', 'merge-status-retry', 'slot-retry']
        if args.cancel:
            names = ['normal', 'missing-metadata', 'missing-snapshots', 'state-open-error', 'state-sync-error', 'state-sync-interrupted', 'merge-status-error', 'reset-normal', 'reset-open-error', 'reset-sync-error']
        for name in names:
            shutil.rmtree(jail/'work'); (jail/'work').mkdir()
            result = subprocess.run(['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                '/android/system/bin/linker64', '/test', name], preexec_fn=isolate,
                capture_output=True, text=True, timeout=20)
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=('Actual ARM64 SnapshotManager CancelUpdate / cleanup / state-file error propagation, including original DynamicPartitionControlAndroid ResetUpdate and persisted-state retry. Deny-all hardware and no snapshot mappings; None-state publication and Initiated missing-directory cases. Metadata mount token and merge HAL result are explicit boundaries. Not full install, merge or image deletion.' if args.cancel else __doc__) + ('\nOriginal PostinstallRunnerAction -> DynamicPartitionControlAndroid -> actual SnapshotManager completion and persistent-state retry. Synthetic plan skips scripts; metadata mount token, merge HAL, boot slot and hardware remain boundaries.' if args.postinstall else ''),
            sources=sources, dependencies=dependencies, image=str(image), image_sha256=sha(image),
            image_entries=entries, fixture_elf_machine=183, fixture_sha256=hashlib.sha256(data).hexdigest(),
            compile_template=compile_args, link_command=link, cases=cases,
            full_payload_install=False, postinstall_connected=args.postinstall, snapshot_manager_executed=True, hardware_effects_denied=True, merge_status_result_boundary=True, cancellation_executed=args.cancel, snapshot_override=str(args.snapshot_source) if args.snapshot_source else None, utility_override=str(args.utility_source) if args.utility_source else None)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'], len(cases), 'cases;', sum(c['status']=='FAIL' for c in cases), 'failures')
        return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
