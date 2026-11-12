#!/usr/bin/env python3
"""Record the generated tree and pinned platform changes used for an image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
ANDROID=Path('/root/AAA/twrp')
TREE=ANDROID/'device/xiaomi/O1_asic'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

parser=argparse.ArgumentParser()
parser.add_argument('image',type=Path)
parser.add_argument('--log',type=Path,required=True)
args=parser.parse_args()
series=json.loads((TREE/'patches/series.json').read_text())
report=dict(image=str(args.image),image_sha256=sha(args.image),source_repositories={},
            build_command='make -j$(nproc) installclean; make -j$(nproc) recoveryimage',
            jobs=int(subprocess.check_output(['nproc'],text=True)),
            build_log=str(args.log),build_log_sha256=sha(args.log),tree_snapshot=str(TREE),files={},symlinks={})
for repo,spec in series['repositories'].items():
    head=subprocess.check_output(['git','-C',str(ANDROID/repo),'rev-parse','HEAD'],text=True).strip()
    assert head==spec['commit']
    changed=subprocess.check_output(['git','-C',str(ANDROID/repo),'diff','HEAD','--name-only'],text=True).splitlines()
    assert not set(changed)-set(spec['result_files'])
    report['source_repositories'][repo]=dict(head=head,changed_files=changed)
    for name,expected in spec['result_files'].items():
        p=ANDROID/repo/name; assert sha(p)==expected
        report['files'][str(p)]=expected
for p in sorted(TREE.rglob('*')):
    if '.git' in p.parts:continue
    if p.is_symlink():report['symlinks'][str(p)]=os.readlink(p)
    elif p.is_file():report['files'][str(p)]=sha(p)
dest=args.image.with_name(args.image.stem+'-sources.json')
dest.write_text(json.dumps(report,indent=2)+'\n')
print('Recorded',len(report['files']),'source files in',dest)
