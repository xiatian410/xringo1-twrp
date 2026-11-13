#!/usr/bin/env python3
"""Build a local host-only F2FS reader with the extra_attr inline offset fix.

Requires gcc/make/autoconf/automake/libtool/pkgconf/uuid-dev. Obtains Debian
source, verifies pinned archive hashes, patches only the diagnostic reader.
No Recovery source, image, phone, mount or block device is modified.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'tools/f2fs-host'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    WORK.mkdir(parents=True,exist_ok=True)
    reference=json.loads((ROOT/'scripts/f2fs-reader-source.json').read_text())
    if not all((WORK/n).exists() for n in reference['archives']):
        subprocess.run(['apt-get','source','--download-only','f2fs-tools=1.16.0-1.1'],cwd=WORK,check=True)
    for name,digest in reference['archives'].items():assert sha(WORK/name)==digest,name
    patch=ROOT/'scripts/f2fs-inline-reader.patch'
    assert sha(patch)==reference['patch_sha256']
    source=WORK/'reader-source'
    if source.exists():raise ValueError('Reader build directory already exists; preserve it and choose a fresh workspace before rebuilding')
    subprocess.run(['dpkg-source','-x',str(WORK/'f2fs-tools_1.16.0-1.1.dsc'),str(source)],check=True)
    subprocess.run(['patch','-p1','-i',str(patch)],cwd=source,check=True)
    log=WORK/'reader-build.log'
    with log.open('w') as output:
        for command in [['./autogen.sh'],['./configure','--without-selinux','--disable-shared'],['make','-j'+subprocess.check_output(['nproc'],text=True).strip()]]:
            subprocess.run(command,cwd=source,stdout=output,stderr=subprocess.STDOUT,check=True)
    binary=source/'fsck/fsck.f2fs';dest=WORK/'dump.f2fs';shutil.copy2(binary,dest)
    metadata=dict(binary=dest.name,binary_sha256=sha(dest),source=reference,build_log_sha256=sha(log),scope='Host reader only, one inline extraction offset correction; no production patch or firmware change.')
    (WORK/'reader.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('Built host-only reader:',dest,sha(dest))


if __name__=='__main__':main()
