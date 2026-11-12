#!/usr/bin/env python3
"""Export reviewed text sources and optionally commit/push the public mirror.

The workspace includes stock blobs and device captures. Export uses an explicit
directory/extension allowlist, excludes private keys, and refuses credential
patterns. It never copies compiled artifacts, logs or firmware payload bytes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(os.environ.get('DIJUN_WORKSPACE', Path(__file__).resolve().parents[1])).resolve()
MIRROR = ROOT.parent / 'xringo1-twrp-public'
REPOSITORY = 'xiatian410/xringo1-twrp'
SUFFIXES = {'.md', '.py', '.cpp', '.c', '.h', '.hpp', '.sh', '.ps1', '.json', '.mk', '.bp',
            '.rc', '.prop', '.conf', '.fstab', '.flags', '.te', '.contexts', '.list', '.plan', '.patch', '.xml', '.yml', '.yaml'}
NAMES = {'file_contexts', 'service_contexts', 'property_contexts', 'vendorsetup.sh', 'NOTICE', 'LICENSE', '.gitignore'}
SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}')

def digest(data):return hashlib.sha256(data).hexdigest()

def candidates():
    for name in ['AGENTS.md', 'README.md', '.gitignore', 'ADAPTATION-GOALS.md', 'MAINTENANCE.md',
                 'FEATURE-USAGE.md', 'BUILD-AND-TEST.md', 'FIRMWARE-MAP.md', 'compatibility-matrix.md',
                 'simulation-report.md', 'simulation-report.json', 'firmware-inventory.json', 'NOTICE']:
        path=ROOT/name
        if path.is_file():yield path
    for name in ['scripts', 'tests', 'docs', 'dtsrc/O1_asic_dual', '.github', 'manifests',
                 'tools/haptics-diagnostic', 'tools/settings-state-collector']:
        for path in sorted((ROOT/name).rglob('*')):
            if not path.is_file() or path.is_symlink():continue
            rel=path.relative_to(ROOT)
            if any(p in {'__pycache__', '.cache', '.git', 'security'} for p in rel.parts):continue
            if 'prebuilt' in rel.parts and path.name!='Android.mk' and path.suffix!='.json':continue
            if path.suffix not in SUFFIXES and path.name not in NAMES:continue
            yield path

def export():
    if ROOT==MIRROR or (ROOT/'SOURCE-MANIFEST.json').exists():
        raise ValueError('Export from the full workspace, or set DIJUN_WORKSPACE to its path')
    if MIRROR.is_symlink():raise ValueError('Refuse symlink mirror')
    files={}
    for path in candidates():
        data=path.read_bytes();data.decode('utf-8')
        if b'\0' in data or SECRET.search(data):raise ValueError('Non-text/credential candidate: '+str(path.relative_to(ROOT)))
        # Git preserves the executable bit, not local group/world write bits.
        mode=0o755 if path.stat().st_mode & 0o111 else 0o644
        files[str(path.relative_to(ROOT))]=(data,mode)
    private=[]
    for path in sorted((ROOT/'dtsrc/O1_asic_dual').rglob('*')):
        if path.is_file() and not path.is_symlink() and str(path.relative_to(ROOT)) not in files:
            # Keys/certificates are deliberately not fingerprinted publicly.
            if 'security' in path.relative_to(ROOT).parts:continue
            data=path.read_bytes()
            private.append(dict(path=str(path.relative_to(ROOT)),size=len(data),sha256=digest(data),mode=oct(path.stat().st_mode & 0o777)))
    files['PRIVATE-ASSETS.json']=((json.dumps(dict(scope='Metadata only. Obtain assets locally from the documented OTA sources; no private keys included.',files=private),indent=2)+'\n').encode(),0o644)
    inventory={name:dict(sha256=digest(data),mode=oct(mode)) for name,(data,mode) in sorted(files.items())}
    files['SOURCE-MANIFEST.json']=((json.dumps(inventory,indent=2)+'\n').encode(),0o644)
    MIRROR.mkdir(parents=True,exist_ok=True)
    # Remove only stale paths from a previous explicit export manifest.
    old=MIRROR/'SOURCE-MANIFEST.json'
    if old.exists():
        for name in json.loads(old.read_text()):
            if name not in files:
                target=MIRROR/name
                if not target.resolve().is_relative_to(MIRROR.resolve()):raise ValueError(name)
                if target.is_file():target.unlink()
    for name,(data,mode) in files.items():
        dest=MIRROR/name
        if dest.is_symlink():raise ValueError('Refuse exported symlink: '+name)
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);dest.chmod(mode)
    subprocess.run(['python3',str(MIRROR/'scripts/check_public_tree.py')],cwd=MIRROR,check=True)
    print('Exported',len(files),'text source/configuration files;',len(private),'private asset metadata records.',flush=True)
    return sorted(files)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--push',action='store_true')
    parser.add_argument('--message',default='Synchronize maintained dijun recovery sources')
    args=parser.parse_args();files=export()
    if not args.push:return
    if not (MIRROR/'.git').is_dir():raise ValueError('Initialize and review the public mirror before the first push')
    origin=subprocess.check_output(['git','remote','get-url','origin'],cwd=MIRROR,text=True).strip()
    if origin not in {'https://github.com/'+REPOSITORY+'.git','git@github.com:'+REPOSITORY+'.git'}:raise ValueError('Unexpected remote: '+origin)
    subprocess.run(['git','add','--',*files],cwd=MIRROR,check=True)
    # Include deletions only of already tracked files; never stage unlisted local data.
    subprocess.run(['git','add','-u'],cwd=MIRROR,check=True)
    pending=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=MIRROR,text=True).splitlines()
    allowed=set(files)
    for name in pending:
        if (MIRROR/name).exists() and name not in allowed:raise ValueError('Unreviewed staged path: '+name)
    if pending:subprocess.run(['git','commit','-m',args.message],cwd=MIRROR,check=True)
    subprocess.run(['git','push','origin','main'],cwd=MIRROR,check=True)
    local=subprocess.check_output(['git','rev-parse','HEAD'],cwd=MIRROR,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=MIRROR,text=True).split()[0]
    assert remote==local,'Remote commit mismatch'
    print('Verified GitHub synchronization:',REPOSITORY,local)

if __name__=='__main__':main()
