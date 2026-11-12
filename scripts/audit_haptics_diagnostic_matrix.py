#!/usr/bin/env python3
"""Bind four waveform/gain request controls to actual diagnostic artifacts; no motor acceptance."""
import hashlib,json,struct,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((ROOT/n).read_text())
def maps(r,key):
 for n,h in r.get(key,{}).items():assert sha(Path(n) if Path(n).is_absolute() else ROOT/n)==h,n
def effect(c):return bytearray.fromhex(next(l.split()[1] for l in c['stdout'].splitlines() if l.startswith('EFFECT_HEX ')))
def operations(c):return [l.split()[1] for l in c['stdout'].splitlines() if l.startswith('BEGIN ')]
def main():
 host=read('logs/haptics-diagnostic-test.json');target=read('logs/haptics-diagnostic-arm64-test.json')
 assert host['status']==target['status']=='PASS' and len(host['cases'])==47 and len(target['cases'])==18
 for r in [host,target]:
  maps(r,'sources');assert all(c['status']=='PASS' for c in r['cases'])
 cases={c['case']:c for c in host['cases']}
 sine0=effect(cases['success']);sine1=effect(cases['sine-gain-success']);assert sine0==sine1
 prior=read('logs/haptics-driver-emulation.json');expected=bytearray.fromhex(next(c['effect_hex'] for c in prior['fixture_bytes'] if c['requested_ms']==80));expected[2:4]=b'\xff\xff';assert sine0==expected
 service=read('logs/haptics-service-request-emulation.json');original=next(c for c in service['cases'] if c['case']=='service-request-80')['operations'];expected=bytearray.fromhex(original[1]['effect']);expected[40:48]=bytes(8)
 for label in ['stock-success','custom-success','custom-no-gain']:
  actual=effect(cases[label]);actual[40:48]=bytes(8);assert actual==expected
  assert next(l.split()[1] for l in cases[label]['stdout'].splitlines() if l.startswith('CUSTOM_HEX '))==original[1]['custom']=='00001f00'
 for label in ['success','sine-gain-success','stock-success','custom-success','custom-no-gain']:
  assert cases[label]['result']==0
  assert operations(cases[label])==['open','name','capabilities']+(['gain'] if label in ['sine-gain-success','stock-success'] else [])+['upload','play','erase','close']
 for label in ['sine-gain-no-gain','sine-gain-no-sine','sine-gain-write-error','sine-gain-write-short','custom-no-custom']:
  assert cases[label]['result']==1 and 'upload' not in operations(cases[label]) and 'play' not in operations(cases[label])
 for c in target['cases']:
  assert 'BEGIN upload' not in c['stdout'] and 'BEGIN play' not in c['stdout'] and 'BEGIN gain' not in c['stdout']
  assert c['result']==(1 if c['case']=='missing-inspect' or c['case'].startswith('regular-file') else 2)
  if c['case'].startswith('regular-file'):assert 'errno=25 ' in c['stdout'] and 'END close result=0 errno=0 ' in c['stdout']
 build=read('tools/haptics-diagnostic/haptics-diagnostic-arm64.json');maps(build,'inputs');binary=ROOT/build['binary'];assert sha(binary)==build['sha256']
 blob=binary.read_bytes();assert blob[:6]==b'\x7fELF\x02\x01' and struct.unpack_from('<H',blob,18)[0]==183
 phoff=struct.unpack_from('<Q',blob,32)[0];size,count=struct.unpack_from('<HH',blob,54)
 assert size==56 and phoff+size*count<=len(blob) and all(struct.unpack_from('<I',blob,phoff+i*size)[0]!=3 for i in range(count))
 archive=ROOT/'tools/haptics-diagnostic-os4.zip'
 with zipfile.ZipFile(archive) as z:
  assert set(z.namelist())=={'haptics-diagnostic-arm64','haptics-diagnostic-arm64.json','README.md'}
  for n in z.namelist():assert z.read(n)==(ROOT/'tools/haptics-diagnostic'/n).read_bytes()
 index=read('simulation-report.json');assert sha(Path(index['image']))==index['image_sha256']
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 for name,count in [('haptics-independent-diagnostic',47),('haptics-diagnostic-ARM64-startup',18)]:
  c,=[c for c in index['checks'] if c['name']==name];assert c['count']==count and c['evidence_sha256']==sha(ROOT/c['evidence'])
 assert index['haptics_diagnostic_matrix']['archive_sha256']==sha(archive)
 evidence=['logs/haptics-diagnostic-test.json','logs/haptics-diagnostic-arm64-test.json','logs/haptics-diagnostic-matrix-build.log','tools/haptics-diagnostic/haptics-diagnostic-arm64.json','tools/haptics-diagnostic-os4.zip']
 result=dict(status='PASS',scope=__doc__,host_cases=47,arm64_cases=18,binary_sha256=sha(binary),image_sha256=index['image_sha256'],production_change=False,
  evidence={n:sha(ROOT/n) for n in evidence},documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md','tools/haptics-diagnostic/README.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-diagnostic-matrix-audit.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: four waveform/gain controls,host47,target18,exact request bytes and static archive; no physical playback or production change.')
if __name__=='__main__':main()
