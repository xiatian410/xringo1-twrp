#!/usr/bin/env python3
"""Actual ARM64 allocated COW -> controller OpenCowWriter -> two stock VABC ops.

Finite handoff coverage, not a full OTA replay. Synthetic32GiB LP, persistent
regular-file base/COW mappings, explicit HAL/kernel capability boundaries;
scratch/daemon disabled. No actual kernel map, mounted filesystem, slot or merge.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile

from ota_vabc_session import ROOT, ANDROID, build
from ota_snapshot_allocate import sha
from acquire_firmware import parse_manifest
from firmware_facts import boot_parts, ramdisk_entries

BASE_SYMBOL = '_ZN7android6fs_mgr22CreateLogicalPartitionENS0_28CreateLogicalPartitionParamsEPNSt3__112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEE'
REALPATH_SYMBOL = '_ZN7android4base8RealpathERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEEPS7_'


def main():
    index = json.loads((ROOT / 'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    reference = json.loads((ROOT / 'logs/ota-snapshot-initialize.json').read_text())
    qemu = ROOT / 'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    sample = ROOT / 'firmware/samples/os4-stable'
    inventory = json.loads((sample / 'inventory.json').read_text())
    manifest = sample / 'payload-manifest.pb'
    assert sha(manifest) == inventory['manifest_sha256']
    part = parse_manifest(manifest.read_bytes())['partitions']['mi_ext']
    original_image = sample / 'mi_ext.img'
    assert sha(original_image) == part['sha256']
    original_zip = sample / 'original-ota.zip'
    assert original_zip.is_file() and not original_zip.is_symlink()
    fixture = ROOT / 'tests/ota_snapshot_payload_handoff.cpp'
    support = ROOT / 'tests/ota_snapshot_initialize.cpp'
    prefix, rest = support.read_text().split('int main(int argc,char**argv){', 1)
    assert rest and 'class InitInfo' in prefix
    sources = {str(p): sha(p) for p in [Path(__file__), fixture, support,
        ROOT / 'tests/ota_snapshot_allocate.cpp', ROOT / 'tests/ota_snapshot_finish.cpp',
        ROOT / 'tests/ota_snapshot_allocate.py', ROOT / 'tests/ota_vabc_session.py',
        ROOT / 'scripts/acquire_firmware.py', ROOT / 'scripts/firmware_facts.py',
        ANDROID / 'system/core/fs_mgr/libsnapshot/snapshot.cpp',
        ANDROID / 'system/core/fs_mgr/fs_mgr_dm_linear.cpp',
        ANDROID / 'system/update_engine/aosp/dynamic_partition_control_android.cc',
        ANDROID / 'system/update_engine/payload_consumer/vabc_partition_writer.cc',
        ANDROID / 'system/update_engine/payload_consumer/install_operation_executor.cc']}
    operations = []
    expected = bytearray()
    with original_zip.open('rb') as package, original_image.open('rb') as golden:
        inputs = []
        for number in range(2):
            op = part['operations'][number]
            assert op[1] == [8, 0][number]
            package.seek(inventory['payload_data_zip_offset'] + op[2])
            data = package.read(op[3])
            assert len(data) == op[3] and hashlib.sha256(data).digest() == op[8]
            inputs.append(data)
            for block, length in op['extents']:
                golden.seek(block * 4096)
                segment = golden.read(length * 4096)
                assert len(segment) == length * 4096
                expected.extend(segment)
            operations.append(dict(number=number, type=op[1], extents=op['extents'],
                                   input_bytes=len(data), input_sha256=hashlib.sha256(data).hexdigest()))
    assert len(expected) == 4194304
    with tempfile.TemporaryDirectory(prefix='snapshot-handoff-', dir=ROOT / 'logs') as tmp:
        work = Path(tmp)
        (work / 'snapshot_init_support.inc').write_text(prefix)
        command = reference['compile_command'].copy()
        command.insert(1, '-I' + str(work))
        vabc = json.loads((ROOT / 'logs/ota-vabc-session.json').read_text())
        command[1:1] = [a for a in vabc['compile_command'] if a.startswith('-I') and a not in command]
        command[command.index('-o') + 1] = str(work / 'fixture.o')
        command[command.index('-MF') + 1] = str(work / 'fixture.d')
        command[-1] = str(fixture)
        build(command)
        for name in shlex.split((work / 'fixture.d').read_text().replace('\\\n', ' ').split(':', 1)[1]):
            dep = ANDROID / name
            if dep.is_file() and not dep.is_relative_to(work):
                sources[str(dep)] = sha(dep)
        link = reference['link_command'].copy()
        link[link.index(next(a for a in link if a.endswith('/fixture.o')))] = str(work / 'fixture.o')
        link[link.index('-o') + 1] = str(work / 'test')
        link += ['-Wl,--wrap=' + symbol for symbol in [BASE_SYMBOL, REALPATH_SYMBOL]]
        build(link)
        dependencies = {str(qemu): sha(qemu)}
        for argument in link:
            dep = ANDROID / argument
            if dep.is_file() and not dep.is_relative_to(work):
                dependencies[str(dep)] = sha(dep)
        elf = (work / 'test').read_bytes()
        assert elf[:6] == b'\x7fELF\x02\x01' and elf[18:20] == b'\xb7\0'
        jail = work / 'jail'
        entries = {}
        for name, mode, *rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name == 'system/bin/linker64' or name.startswith('system/lib64/') and name.endswith('.so')):
                path = jail / 'android' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(rest[-1]); path.chmod(mode & 0o777)
                entries[name] = hashlib.sha256(rest[-1]).hexdigest()
        (jail / 'dev').mkdir(); (jail / 'dev/null').touch()
        for name, source in [('qemu', qemu), ('test', work / 'test')]:
            shutil.copyfile(source, jail / name); (jail / name).chmod(0o755)

        def isolate():
            os.chroot(jail); os.chdir('/')

        cases = []
        for name in ['normal', 'resume', 'corrupt-header']:
            shutil.rmtree(jail / 'work', ignore_errors=True); (jail / 'work').mkdir()
            shutil.copyfile(manifest, jail / 'work/manifest.pb')
            (jail / 'work/expected.bin').write_bytes(expected)
            for i, data in enumerate(inputs):
                (jail / f'work/input{i}.bin').write_bytes(data)
            child = subprocess.run(['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                '/android/system/bin/linker64', '/test', name], preexec_fn=isolate,
                capture_output=True, text=True, timeout=60)
            ok = child.returncode == 0 and 'PASS ' + name in child.stdout
            readback = jail / 'work/readback.bin'
            if ok and name != 'corrupt-header':
                ok = readback.read_bytes() == expected
            cases.append(dict(name=name, status='PASS' if ok else 'FAIL', returncode=child.returncode,
                stdout=child.stdout, stderr=child.stderr,
                readback_sha256=sha(readback) if readback.exists() else None))
            print(cases[-1]['status'], name, flush=True)
        report = dict(status='PASS' if all(c['status'] == 'PASS' for c in cases) else 'FAIL', scope=__doc__,
            image=str(image), image_sha256=sha(image), image_entries=entries,
            sources=sources, dependencies=dependencies, compile_command=command, link_command=link,
            support_prefix_sha256=hashlib.sha256(prefix.encode()).hexdigest(), fixture_elf_machine=183,
            fixture_sha256=hashlib.sha256(elf).hexdigest(), manifest_sha256=sha(manifest),
            inventory_sha256=sha(sample / 'inventory.json'), stock_partition_sha256=part['sha256'],
            operations=operations, expected_bytes=len(expected), expected_sha256=hashlib.sha256(expected).hexdigest(),
            cases=cases, actual_snapshot_manager=True, actual_controller_open_writer=True, actual_vabc_writer=True,
            synthetic_layout=True, file_mapping_model=True, scratch_and_daemon_disabled_for_test=True,
            actual_kernel_mapping=False, full_ota_install=False, production_changes=False, new_build=False)
        (ROOT / 'logs/ota-snapshot-payload-handoff.json').write_text(json.dumps(report, indent=2) + '\n')
        return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
