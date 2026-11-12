#!/usr/bin/env python3
"""Execute current Recovery ARM64 COW archive with stock OTA options on private files.

This tests the current build archive's real writer, parser and LZ4 decompressor, not SnapshotManager,
update_engine scheduling, dm-user/UBLK, LP metadata, merge or an OTA install.
The delivered linker/shared libraries are image-bound. The archive is bound at
test time and is a declared engine link input, not historically hash-bound to
the delivered executable by the older 775-source provenance manifest.
No phone, device node, mount or physical block device is used.
"""
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
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_cow_roundtrip.cpp',
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
        stock.append(dict(sample=path.parent.name, manifest_sha256=sha(path),
                          inventory_sha256=sha(path.with_name('inventory.json')),
                          snapshot_enabled=bool(dynamic[2]), vabc_enabled=bool(dynamic[3]),
                          disable_ublk=bool(dynamic.get(8, 0)), options=options,
                          unhandled_dynamic_fields=[n for n in dynamic if n > 8]))
    assert len(stock) == 6
    ninja = ANDROID/'prebuilts/build-tools/linux-x86/bin/ninja'
    target = 'out/soong/.intermediates/system/update_engine/update_engine_sideload/android_recovery_arm64_armv8-a/unstripped/update_engine_sideload'
    commands = subprocess.run([str(ninja), '-f', 'out/combined-twrp_dijun.ninja', '-t', 'commands', target],
                              cwd=ANDROID, capture_output=True, text=True, check=True).stdout.splitlines()
    compile_line = next(l for l in commands if l.endswith('libsnapshot_cow/writer_v3.cpp'))
    link_line = next(l for l in reversed(commands) if 'clang++ ' in l and ' -o '+target+' ' in l)
    with tempfile.TemporaryDirectory(prefix='ota-cow-') as temp:
        work = Path(temp)
        obj = work/'fixture.o'
        compile_args = shlex.split(compile_line)
        if compile_args[0].startswith('PWD='):
            compile_args.pop(0)
        for flag in ['-o', '-MF']:
            pos = compile_args.index(flag)
            compile_args[pos+1] = str(obj if flag == '-o' else work/'fixture.d')
        compile_args[-1] = str(ROOT/'tests/ota_cow_roundtrip.cpp')
        # Android release flags disable assert; keep the fixture's checks AND
        # its I/O calls active. Production archives retain their original flags.
        compile_args.insert(1, '-UNDEBUG')
        compile_args = [a for a in compile_args if a != '-DNDEBUG']
        build(compile_args)
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
        scenarios = [('stock-options', 3, 'lz4', 65536, 'roundtrip'),
                     ('capacity-rejection', 3, 'lz4', 65536, 'capacity'),
                     ('bad-magic', 3, 'lz4', 65536, 'bad-magic'),
                     ('unsupported-version', 99, 'lz4', 65536, 'reject-options'),
                     ('unsupported-compressor', 3, 'invalid', 65536, 'reject-options')]
        for name, version, compression, factor, mode in scenarios:
            readback = jail/'work/readback.bin'
            readback.unlink(missing_ok=True)
            cmd = ['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                   '/android/system/bin/linker64', '/test', str(version), compression, str(factor), mode]
            result = subprocess.run(cmd, preexec_fn=isolate, capture_output=True, text=True, timeout=25)
            assert result.returncode == 0 and 'PASS ' in result.stdout, (name, result.returncode, result.stdout, result.stderr)
            row = dict(name=name, status='PASS', stdout=result.stdout, stderr=result.stderr)
            if mode == 'roundtrip':
                expected = bytes((i//4096+i%31)%251 for i in range(factor))
                assert readback.read_bytes() == expected
                row['readback_sha256'] = sha(readback)
                row['cow_sha256'] = sha(jail/'work/test.cow')
            else:
                assert not readback.exists()
            cases.append(row)
        report = dict(status='PASS', scope=__doc__, image=str(image), image_sha256=sha(image),
                      fixture_elf_machine=183, cow_archive=str(ANDROID/cow), cow_archive_sha256=sha(ANDROID/cow),
                      sources=sources, dependencies=dependencies, image_entries=entries,
                      qemu_sha256=sha(qemu), stock=stock, cases=cases,
                      compile_command=compile_args, link_command=link_args,
                      full_ota_install=False, snapshot_manager_executed=False,
                      archive_historically_bound_to_image=False,
                      engine_link_response_sha256=sha(rsp))
        (ROOT/'logs/ota-cow-roundtrip.json').write_text(json.dumps(report, indent=2)+'\n')
        print('PASS: ARM64 COW v3/LZ4/64KiB roundtrip and four failure boundaries; six stock option sets agree')


if __name__ == '__main__':
    main()
