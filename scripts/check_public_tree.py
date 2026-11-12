#!/usr/bin/env python3
"""Check the public export inventory and pinned patch hashes, without blobs."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def main():
 manifest=json.loads((ROOT/'SOURCE-MANIFEST.json').read_text())
 for name,item in manifest.items():
  p=ROOT/name;assert p.resolve().is_relative_to(ROOT.resolve()) and not p.is_symlink(),name
  data=p.read_bytes();data.decode('utf-8');assert b'\0' not in data,name
  assert hashlib.sha256(data).hexdigest()==item['sha256'],name
  assert p.stat().st_mode & 0o777==int(item['mode'],8),name
  assert p.suffix not in {'.img','.ko','.so','.a','.zip','.deb','.pk8','.key'},name
  assert not re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}',data),name
  if p.suffix=='.py':compile(data,str(p),'exec')
  if p.suffix=='.json':
   # Android's JsonCpp task profiles intentionally allow whole-line comments.
   content=re.sub(rb'(?m)^\s*//[^\n]*',b'',data) if p.name=='task_profiles.json' else data
   try:json.loads(content)
   except ValueError as error:raise ValueError('Invalid JSON: '+name) from error
 tree=ROOT/'dtsrc/O1_asic_dual';spec=json.loads((tree/'patches/series.json').read_text())
 for repository,config in spec['repositories'].items():
  for patch in config['patches']:
   p=(tree/'patches'/patch['file']).resolve();assert p.is_relative_to(tree)
   assert hashlib.sha256(p.read_bytes()).hexdigest()==patch['sha256'],str(p)
 print('PASS: public source inventory, Python/JSON syntax, pinned patches and artifact exclusion;',len(manifest),'entries')
if __name__=='__main__':main()
