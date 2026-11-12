#!/usr/bin/env python3
"""Run delivered Android filesystem tools on disposable regular files in QEMU.

Actual ARM64 linker, libraries and filesystem tools are extracted from the
current recovery image. No mount, loop device, physical block device, phone,
kernel filesystem implementation or GUI operation executes. Android SELinux
labeling/encrypted volumes and hardware discard behavior remain unverified.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from firmware_facts import boot_parts, ramdisk_entries

IMAGE = ROOT / 'imgs/built/recovery-dijun-unified-clock-failure.img'
QEMU = ROOT / 'tools/qemu-user/qemu-aarch64'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=IMAGE)
    parser.add_argument('--image-sha256', default='1c0813cf324d76be52e588e4dd3358c1c104946841e393aef84df2d951437adc')
    args = parser.parse_args()
    image_path = args.image.resolve()
    assert image_path.is_file() and not image_path.is_block_device()
    assert sha(image_path) == args.image_sha256
    qemu_source = QEMU.parent / 'source.json'
    assert sha(QEMU) == json.loads(qemu_source.read_text())['binary_sha256']
    _, parts = boot_parts(image_path.read_bytes())
    entries = ramdisk_entries(parts['ramdisk'])
    cases, binaries, transcripts = [], {}, []
    debugfs = Path(shutil.which('debugfs'))
    with tempfile.TemporaryDirectory(prefix='dijun-filesystem-tools-') as temp:
        work = Path(temp)
        prefix = work / 'root'
        for name, mode, *rest in entries:
            if not name.startswith(('system/bin/', 'system/lib64/', 'system/etc/')):
                continue
            relative = Path(name)
            assert not relative.is_absolute() and '..' not in relative.parts
            if stat.S_ISREG(mode):
                target = prefix / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(rest[-1])
                target.chmod(mode & 0o777)
                binaries[name] = hashlib.sha256(rest[-1]).hexdigest()
        fixtures = work / 'fixtures'
        fixtures.mkdir()
        def image(name, size):
            target = fixtures / name
            with target.open('xb') as stream:
                stream.truncate(size)
            assert target.is_file() and not target.is_symlink()
            return target

        env = {k: v for k, v in os.environ.items() if not k.startswith(('LD_', 'QEMU_'))}
        env.update(LD_LIBRARY_PATH=str(prefix / 'system/lib64'),
                   MKE2FS_CONFIG=str(prefix / 'system/etc/mke2fs.conf'))
        allowed = {'mke2fs', 'e2fsdroid', 'e2fsck', 'resize2fs', 'make_f2fs',
                   'fsck.f2fs', 'sload_f2fs', 'mkfs.erofs', 'fsck.erofs'}
        def execute(label, tool, args, success=True, expected_exit=None):
            assert tool in allowed
            # Every explicit path operand belongs to this run. The harness
            # accepts no external target path or command-line image override.
            for arg in map(str, args):
                if arg.startswith('/'):
                    assert arg.startswith(str(work) + '/'), arg
            command = [str(QEMU), '-L', str(prefix), str(prefix / 'system/bin/linker64'),
                       str(prefix / 'system/bin' / tool), *map(str, args)]
            run = subprocess.run(command, cwd=work, env=env, capture_output=True,
                                 text=True, timeout=45)
            transcripts.append(f'CASE {label}\nCOMMAND {command!r}\nEXIT {run.returncode}\n{run.stdout}\n{run.stderr}')
            if expected_exit is None:
                assert (run.returncode == 0) == success, (label, run.returncode, run.stdout, run.stderr)
            else:
                assert run.returncode == expected_exit, (label, run.returncode, run.stdout, run.stderr)
            cases.append(dict(case=label, status='PASS', tool=tool, returncode=run.returncode))
            return run

        src = fixtures / 'source'
        src.mkdir()
        payload = (b'dijun filesystem content\n' * 1024) + bytes(range(256))
        (src / 'payload.bin').write_bytes(payload)
        (src / 'empty').write_bytes(b'')
        (src / 'link').symlink_to('payload.bin')
        ext = image('ext4.img', 64 << 20)
        execute('ext4-format', 'mke2fs', ['-t', 'ext4', '-b', '4096', '-I', '512',
                                        '-O', 'metadata_csum,64bit,extent', ext, str(ext.stat().st_size // 4096)])
        with ext.open('rb') as stream:
            stream.seek(1024)
            sb = stream.read(1024)
        assert sb[56:58] == b'\x53\xef'
        assert struct.unpack_from('<I', sb, 4)[0] * (1024 << struct.unpack_from('<I', sb, 24)[0]) == ext.stat().st_size
        execute('ext4-populate', 'e2fsdroid', ['-e', '-f', src, ext])
        execute('ext4-repair-clean', 'e2fsck', ['-fp', ext])
        # Introduce a bounded metadata inconsistency with an independent host
        # tool. Actual target e2fsck must repair it and report exit 1.
        mutation = subprocess.run([str(debugfs), '-w', '-R',
                                   'set_inode_field /payload.bin links_count 7', str(ext)],
                                  capture_output=True, text=True, timeout=15)
        assert mutation.returncode == 0
        repaired = execute('ext4-repair-link-count', 'e2fsck', ['-fp', ext], expected_exit=1)
        assert 'FIXED' in repaired.stdout
        execute('ext4-check-after-repair', 'e2fsck', ['-fn', ext])
        out = fixtures / 'ext4-payload.bin'
        run = subprocess.run([str(debugfs), '-R', f'dump /payload.bin {out}', str(ext)],
                             cwd=work, capture_output=True, text=True, timeout=15)
        transcripts.append(f'HOST debugfs EXIT {run.returncode}\n{run.stdout}\n{run.stderr}')
        assert run.returncode == 0 and out.read_bytes() == payload
        cases.append(dict(case='ext4-independent-content-read', status='PASS', sha256=sha(out)))
        with ext.open('r+b') as stream:
            stream.truncate(96 << 20)
        execute('ext4-resize', 'resize2fs', [ext])
        execute('ext4-check-after-resize', 'e2fsck', ['-fn', ext])
        with ext.open('rb') as stream:
            stream.seek(1024 + 4)
            assert struct.unpack('<I', stream.read(4))[0] == (96 << 20) // 4096

        f2 = image('f2fs.img', 256 << 20)
        execute('f2fs-format-casefold', 'make_f2fs', ['-g', 'android', '-O', 'project_quota,extra_attr',
                                                   '-O', 'casefold', '-C', 'utf8', f2,
                                                   str(f2.stat().st_size // 4096)])
        with f2.open('rb') as stream:
            stream.seek(1024)
            sb = stream.read(128)
        assert struct.unpack_from('<I', sb)[0] == 0xf2f52010
        assert struct.unpack_from('<Q', sb, 36)[0] * 4096 == f2.stat().st_size
        # Same post-format tool as Recovery, without Android labels. Populate
        # actual fixture data; physical mount and casefold lookup are not tested.
        execute('f2fs-populate', 'sload_f2fs', ['-f', src, f2])
        before = sha(f2)
        execute('f2fs-check-dry-run', 'fsck.f2fs', ['-f', '--dry-run', f2])
        assert sha(f2) == before, 'dry-run modified the regular-file filesystem'

        erofs = image('erofs.img', 0)
        execute('erofs-format-lz4hc', 'mkfs.erofs', ['-zlz4hc', erofs, src])
        with erofs.open('rb') as stream:
            stream.seek(1024)
            assert stream.read(4) == struct.pack('<I', 0xe0f5e1e2)
        extracted = fixtures / 'erofs-extracted'
        before = sha(erofs)
        execute('erofs-check-extract', 'fsck.erofs', ['--extract=' + str(extracted), erofs])
        assert sha(erofs) == before and (extracted / 'payload.bin').read_bytes() == payload
        assert (extracted / 'link').is_symlink() and os.readlink(extracted / 'link') == 'payload.bin'
        cases.append(dict(case='erofs-content-and-symlink', status='PASS', sha256=sha(extracted / 'payload.bin')))
        # Unformatted private regular files must be rejected by each checker.
        for tool, args in [('e2fsck', ['-fn']), ('fsck.f2fs', ['-f', '--dry-run']), ('fsck.erofs', [])]:
            bad = image(tool + '-invalid.img', 4 << 20)
            execute(tool + '-reject-invalid', tool, [*args, bad], success=False)
    logs = ROOT / 'logs'
    (logs / 'filesystem-tools-image-test.log').write_text('\n'.join(transcripts))
    sources = [image_path, QEMU, qemu_source, debugfs, Path(__file__),
               ROOT / 'scripts/firmware_facts.py', ROOT / 'scripts/acquire_firmware.py',
               Path('/root/AAA/twrp/bootable/recovery/partition.cpp')]
    report = dict(status='PASS', scope=__doc__.strip(), cases=cases,
                  sources={str(p): sha(p) for p in sources}, ramdisk_files=binaries,
                  limitations=['QEMU uname exposes host kernel; not an Android kernel feature check.',
                               'Linker uses private LD_LIBRARY_PATH; production namespace and SELinux untested.',
                               'No GUI/PartitionManager operation, mount, encryption, discard or physical I/O.',
                               'No claim of complete F2FS data-content readback or kernel casefold behavior.'])
    (logs / 'filesystem-tools-image-test.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'actual ARM64 filesystem tool cases on disposable regular files')


if __name__ == '__main__':
    main()
