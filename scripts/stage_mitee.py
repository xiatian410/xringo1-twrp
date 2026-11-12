#!/usr/bin/env python3
"""Stage the dijun MiTEE ELF closure from the extracted, matching OTA vendor.
Vendor DSOs stay private to the HAL processes, never replace TWRP's DSOs.
Static symbol checks are necessary but do not prove secure-world compatibility.
"""
from pathlib import Path
import hashlib,json,re,shutil,stat,struct,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from repack_ramdisk import parse_cpio
from lz4legacy import decompress
ROOT=Path(__file__).resolve().parent.parent
V=ROOT/'imgs/firmware/vendor'
OVERLAY=ROOT/'dtsrc/O1_asic_dual/prebuilt/dijun/mitee/root'
CACHE=ROOT/'imgs/firmware/recovery-elf'
BASE=ROOT/'imgs/built/twrp-recovery-keystorefix.img'

def elf(path):
    dynamic=subprocess.check_output(['readelf','-dW',str(path)],text=True)
    needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]',dynamic)
    out=subprocess.check_output(['readelf','--dyn-syms','-W',str(path)],text=True)
    defs=set(); refs=set()
    for l in out.splitlines():
        p=l.split()
        if len(p)<8 or not p[0].rstrip(':').isdigit(): continue
        # GNU IFUNC is printed as '<OS specific>: 10' (three columns).
        if p[3]=='<OS': p=p[:3]+['IFUNC']+p[6:]
        symbol=p[7].replace('@@','@')
        if p[6]=='UND':
            if p[4]!='WEAK': refs.add(symbol)
        elif p[5] in ('DEFAULT','PROTECTED') and p[4] in ('GLOBAL','WEAK','UNIQUE'):
            defs.add(symbol); defs.add(symbol.split('@')[0])
    return needed,defs,refs

def main():
    CACHE.mkdir(parents=True,exist_ok=True)
    b=BASE.read_bytes(); n=struct.unpack_from('<I',b,12)[0]
    ents=parse_cpio(decompress(b[4096:4096+n]))
    for e in ents:
        if (e[0].startswith('system/lib64/') or e[0]=='system/bin/linker64') and stat.S_ISREG(e[1]):
            p=CACHE/e[0]; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(e[11])
    binaries=['bin/tee-supplicant','bin/hw/android.hardware.security.keymint@3.0-service.mitee','bin/hw/android.hardware.gatekeeper-service.mitee']
    # MiTEE authenticates d_path(exe): preserve original vendor executable paths.
    ld=next(e[11].decode() for e in ents if e[0]=='system/etc/ld.config.txt')
    assert 'dir.recovery = /system/bin' in ld
    if 'dir.recovery = /vendor/bin' not in ld:
        ld=ld.replace('dir.recovery = /system/bin',
                      'dir.recovery = /system/bin\ndir.recovery = /vendor/bin',1)
    config=OVERLAY/'system/etc/ld.config.txt'
    config.parent.mkdir(parents=True,exist_ok=True); config.write_text(ld)
    chosen={}; provenance={}; queue=[]
    for rel in binaries:
        src=V/rel; dst=OVERLAY/'vendor'/rel
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst); dst.chmod(0o755)
        queue.append(src)
        provenance[str(dst.relative_to(OVERLAY))]=str(src.relative_to(ROOT))
    visited=set()
    while queue:
        p=queue.pop(0)
        if p in visited: continue
        visited.add(p)
        for dep in elf(p)[0]:
            if dep in chosen: continue
            vp=V/'lib64'/dep; sp=CACHE/'system/lib64'/dep
            if dep in ('libbinder.so','libbinder_ndk.so') and sp.exists():
                chosen[dep]=sp; queue.append(sp)
            elif vp.exists():
                chosen[dep]=vp; queue.append(vp)
            elif sp.exists():
                chosen[dep]=sp; queue.append(sp)
            else: raise SystemExit(f'MISSING NEEDED: {dep}, owner {p}')
    private=OVERLAY/'system/lib64/mitee'
    private.mkdir(parents=True,exist_ok=True)
    for stale in private.glob('*.so'):
        if stale.name not in chosen or not chosen[stale.name].is_relative_to(V): stale.unlink()
    for dep,src in chosen.items():
        if src.is_relative_to(V):
            dst=private/dep; shutil.copyfile(src,dst); dst.chmod(0o644)
            provenance[str(dst.relative_to(OVERLAY))]=str(src.relative_to(ROOT))
    # VINTF fragments and TA images come from the same vendor filesystem.
    manifest_names=['android.hardware.security.keymint-service.mitee.xml',
                    'android.hardware.security.sharedsecret-service.mitee.xml',
                    'android.hardware.security.secureclock-service.mitee.xml',
                    'android.hardware.gatekeeper-service.mitee.xml']
    for name in manifest_names:
        src=V/'etc/vintf/manifest'/name
        dst=OVERLAY/'system/etc/vintf/manifest'/name
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst); dst.chmod(0o644)
        provenance[str(dst.relative_to(OVERLAY))]=str(src.relative_to(ROOT))
    for src in sorted((V/'mitee/ta').glob('*.ta')):
        dst=OVERLAY/'vendor/mitee/ta'/src.name
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(src,dst); dst.chmod(0o644)
        provenance[str(dst.relative_to(OVERLAY))]=str(src.relative_to(ROOT))
    checks={}
    for rel in binaries:
        start=V/rel; todo=[start]; seen=set(); definitions=set(); refs=set()
        while todo:
            p=todo.pop()
            if p in seen: continue
            seen.add(p); deps,defs,undefined=elf(p); definitions|=defs; refs|=undefined
            todo += [chosen[d] for d in deps]
        missing=sorted(refs-definitions)
        checks[rel]={'elfs':len(seen),'unresolved_strong_symbols':missing}
        print(rel, 'ELFs',len(seen),'unresolved',missing[:30])
    files=[]
    for path,source in sorted(provenance.items()):
        p=OVERLAY/path
        files.append({'path':path,'source':source,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    inventory={'ota':'OS4.0.0.19.XODCNXM','files':files,'checks':checks,'private_dso_count':len(list(private.glob('*.so')))}
    (ROOT/'dtsrc/O1_asic_dual/mitee-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print('Private DSOs:',inventory['private_dso_count'],'bytes',sum(p.stat().st_size for p in private.glob('*.so')))
    if any(c['unresolved_strong_symbols'] for c in checks.values()): raise SystemExit('FAIL: ELF imports unresolved; do not build a runtime image')
if __name__=='__main__': main()
