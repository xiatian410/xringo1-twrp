#!/usr/bin/env python3
"""Stream synthetic CrAU/protobuf/operation bytes through intact ARM64 engine.

Original metadata parsing, plan creation, partition factory, VABC/COW and final
verifier execute. FakeBootControl/FakeHardware and FileControl replace device
mapping; snapshot view is materialized for verification. Recovery signature
checks retain their existing compile-time behavior; not authenticated stock OTA.
"""
import argparse
import bz2
import lzma
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
    parser.add_argument('--source', type=Path, default=ANDROID/'system/update_engine/payload_consumer/delta_performer.cc')
    parser.add_argument('--report', type=Path, default=ROOT/'logs/ota-payload-stream.json')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--finalize', action='store_true', help='Connect final hash verification to original PostinstallRunnerAction; five targeted cases')
    args = parser.parse_args()
    if args.finalize and args.report == ROOT/'logs/ota-payload-stream.json':
        args.report = ROOT/'logs/ota-payload-finalization.json'
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
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_payload_stream.cpp',
        ROOT/'tests/ota_vabc_session.py', args.source, ROOT/'scripts/firmware_facts.py',
        ROOT/'scripts/acquire_firmware.py']}
    with tempfile.TemporaryDirectory(prefix='ota-payload-stream-') as temp:
        work = Path(temp)
        compile_args = reference['compile_command'].copy()
        # Record fixture and intact production TU separately. Never rewrite a method.
        for unit, source in [('fixture', ROOT/'tests/ota_payload_stream.cpp'), ('delta', args.source)]:
            command = compile_args.copy()
            command[command.index('-o')+1] = str(work/(unit+'.o'))
            command[command.index('-MF')+1] = str(work/(unit+'.d'))
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
        # Ephemeral key is fixture-only and never enters the public tree.
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(work/'key.pem')], capture_output=True, check=True)
        subprocess.run(['openssl', 'pkey', '-in', str(work/'key.pem'), '-pubout', '-out', str(jail/'work/public.pem')], capture_output=True, check=True)
        (jail/'dev').mkdir(); (jail/'dev/null').touch()
        shutil.copyfile(ROOT/'tools/qemu-user/qemu-aarch64', jail/'qemu'); (jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'test', jail/'test'); (jail/'test').chmod(0o755)
        def isolate():
            os.chroot(jail); os.chdir('/')
        cases = []
        expected = bytes((i//4096+i%31)%251 for i in range(65536))
        (jail/'work/expected.bin').write_bytes(expected)
        scenarios = [('raw', 0, expected), ('bz', 1, bz2.compress(expected)),
                     ('xz', 8, lzma.compress(expected, check=lzma.CHECK_CRC32))]
        scenarios += [(name, 0, expected) for name in ['bad-magic', 'bad-major', 'bad-minor',
            'bad-metadata-size', 'bad-operation-hash', 'prepare-fail', 'open-fail', 'truncated-data', 'truncated-signature', 'missing-signature']]
        if args.finalize:
            scenarios = [(name, 0, expected) for name in ['raw', 'finish-fail', 'slot-fail', 'no-switch', 'final-hash-fail']]
        for name, kind, encoded in scenarios:
            for stale in ['test.cow', 'readback.bin', 'view.bin']:
                (jail/'work'/stale).unlink(missing_ok=True)
            (jail/'work/input.bin').write_bytes(encoded)
            result = subprocess.run(['/qemu', '-L', '/android', '-E', 'LD_LIBRARY_PATH=/android/system/lib64',
                '/android/system/bin/linker64', '/test', name, str(kind), *(['finalize'] if args.finalize else [])], preexec_fn=isolate,
                capture_output=True, text=True, timeout=20)
            readback = jail/'work/readback.bin'
            if result.returncode == 0:
                assert readback.read_bytes() == expected if args.finalize or name in ['raw', 'bz', 'xz'] else not readback.exists()
            cases.append(dict(name=name, status='PASS' if result.returncode == 0 else 'FAIL',
                returncode=result.returncode, stdout=result.stdout, stderr=result.stderr,
                input_sha256=hashlib.sha256(encoded).hexdigest()))
        report = dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL', scope=(__doc__ + ('\nFinalization mode connects original PostinstallRunnerAction and observes FinishUpdate -> SetActiveBootSlot ordering. Boot control/hardware are explicit test doubles; no real slot, metadata or vbmeta writes, actual postinstall script, SnapshotManager or merge.' if args.finalize else '')),
            sources=sources, dependencies=dependencies, image=str(image), image_sha256=sha(image),
            image_entries=entries, fixture_elf_machine=183, fixture_sha256=hashlib.sha256(data).hexdigest(),
            compile_template=compile_args, link_command=link, cases=cases,
            full_payload_install=False, parsed_manifest_seeded=False, writer_failure_boundary=False,
            synthetic_payload_stream=True, real_signature_verification=False,
            postinstall_connected=args.finalize, boot_control_boundary="Explicit observing FakeBootControl and FileControl; no real slot or metadata writes",
            snapshot_mapping="FileControl ordinary COW file, materialized original reader output; no SnapshotManager or snapuserd")
        args.report.write_text(json.dumps(report, indent=2)+'\n')
        print(report['status'], len(cases), 'cases;', sum(c['status']=='FAIL' for c in cases), 'failures')
        return 0 if report['status']=='PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
