#!/usr/bin/env python3
"""Run real ARM64 operation executor -> snapshot extent writer -> COW -> decompression.

Synthetic payload operation data, real current build archives; no DeltaPerformer
hash/signature validation, VABC Init/SnapshotManager, devices, merge or full OTA.
Delivered linker/shared libraries are image-bound; archives are test-time bound,
not historically bound by the older image provenance manifest.
"""
import hashlib
import bz2
import lzma
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

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT.parent / 'twrp'
sys.path.insert(0, str(ROOT / 'scripts'))
from acquire_firmware import fields
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(command):
    result = subprocess.run(command, cwd=ANDROID, capture_output=True, text=True)
    if result.returncode:
        print(result.stdout + result.stderr, file=sys.stderr)
        result.check_returncode()


def main():
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image'])
    assert sha(image) == index['image_sha256']
    qemu = ROOT/'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_operation_cow.cpp',
                ROOT/'scripts/acquire_firmware.py', ROOT/'scripts/firmware_facts.py']}
    stock = []
    for path in sorted((ROOT/'firmware/samples').glob('*/payload-manifest.pb')):
        inventory = json.loads(path.with_name('inventory.json').read_text())
        assert sha(path) == inventory['manifest_sha256']
        assert inventory['payload_metadata_hash_verified'] is True
        manifest = dict(fields(path.read_bytes()))
        dynamic = dict(fields(manifest[15]))
        assert manifest.get(12, 0) == 0 and inventory['payload_version'] == 2
        options = dict(version=dynamic[5], compression=dynamic[4].decode(), factor=dynamic[7])
        assert options == dict(version=3, compression='lz4', factor=65536)
        operation_counts = {}
        for partition in inventory['partitions'].values():
            for name, count in partition['operation_counts'].items():
                operation_counts[name] = operation_counts.get(name, 0) + count
        stock.append(dict(sample=path.parent.name, manifest_sha256=sha(path),
                          inventory_sha256=sha(path.with_name('inventory.json')),
                          snapshot_enabled=bool(dynamic[2]), vabc_enabled=bool(dynamic[3]),
                          disable_ublk=bool(dynamic.get(8, 0)), options=options,
                          operation_counts=operation_counts,
                          unhandled_dynamic_fields=[n for n in dynamic if n > 8]))
    assert len(stock) == 6
    ninja = ANDROID/'prebuilts/build-tools/linux-x86/bin/ninja'
    target = 'out/soong/.intermediates/system/update_engine/update_engine_sideload/android_recovery_arm64_armv8-a/unstripped/update_engine_sideload'
    commands = subprocess.run([str(ninja), '-f', 'out/combined-twrp_dijun.ninja', '-t', 'commands', target],
                              cwd=ANDROID, capture_output=True, text=True, check=True).stdout.splitlines()
    compile_line = next(l for l in commands if l.endswith('payload_consumer/install_operation_executor.cc'))
    link_line = next(l for l in reversed(commands) if 'clang++ ' in l and ' -o '+target+' ' in l)
    with tempfile.TemporaryDirectory(prefix='ota-operation-cow-') as temp:
        work = Path(temp)
        obj = work/'fixture.o'
        compile_args = shlex.split(compile_line)
        if compile_args[0].startswith('PWD='):
            compile_args.pop(0)
        for flag in ['-o', '-MF']:
            pos = compile_args.index(flag)
            compile_args[pos+1] = str(obj if flag == '-o' else work/'fixture.d')
        compile_args[-1] = str(ROOT/'tests/ota_operation_cow.cpp')
        # Android release flags disable assert; keep the fixture's checks AND
        # its I/O calls active. Production archives retain their original flags.
        compile_args.insert(1, '-UNDEBUG')
        compile_args = [a for a in compile_args if a != '-DNDEBUG']
        build(compile_args)
        # Bind the actual generated protobuf and transitive headers used to
        # build the fixture. Archives remain independently hash-bound below.
        depfile = (work/'fixture.d').read_text().replace('\\\n', ' ')
        for arg in shlex.split(depfile.split(':', 1)[1]):
            path = ANDROID/arg
            if path.is_file():
                sources[str(path)] = sha(path)
        # Reuse only link inputs/libraries, never the engine's entry-point objects.
        link_args = shlex.split(link_line)
        rsp_arg = next(a for a in link_args if a.startswith('@'))
        rsp = ANDROID/rsp_arg[1:]
        inputs = shlex.split(rsp.read_text())
        libraries = [a for a in inputs if not a.endswith('.o')]
        assert all(not a.startswith('@') for a in libraries)
        cow = next(a for a in libraries if a.endswith('/libsnapshot_cow.a'))
        assert 'android_recovery_arm64' in cow
        link_args[link_args.index(rsp_arg):link_args.index(rsp_arg)+1] = [str(obj)] + libraries
        link_args[link_args.index('-o')+1] = str(work/'cow-test')
        build(link_args)
        binary = (work/'cow-test').read_bytes()
        assert binary[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', binary, 18)[0] == 183
        dependencies = {}
        for path in [qemu, qemu.with_name('source.json'), rsp, ANDROID/compile_args[0]]:
            dependencies[str(path)] = sha(path)
        for arg in link_args + libraries:
            path = ANDROID/arg
            if path.is_file() and path != obj and not path.is_relative_to(work):
                dependencies[str(path)] = sha(path)
        # Bind actual archive sources/headers, not merely the binary name.
        snapshot = ANDROID/'system/core/fs_mgr/libsnapshot'
        for folder in [snapshot/'libsnapshot_cow', snapshot/'include/libsnapshot']:
            for path in sorted(folder.glob('*')):
                if path.suffix in ('.cpp', '.h'):
                    sources[str(path)] = sha(path)
        consumer = ANDROID/'system/update_engine/payload_consumer'
        for stem in ['install_operation_executor', 'snapshot_extent_writer', 'block_extent_writer',
                     'bzip_extent_writer', 'xz_extent_writer', 'extent_writer']:
            for suffix in ['.cc', '.h']:
                path = consumer/(stem + suffix)
                if path.is_file():
                    sources[str(path)] = sha(path)
        entries = {}
        for name, mode, *rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name == 'system/bin/linker64' or
                    (name.startswith('system/lib64/') and name.endswith('.so'))):
                dest = work/'jail/android'/name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(rest[-1]); dest.chmod(mode & 0o777)
                entries[name] = hashlib.sha256(rest[-1]).hexdigest()
        jail = work/'jail'
        (jail/'work').mkdir()
        (jail/'dev').mkdir(); (jail/'dev/null').touch()
        shutil.copyfile(qemu, jail/'qemu'); (jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'cow-test', jail/'test'); (jail/'test').chmod(0o755)
        def isolate():
            os.chroot(jail); os.chdir('/')
        cases = []
        expected = bytes((i//4096+i%31)%251 for i in range(65536))
        (jail/'work/expected.bin').write_bytes(expected)
        scenarios = [
            ('replace', 0, expected, 'roundtrip'),
            ('replace-bz', 1, bz2.compress(expected), 'roundtrip'),
            ('replace-xz', 8, lzma.compress(expected, check=lzma.CHECK_CRC32), 'roundtrip'),
            ('bz-bad-magic', 1, b'invalid-bz-data', 'bad-data'),
            ('xz-bad-magic', 8, b'invalid-xz-data', 'bad-data'),
            ('target-overflow', 0, expected, 'target-overflow'),
            ('short-raw', 0, expected[:4096], 'short-raw'),
            ('oversize-raw', 0, expected + bytes(4096), 'oversize-raw'),
        ]
        for name, kind, data, mode in scenarios:
            (jail/'work/input.bin').write_bytes(data)
            cmd = ['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                   '/android/system/bin/linker64', '/test', str(kind), 'lz4', '65536', mode]
            result = subprocess.run(cmd, preexec_fn=isolate, capture_output=True, text=True, timeout=25)
            assert result.returncode == 0 and 'PASS ' in result.stdout, (name, result.returncode, result.stdout, result.stderr)
            actual = (jail/'work/readback.bin').read_bytes()
            assert len(actual) == len(expected)
            if mode == 'roundtrip' or mode == 'oversize-raw':
                assert actual == expected
            else:
                assert actual != expected
            cases.append(dict(name=name, status='PASS', stdout=result.stdout, stderr=result.stderr,
                              input_sha256=hashlib.sha256(data).hexdigest(),
                              expected_sha256=hashlib.sha256(expected).hexdigest(),
                              readback_sha256=hashlib.sha256(actual).hexdigest()))
        report = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image),
                      fixture_elf_machine=183, cow_archive=str(ANDROID/cow), cow_archive_sha256=sha(ANDROID/cow),
                      sources=sources, dependencies=dependencies, image_entries=entries,
                      qemu_sha256=sha(qemu), stock=stock, cases=cases,
                      compile_command=compile_args, link_command=link_args,
                      full_ota_install=False, snapshot_manager_executed=False,
                      archive_historically_bound_to_image=False,
                      engine_link_response_sha256=sha(rsp))
        report['fixture_sha256'] = hashlib.sha256(binary).hexdigest()
        report['upper_source_review'] = {
            'execution': False,
            'sources': {str(p): sha(p) for p in [
                consumer/'delta_performer.cc', consumer/'vabc_partition_writer.cc',
                consumer/'filesystem_verifier_action.cc']},
            'scope': 'Source review only: DeltaPerformer buffers declared input and invokes final partition writer completion; target hash mismatch is rejected by FilesystemVerifierAction. These upper layers were not executed by this suite.',
        }
        (ROOT/'logs/ota-operation-cow.json').write_text(json.dumps(report, indent=2)+'\n')
        print('PASS: eight ARM64 executor/snapshot/COW scenarios; short input true distinguished from complete output')


if __name__ == '__main__':
    main()
