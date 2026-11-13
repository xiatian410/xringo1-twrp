#!/usr/bin/env python3
"""Run original ARM64 controller unmap aggregation with explicit mapping boundaries.

Whole production controller TU with original tracked-device iteration. Snapshot
unmap result, logical unmap effects and metadata token are explicit doubles.
No actual SnapshotManager, device mapper, mount, full verifier or installation.
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
    parser.add_argument('--source', type=Path, default=ANDROID/'system/update_engine/aosp/dynamic_partition_control_android.cc')
    parser.add_argument('--report', type=Path, default=ROOT/'logs/ota-unmap-control.json')
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    args.source = args.source.resolve()
    if args.image is not None:
        args.image = args.image.resolve()
    reference = json.loads((ROOT/'logs/ota-vabc-session.json').read_text())
    current = json.loads((ROOT/'simulation-report.json').read_text())
    image = args.image or Path(current['image'])
    if args.image is None:
        assert sha(image) == current['image_sha256']
    # Reuse resolved flags and paths, binding the CURRENT rebuilt link inputs.
    # The fixture/delta objects replace the stale temporary object explicitly.
    dependencies = {name: sha(name) for name in reference['dependencies']}
    assert dependencies[str(ROOT/'tools/qemu-user/qemu-aarch64')] == reference['dependencies'][str(ROOT/'tools/qemu-user/qemu-aarch64')]
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_unmap_control.cpp',
        ROOT/'tests/ota_vabc_session.py', args.source, ROOT/'scripts/firmware_facts.py',
        ROOT/'scripts/acquire_firmware.py']}
    with tempfile.TemporaryDirectory(prefix='ota-snapshot-map-') as temp:
        work = Path(temp)
        obj = 'out/soong/.intermediates/system/update_engine/libupdate_engine_boot_control/android_recovery_arm64_armv8-a_static/obj/system/update_engine/aosp/dynamic_partition_control_android.o'
        commands = subprocess.check_output(['prebuilts/build-tools/linux-x86/bin/ninja', '-f', 'out/combined-twrp_dijun.ninja', '-t', 'commands', obj], cwd=ANDROID, text=True)
        row = next(row for row in commands.splitlines() if row.endswith(' system/update_engine/aosp/dynamic_partition_control_android.cc'))
        compile_args = shlex.split(row)[1:] if row.startswith('PWD=') else shlex.split(row)
        compile_args = [a for a in compile_args if a != '-DNDEBUG']
        compile_args.insert(1, '-UNDEBUG')
        # Record fixture and intact production TU separately. Never rewrite a method.
        for unit, source in [('fixture', ROOT/'tests/ota_unmap_control.cpp'), ('delta', args.source)]:
            command = compile_args.copy()
            if unit == 'delta':
                # Match libchrome's release ABI; assertions stay enabled only
                # in the fixture, original production TU uses original NDEBUG.
                command = [a for a in command if a != '-UNDEBUG']
                command.insert(1, '-DNDEBUG')
            command[command.index('-o')+1] = str(work/(unit+'.o'))
            command[command.index('-MF')+1] = str(work/(unit+'.d'))
            command.insert(-1, '-I'+str(ANDROID/'system/update_engine/aosp'))
            command[-1] = str(source)
            build(command)
            depfile = (work/(unit+'.d')).read_text().replace('\\\n', ' ')
            for name in shlex.split(depfile.split(':', 1)[1]):
                p = ANDROID/name
                if p.is_file(): sources[str(p)] = sha(p)
        link = reference['link_command'].copy()
        old_obj = next(a for a in link if a.endswith('/fixture.o'))
        link[link.index(old_obj):link.index(old_obj)+1] = [str(work/'fixture.o'), str(work/'delta.o')]
        link[link.index('-o')+1] = str(work/'test')
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
        for name in ['normal', 'snapshot-fail', 'logical-fail', 'combined-fail', 'empty', 'source-only', 'non-vab', 'no-metadata']:
            result = subprocess.run(['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                '/android/system/bin/linker64', '/test', name], preexec_fn=isolate,
                capture_output=True, text=True, timeout=20)
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                returncode=result.returncode, stdout=result.stdout, stderr=result.stderr))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=__doc__,
            sources=sources, dependencies=dependencies, image=str(image), image_sha256=sha(image),
            image_entries=entries, fixture_elf_machine=183, fixture_sha256=hashlib.sha256(data).hexdigest(),
            compile_template=compile_args, link_command=link, cases=cases,
            full_payload_install=False, mapping_result_boundary=True, snapshot_manager_executed=False)
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'], len(cases), 'cases;', sum(c['status']=='FAIL' for c in cases), 'failures')
        return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
