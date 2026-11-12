#!/usr/bin/env python3
"""Stream an unchanged locally available stock payload through the ARM64 engine.

Ordinary target files and COWs replace device mapping; original full manifest,
operation bytes and final partition hashes execute. No SnapshotManager, real
metadata, slot, postinstall, AVB or physical device. No signature-policy changes.
"""
import base64
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
import zipfile

from ota_vabc_session import ROOT, ANDROID, build
sys.path.insert(0, str(ROOT/'scripts'))
from acquire_firmware import payload_position
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    sample = ROOT/'firmware/samples/os4-current'
    inventory = json.loads((sample/'inventory.json').read_text())
    source = Path(inventory['source'])
    assert source.is_file() and not source.is_symlink()
    assert sha(sample/'payload-manifest.pb') == inventory['manifest_sha256']
    properties = dict(line.split('=', 1) for line in (sample/'payload_properties.txt').read_text().splitlines())
    with source.open('rb') as f, zipfile.ZipFile(f) as z:
        entry = z.getinfo('payload.bin')
        offset = payload_position(f, entry)
        assert entry.file_size == int(properties['FILE_SIZE'])
        f.seek(offset)
        header = f.read(24)
        magic, version, length, signature = struct.unpack('>4sQQI', header)
        assert magic == b'CrAU' and version == 2
        manifest = f.read(length)
        assert hashlib.sha256(manifest).hexdigest() == inventory['manifest_sha256']
        assert hashlib.sha256(header+manifest).digest() == base64.b64decode(properties['METADATA_HASH'])
    reference = json.loads((ROOT/'logs/ota-vabc-session.json').read_text())
    index = json.loads((ROOT/'simulation-report.json').read_text())
    image = Path(index['image']); assert sha(image) == index['image_sha256']
    dependencies = {n: sha(n) for n in reference['dependencies']}
    qemu = ROOT/'tools/qemu-user/qemu-aarch64'
    assert sha(qemu) == json.loads(qemu.with_name('source.json').read_text())['binary_sha256']
    sources = {str(p): sha(p) for p in [Path(__file__), ROOT/'tests/ota_stock_payload.cpp',
        ROOT/'tests/ota_vabc_session.py', ROOT/'scripts/acquire_firmware.py', ROOT/'scripts/firmware_facts.py']}
    # Disk-backed temporary files; full targets exceed the default /tmp tmpfs.
    temporary = ROOT/'logs/stock-payload-work'; temporary.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-', dir=temporary) as temp:
        work = Path(temp)
        compile_args = reference['compile_command'].copy()
        compile_args[compile_args.index('-o')+1] = str(work/'fixture.o')
        compile_args[compile_args.index('-MF')+1] = str(work/'fixture.d')
        compile_args[-1] = str(ROOT/'tests/ota_stock_payload.cpp')
        build(compile_args)
        for n in shlex.split((work/'fixture.d').read_text().replace('\\\n',' ').split(':',1)[1]):
            p=ANDROID/n
            if p.is_file(): sources[str(p)]=sha(p)
        # Bind directly used implementation files as well as original archives.
        for stem in ['delta_performer','filesystem_verifier_action','partition_writer','vabc_partition_writer','partition_writer_factory_android']:
            p=ANDROID/'system/update_engine/payload_consumer'/(stem+'.cc')
            sources[str(p)]=sha(p)
        link=reference['link_command'].copy()
        link[link.index(next(a for a in link if a.endswith('/fixture.o')))]=str(work/'fixture.o')
        link[link.index('-o')+1]=str(work/'test'); build(link)
        elf=(work/'test').read_bytes()
        assert elf[:6]==b'\x7fELF\x02\x01' and struct.unpack_from('<H',elf,18)[0]==183
        jail=work/'jail'; entries={}
        for name,mode,*rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if stat.S_ISREG(mode) and (name=='system/bin/linker64' or name=='system/etc/security/otacerts.zip' or (name.startswith('system/lib64/') and name.endswith('.so'))):
                p=jail/name if name=='system/etc/security/otacerts.zip' else jail/'android'/name
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(rest[-1]);p.chmod(mode&0o777);entries[name]=hashlib.sha256(rest[-1]).hexdigest()
        (jail/'work').mkdir();(jail/'dev').mkdir();(jail/'dev/null').touch()
        # Only this already existing ordinary ZIP is hard-linked read-only by
        # convention in the private namespace. Target code opens it O_RDONLY.
        os.link(source,jail/'work/source.zip')
        shutil.copyfile(qemu,jail/'qemu');(jail/'qemu').chmod(0o755)
        shutil.copyfile(work/'test',jail/'test');(jail/'test').chmod(0o755)
        def isolate():
            os.chroot(jail);os.chdir('/')
        command=['/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64',
            '/android/system/bin/linker64','/test',str(offset),properties['FILE_SIZE'],properties['METADATA_SIZE'],base64.b64decode(properties['FILE_HASH']).hex()]
        stdout=ROOT/'logs/ota-stock-payload.stdout';stderr=ROOT/'logs/ota-stock-payload.stderr'
        with stdout.open('w') as out,stderr.open('w') as err:
            result=subprocess.run(command,preexec_fn=isolate,stdout=out,stderr=err,timeout=1800)
        status='PASS' if result.returncode==0 and 'PASS full-stock-payload' in stdout.read_text() else 'FAIL'
        report=dict(status=status,scope=__doc__,sample='os4-current',image=str(image),image_sha256=sha(image),
            source_size=source.stat().st_size,source_sha256=sha(source),payload_offset=offset,payload_size=entry.file_size,
            expected_payload_sha256=base64.b64decode(properties['FILE_HASH']).hex(),manifest_sha256=inventory['manifest_sha256'],
            original_manifest_unmodified=True,original_payload_unmodified=True,sources=sources,dependencies=dependencies,image_entries=entries,
            fixture_elf_machine=183,fixture_sha256=hashlib.sha256(elf).hexdigest(),compile_command=compile_args,link_command=link,
            stdout=stdout.read_text(),stderr_sha256=sha(stderr),returncode=result.returncode,
            full_payload_streamed=status=='PASS',full_ota_install=False,snapshot_manager_executed=False,postinstall_executed=False,
            archive_historically_bound_to_image=False,signature_scope='Unchanged Recovery build behavior; no authenticated whole-OTA claim')
        (ROOT/'logs/ota-stock-payload.json').write_text(json.dumps(report,indent=2)+'\n')
        print(status,'full stock payload',entry.file_size,'bytes',flush=True)
        return result.returncode if result.returncode else (0 if status=='PASS' else 1)


if __name__=='__main__':sys.exit(main())
