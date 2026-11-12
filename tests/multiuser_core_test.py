#!/usr/bin/env python3
"""Execute production user discovery and per-user unlock control on file fixtures.

Property, DE/CE provider and partition operations are substitutes. XML/ABX parsing
uses checkout code. No real credentials, encryption keys, mounts or devices.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/root/AAA/twrp/bootable/recovery')
XML=SRC.parents[1]/'external/tinyxml2'

def method(text, signature):
    start=text.index(signature);opening=text.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

parser=argparse.ArgumentParser()
parser.add_argument('--report',type=Path,default=ROOT/'logs/multiuser-core.json')
args=parser.parse_args()
source=(SRC/'partitionmanager.cpp').read_text()
code='\n'.join(method(source, s) for s in [
    'void TWPartitionManager::ParseUsers()', 'void TWPartitionManager::MarkUserDecrypted(',
    'void TWPartitionManager::CheckUsersDecryptionStatus()', 'int TWPartitionManager::DecryptDevice('])
cases=['discover','missing-profile','repeat','stale-users','bad-directory',
       'malformed-xml','oversized-xml','abx','invalid-abx','identities',
       'wrong-credential','secondary-isolation','owner-unlock','service-unavailable',
       'missing-user','de-failure','already-unlocked','all-users']
with tempfile.TemporaryDirectory(prefix='dijun-users-') as d:
    d=Path(d);fixture=d/'fixture';fixture.mkdir()
    # Redirect only two filesystem root literals to disposable fixture roots.
    code=code.replace('"/data/system/users"','"'+str(fixture/'users')+'"')
    code=code.replace('"/data/misc/vold/user_keys/de"','"'+str(fixture/'keys')+'"')
    harness=(ROOT/'tests/multiuser_core_test.cpp').read_text().replace('// PRODUCTION_METHODS',code)
    harness=harness.replace('FIXTURE_ROOT',str(fixture))
    (d/'test.cpp').write_text(harness)
    subprocess.run(['g++','-std=c++23','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                    '-Wno-ignored-attributes','-fsanitize=undefined','-fno-sanitize-recover=all',
                    '-I'+str(SRC),'-I'+str(XML),str(d/'test.cpp'),str(SRC/'abx.cpp'),
                    str(XML/'tinyxml2.cpp'),'-lcrypto','-o',str(d/'test')],check=True)
    results=[]
    for case in cases:
        result=subprocess.run([str(d/'test'),case],text=True,capture_output=True,timeout=10)
        entry=dict(case=case,status='PASS' if result.returncode==0 else 'FAIL',exit=result.returncode,
                   diagnostic=(result.stdout+result.stderr).strip())
        results.append(entry);print(entry['status'],case,entry['diagnostic'],flush=True)
    report=dict(status='PASS' if all(x['exit']==0 for x in results) else 'FAIL',scope=__doc__,cases=results,
                sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                         [SRC/'partitionmanager.cpp',SRC/'abx.cpp',XML/'tinyxml2.cpp',Path(__file__),ROOT/'tests/multiuser_core_test.cpp']})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(report['status']!='PASS')
