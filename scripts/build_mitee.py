#!/usr/bin/env python3
"""Build the dijun MiTEE integration candidate from maintained tree files.
This is a ramdisk rebuild, not an Android source compile or proof of decryption.
"""
from pathlib import Path
import hashlib,json,stat,struct,subprocess,sys,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parent))
from lz4legacy import decompress
from repack_ramdisk import parse_cpio,emit_cpio
from make_fix_images import pack
ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT/'imgs/built/twrp-recovery-keystorefix.img'
OVERLAY=ROOT/'dtsrc/O1_asic_dual/prebuilt/dijun/mitee/root'

def main():
    inventory=json.loads((ROOT/'dtsrc/O1_asic_dual/mitee-inventory.json').read_text())
    assert all(not c['unresolved_strong_symbols'] for c in inventory['checks'].values())
    for file in inventory['files']:
        assert hashlib.sha256((OVERLAY/file['path']).read_bytes()).hexdigest()==file['sha256']
    subprocess.run(['sh','-n',str(OVERLAY/'system/bin/dijun-prepare-mitee.sh')],check=True)
    verifier=Path('/root/AAA/twrp/out/host/linux-x86/bin/host_init_verifier')
    if verifier.exists():
        for rc in (OVERLAY/'system/etc/init').glob('*.rc'):
            subprocess.run([str(verifier),str(rc)],check=True)
    raw=BASE.read_bytes(); n=struct.unpack_from('<I',raw,12)[0]
    original=parse_cpio(decompress(raw[4096:4096+n]))
    entries=original[:-1]; byname={e[0]:i for i,e in enumerate(entries)}
    replacements={}; added=[]
    def ensure_dir(path):
        if path in ('','.'): return
        if path in byname: return
        ensure_dir(str(Path(path).parent))
        byname[path]=len(entries)
        entries.append((path,stat.S_IFDIR|0o755,0,0,2,0,0,0,0,0,0,b''))
    for f in sorted(OVERLAY.rglob('*')):
        if not f.is_file(): continue
        name=f.relative_to(OVERLAY).as_posix(); payload=f.read_bytes()
        ensure_dir(str(Path(name).parent))
        mode=stat.S_IFREG | (0o755 if name.startswith(('system/bin/','vendor/bin/')) else 0o644)
        entry=(name,mode,0,0,1,0,len(payload),0,0,0,0,payload)
        if name in byname:
            old=entries[byname[name]]
            assert stat.S_ISREG(old[1]),name
            entries[byname[name]]=entry; replacements[name]=True
        else:
            byname[name]=len(entries); entries.append(entry); added.append(name)
    entries.append(original[-1])
    manifest={}
    for e in entries:
        if '/vintf/manifest/' in e[0] and e[0].endswith('.xml'):
            tree=ET.fromstring(e[11])
            if tree.get('type')!='device': continue
            for hal in tree.findall('hal'):
                for fq in hal.findall('fqname'):
                    key=(hal.findtext('name'),fq.text)
                    assert key not in manifest,(key,e[0],manifest.get(key))
                    manifest[key]=e[0]
    for name in ['android.hardware.security.keymint','android.hardware.security.sharedsecret','android.hardware.security.secureclock','android.hardware.gatekeeper']:
        assert any(key[0]==name for key in manifest),name
    table={e[0]:e for e in entries}
    rc=table['system/etc/init/dijun-mitee.rc'][11].decode()
    for rel in ['bin/tee-supplicant','bin/hw/android.hardware.security.keymint@3.0-service.mitee','bin/hw/android.hardware.gatekeeper-service.mitee']:
        name='vendor/'+rel
        assert '/'+name in rc,name
        assert stat.S_ISREG(table[name][1]) and table[name][1]&0o111,name
        assert table[name][11]==(ROOT/'imgs/firmware/vendor'/rel).read_bytes(),name
        assert 'system/'+rel not in table,rel
    assert b'dir.recovery = /vendor/bin' in table['system/etc/ld.config.txt'][11]
    cpio=emit_cpio(entries)
    result=subprocess.run(['lz4','-l','-12','-c','-q'],input=cpio,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    rd=Path('/tmp/dijun-mitee.rd'); rd.write_bytes(result.stdout)
    roundtrip=parse_cpio(decompress(result.stdout)); assert entries==roundtrip
    base_names={e[0]:e for e in original}
    new_names={e[0]:e for e in roundtrip}
    assert len(new_names)==len(roundtrip)
    assert not (base_names.keys()-new_names.keys())
    assert not [k for k in base_names if base_names[k]!=new_names[k] and k not in replacements]
    print('Verified complete ELF closure, shell syntax, unique AIDL instances, regular/executable modes, cpio round trip.')
    print('New files',len(added),'replaced',list(replacements),'ramdisk',len(result.stdout))
    out=ROOT/'imgs/built/twrp-recovery-mitee-vendorpath.img'
    pack(raw,str(rd),str(out))
    final=out.read_bytes(); expected=struct.unpack_from('<I',final,12)[0]
    assert len(final)==104857600 and final[4096:4096+expected]==result.stdout
    f=final[-64:]; orig,off,size=struct.unpack_from('>QQQ',f,12)
    bf=raw[-64:]; oldoff,oldsize=struct.unpack_from('>QQ',bf,20)
    assert size==oldsize and final[off:off+size]==raw[oldoff:oldoff+oldsize]
    print('ON-DISK MD5',hashlib.md5(final).hexdigest())
if __name__=='__main__': main()
