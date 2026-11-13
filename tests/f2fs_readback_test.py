#!/usr/bin/env python3
"""Read ARM64-created F2FS files through a separately packaged host reader.

Current-image make_f2fs/sload_f2fs run via pinned QEMU/linker in a private chroot.
Debian amd64 dump.f2fs reads ordinary image files; compare every exported byte
and require unchanged image SHA. Not a mount, fscrypt, full Recovery caller/GUI,
metadata fidelity, sparse allocation, compressed filesystem or power-loss test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from nested_partition_path_test import ROOT
sys.path.insert(0, str(ROOT/'scripts'))
from firmware_facts import boot_parts, ramdisk_entries


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-reader',action='store_true')
    parser.add_argument('--report',type=Path,default=ROOT/'logs/f2fs-readback.json')
    args=parser.parse_args()
    index=json.loads((ROOT/'simulation-report.json').read_text())
    image=ROOT/index['image'];assert sha(image)==index['image_sha256']
    qemu=ROOT/'tools/qemu-user/qemu-aarch64'
    qsource=qemu.parent/'source.json';assert sha(qemu)==json.loads(qsource.read_text())['binary_sha256']
    host_meta=ROOT/'tools/f2fs-host'/('source.json' if args.stock_reader else 'reader.json');host_info=json.loads(host_meta.read_text())
    reader=host_meta.parent/host_info['binary'];assert sha(reader)==host_info['binary_sha256']
    dependencies=[]
    import re
    for line in subprocess.check_output(['ldd',str(reader)],text=True).splitlines():
        found=re.search(r'(/[^\s()]+)',line)
        if found:dependencies.append(Path(found[1]))
    transcripts=[];ramdisk={};cases=[]
    with tempfile.TemporaryDirectory(prefix='dijun-f2fs-readback-') as temp:
        work=Path(temp);jail=work/'jail';jail.mkdir();android=jail/'android'
        for name,mode,*rest in ramdisk_entries(boot_parts(image.read_bytes())[1]['ramdisk']):
            if not name.startswith(('system/bin/','system/lib64/')) or not stat.S_ISREG(mode):continue
            dest=android/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(rest[-1]);dest.chmod(mode&0o777);ramdisk[name]=sha(dest)
        shutil.copyfile(qemu,jail/'qemu');(jail/'qemu').chmod(0o755)
        (jail/'dev').mkdir();(jail/'dev/null').touch()
        (jail/'proc').mkdir();(jail/'proc/mounts').write_text('')
        fixture=jail/'fixtures';fixture.mkdir();source=fixture/'source';source.mkdir()
        expected={
            'empty.bin':b'',
            'inline.bin':bytes(range(251)),
            'payload.bin':b'F2FS independent readback marker\n'*1024+bytes(range(256)),
            'nested/跨目录-文件.bin':b'\0'*4096+bytes(range(256))*33,
            'nested/multi-node.bin':hashlib.shake_256(b'dijun multi-node deterministic fixture').digest((5<<20)+17),
            'zero-ranges.bin':b'head\n'+b'\0'*(3<<20)+b'tail\n',
        }
        for name,data in expected.items():
            dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        volume=fixture/'volume.img'
        with volume.open('xb') as file:file.truncate(256<<20)
        env={k:v for k,v in os.environ.items() if not k.startswith(('LD_','QEMU_'))}
        def target(tool,args):
            command=['chroot',str(jail),'/qemu','-L','/android','-E','LD_LIBRARY_PATH=/android/system/lib64','/android/system/bin/linker64','/android/system/bin/'+tool,*args]
            run=subprocess.run(command,env=env,capture_output=True,text=True,timeout=90)
            transcripts.append(dict(tool=tool,args=args,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr));assert run.returncode==0,transcripts[-1]
        target('make_f2fs',['-g','android','-O','project_quota,extra_attr','/fixtures/volume.img','65536'])
        target('sload_f2fs',['-f','/fixtures/source','/fixtures/volume.img'])
        # Debian1.16 has per-inode extraction, no Android recursive -r/-o.
        # Locate known synthetic names in actual inode blocks; the external
        # reader resolves NAT/data itself. This is not general directory lookup.
        def locate(path):
            blob=path.read_bytes();nodes={}
            for offset in range(0,len(blob),4096):
                node=blob[offset:offset+4096]
                if len(node)!=4096:continue
                mode=struct.unpack_from('<H',node)[0]
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):continue
                length=struct.unpack_from('<I',node,88)[0]
                if not 0<length<=255:continue
                raw=node[92:92+length]
                try:base=raw.decode('utf-8')
                except UnicodeDecodeError:continue
                if base not in {Path(n).name for n in expected}|{'nested'}:continue
                nid,ino=struct.unpack_from('<II',node,4072)
                if nid==0 or nid!=ino:continue
                nodes.setdefault(base,[]).append(dict(nid=nid,parent=struct.unpack_from('<I',node,84)[0],offset=offset,size=struct.unpack_from('<Q',node,16)[0]))
            assert all(len(rows)==1 for rows in nodes.values()),nodes
            assert set(nodes)=={Path(n).name for n in expected}|{'nested'},nodes
            nested=nodes['nested'][0]['nid']
            for name in expected:
                assert nodes[Path(name).name][0]['parent']==(nested if '/' in name else 3)
            return nodes
        nodes=locate(volume)
        def readback(name,path):
            dest=work/name;dest.mkdir();before=sha(path);runs=[];files={}
            for relative in expected:
                base=Path(relative).name;nid=nodes[base][0]['nid']
                folder=dest/str(nid);folder.mkdir()
                run=subprocess.run([str(reader),'-i',str(nid),str(path)],input='y\n',cwd=folder,env=env,capture_output=True,text=True,timeout=60)
                exported=folder/'lost_found'/base
                if exported.is_file():files[relative]=exported.read_bytes()
                runs.append(dict(nid=nid,returncode=run.returncode,stdout=run.stdout,stderr=run.stderr))
            return dict(returncode=0 if all(r['returncode']==0 for r in runs) else 1,runs=runs,image_unchanged=sha(path)==before),files
        result,actual=readback('intact',volume)
        checks=dict(reader_success=result['returncode']==0,exact_paths=set(actual)==set(expected),exact_bytes=actual==expected,image_unchanged=result['image_unchanged'])
        cases.append(dict(name='intact-content',status='PASS' if all(checks.values()) else 'FAIL',checks=checks,reader=result,expected_files={n:dict(size=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in expected.items()},files={n:dict(size=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in actual.items()}))
        # Change one actual payload block in a copy; structural fsck success
        # alone cannot establish content integrity. No data/metadata rewrite by reader.
        corrupt=fixture/'corrupt.img';shutil.copyfile(volume,corrupt)
        marker=expected['payload.bin'][:128];blob=corrupt.read_bytes();offset=blob.find(marker)
        assert offset>=0 and blob.find(marker,offset+1)>=0
        with corrupt.open('r+b') as file:file.seek(offset+20);byte=file.read(1);file.seek(offset+20);file.write(bytes([byte[0]^0x80]))
        result,actual=readback('corrupted',corrupt)
        checks=dict(reader_success=result['returncode']==0,exact_paths=set(actual)==set(expected),only_payload_changed={n for n in expected if actual.get(n)!=expected[n]}=={'payload.bin'},content_difference_detected=actual!=expected,image_unchanged=result['image_unchanged'],original_payload_unchanged=(source/'payload.bin').read_bytes()==expected['payload.bin'])
        cases.append(dict(name='payload-corruption-detected',status='PASS' if all(checks.values()) else 'FAIL',checks=checks,changed_offset=offset+20,reader=result))
        print(json.dumps([dict(name=c['name'],status=c['status'],checks=c['checks']) for c in cases],indent=2),flush=True)
    sources=[Path(__file__),ROOT/'tests/nested_partition_path_test.py',ROOT/'scripts/firmware_facts.py',ROOT/'scripts/acquire_firmware.py',ROOT/'scripts/f2fs-reader-source.json',ROOT/'scripts/f2fs-inline-reader.patch',ROOT/'scripts/prepare_f2fs_reader.py',image,qemu,qsource,reader,host_meta,*dependencies]
    report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,image_sha256=index['image_sha256'],cases=cases,tool_transcripts=transcripts,reader_package=host_info,inode_locator='Known synthetic basenames and parent fields in raw inode blocks; not a general directory walker. dump.f2fs independently resolves NAT and data.',inode_nodes=nodes,ramdisk_files=ramdisk,sources={str(p):sha(p) for p in sources})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return report['status']!='PASS'


if __name__=='__main__':raise SystemExit(main())
