#!/usr/bin/env python3
"""Actual ARM64 postinstall program and original PostinstallRunnerAction/Subprocess.

Private chroot, real clone/pipes/signalfd/wait and harmless dynamic ARM64 child.
Explicit execv QEMU bridge preserves script argv; mounts/readonly/boot/hardware
are recorded fixtures. No devices, actual OTA scripts, snapshots or full OTA.
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
from acquire_firmware import fields


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT/'logs/ota-postinstall-program.json')
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    fixture = ROOT/'tests/ota_postinstall_program.cpp'
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
    sources = {str(p): sha(p) for p in [Path(__file__), fixture,
        ROOT/'tests/ota_vabc_session.py', ANDROID/'system/core/fs_mgr/libsnapshot/snapshot.cpp',
        ANDROID/'system/core/fs_mgr/libsnapshot/utility.cpp', ROOT/'scripts/firmware_facts.py',
        ROOT/'scripts/acquire_firmware.py']}
    for path in [ANDROID/'system/update_engine/aosp/dynamic_partition_control_android.cc',
                     ANDROID/'system/update_engine/payload_consumer/postinstall_runner_action.cc',
                     ANDROID/'system/update_engine/common/subprocess.cc', ANDROID/'external/libbrillo/brillo/process.cc',
                     ANDROID/'external/libbrillo/brillo/process_reaper.cc', ANDROID/'external/libbrillo/brillo/asynchronous_signal_handler.cc',
                     ROOT/'tests/ota_postinstall_program.c']:
        sources[str(path)] = sha(path)
    stock_postinstall = []
    for path in sorted((ROOT/'firmware/samples').glob('*/payload-manifest.pb')):
        inventory = json.loads(path.with_name('inventory.json').read_text())
        assert sha(path) == inventory['manifest_sha256']
        configured = []
        for field, value in fields(path.read_bytes()):
            if field != 13:
                continue
            partition = dict(fields(value))
            if partition.get(2) or partition.get(3):
                configured.append(dict(partition=partition[1].decode(), run=bool(partition.get(2)),
                    path=partition.get(3, b'postinst').decode(), optional=bool(partition.get(9))))
        stock_postinstall.append(dict(sample=path.parent.name, manifest_sha256=sha(path), configured=configured))
        sources[str(path)] = sha(path)
    with tempfile.TemporaryDirectory(prefix='ota-postinstall-program-') as temp:
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
        link[link.index('-o')+1] = str(work/'test')
        symbols = ['execv',
            '_ZN22chromeos_update_engine5utils12IsMountpointERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE',
            '_ZN22chromeos_update_engine5utils15MountFilesystemERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_mS9_S9_',
            '_ZN22chromeos_update_engine5utils17UnmountFilesystemERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE',
            '_ZN22chromeos_update_engine5utils22SetBlockDeviceReadOnlyERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEEb']
        link += ['-Wl,--wrap='+symbol for symbol in symbols]
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
        clang = ANDROID/'prebuilts/clang/host/linux-x86/clang-r547379/bin/clang'
        libc = ANDROID/'out/soong/.intermediates/bionic/libc'
        begin = libc/'crtbegin_dynamic/android_recovery_arm64_armv8-a/crtbegin_dynamic.o'
        end = libc/'crtend_android/android_recovery_arm64_armv8-a/crtend_android.o'
        for p in [clang, begin, end]: dependencies[str(p)] = sha(p)
        child_command = [str(clang), '--target=aarch64-linux-android35', '-fuse-ld=lld',
            '-nostdlib', '-fPIE', '-pie', '-Wl,--dynamic-linker=/system/bin/linker64', str(begin),
            str(ROOT/'tests/ota_postinstall_program.c'), str(jail/'android/system/lib64/libc.so'),
            str(end), '-o', str(work/'program')]
        build(child_command)
        child = (work/'program').read_bytes()
        assert child[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H',child,18)[0] == 183
        def isolate():
            os.chroot(jail); os.chdir('/')
        cases = []
        names = ['normal','exit7','optional-exit7','exit3','exit4','signal15','missing-program','mount-fail','cancel']
        for name in names:
            shutil.rmtree(jail/'work'); (jail/'work').mkdir()
            destination = jail/'work/mount/bin/postinstall'
            destination.parent.mkdir(parents=True)
            destination.write_bytes(child); destination.chmod(0o755)
            result = subprocess.run(['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                '/android/system/bin/linker64', '/test', name], preexec_fn=isolate,
                capture_output=True, text=True, timeout=20)
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=__doc__,
            sources=sources, dependencies=dependencies, image=str(image), image_sha256=sha(image),
            image_entries=entries, fixture_elf_machine=183, fixture_sha256=hashlib.sha256(data).hexdigest(),
            child_elf_machine=183, child_sha256=hashlib.sha256(child).hexdigest(), child_command=child_command,
            compile_template=compile_args, link_command=link, cases=cases,
            full_payload_install=False, original_postinstall=True, original_subprocess=True,
            exec_boundary='QEMU execv bridge, original argv preserved', mount_boundary=True,
            snapshot_manager_executed=False, production_fix=False, stock_postinstall=stock_postinstall)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'], len(cases), 'cases;', sum(c['status']=='FAIL' for c in cases), 'failures')
        return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
