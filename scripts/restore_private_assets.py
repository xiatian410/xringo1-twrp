#!/usr/bin/env python3
"""Restore omitted build assets from a local source tree, verifying every hash.

No network download, keys, device access or firmware modification. Source tree
must have paths matching PRIVATE-ASSETS.json; destination is this checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

def main():
 root=Path(__file__).resolve().parents[1]
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--from-tree',type=Path,required=True)
 args=parser.parse_args();source=args.from_tree.resolve()
 records=json.loads((root/'PRIVATE-ASSETS.json').read_text())['files']
 ready=[]
 for item in records:
  rel=Path(item['path']);assert not rel.is_absolute() and '..' not in rel.parts and 'security' not in rel.parts
  src=source/rel;dest=root/rel
  assert src.resolve().is_relative_to(source) and src.is_file() and not src.is_symlink(),str(src)
  assert dest.resolve().is_relative_to(root) and not dest.is_symlink(),str(dest)
  data=src.read_bytes();assert len(data)==item['size'] and hashlib.sha256(data).hexdigest()==item['sha256'],str(src)
  if dest.exists():assert dest.is_file() and dest.read_bytes()==data,'Conflicting asset: '+str(dest)
  ready.append((src,dest,int(item['mode'],8)))
 for src,dest,mode in ready:
  dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():shutil.copyfile(src,dest);dest.chmod(mode)
 print('Verified/restored',len(ready),'local assets; no keys imported.')
if __name__=='__main__':main()
