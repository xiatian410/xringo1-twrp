#!/usr/bin/env python3
"""Bind stock haptic supply/GPIO topology and retain electrical unknowns."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/haptics-power-topology.json';r=json.loads(path.read_text());assert r['status']=='PASS' and len(r['cases'])==6
 for group in ['sources','tests','emulator_files']:
  assert r[group]
  for name,digest in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==digest,name
 samples={p.parent.name for p in (ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')};assert {c['sample'] for c in r['cases']}==samples
 for c in r['cases']:
  assert c['status']=='PASS' and c['module_supplies']==['VP','VA']
  assert c['module_supply_struct_size']==(48 if c['sample'].startswith('os4-') else 64)
  assert set(c['supply_links'])=={'VA-supply'} and c['supply_links']['VA-supply']==c['va_regulator']['path']
  assert c['va_regulator']['properties']['regulator-name']==['mldo8']
  assert c['va_regulator']['properties']['regulator-min-microvolt']==[1650000]
  assert c['va_regulator']['properties']['regulator-max-microvolt']==[1960000]
  assert c['upstream_regulator']['properties']['regulator-name']==['mbuck10'] and c['upstream_regulator']['properties']['regulator-always-on']
  assert c['pins']['reset-gpios']['line_name']=='GPIO_105' and c['pins']['reset-gpios']['flags']==1
  assert c['pins']['irq-gpio']['line_name']=='GPIO_046' and c['irq_cells']==[14,8]
  assert c['irq_parent']==c['pins']['irq-gpio']['controller']
  assert not c['service_write_commands']
  if c['sample'].startswith('os4-'):
   assert c['inspected_init_files'] and c['init_matches']
   for name in c['inspected_init_files']:assert name in r['sources']
   assert [x['text'] for x in c['init_matches'] if x['text'].startswith('write ')]==['write /sys/class/leds/vibrator/trigger "transient"']
  else:assert not c['inspected_init_files'] and c['stock_service_rc'] is None
 assert 'supply VP not found, using dummy regulator' in r['field_VP_warning']
 index=json.loads((ROOT/'simulation-report.json').read_text());check,=[c for c in index['checks'] if c['name']=='six-profile-haptics-power-topology']
 assert check['count']==6 and check['evidence_sha256']==sha(path)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert sha(Path(index['image']))==index['image_sha256']
 out=dict(status='PASS',scope=__doc__,profiles=6,evidence_sha256=sha(path),production_change=False,image_sha256=index['image_sha256'],
  documents={n:sha(ROOT/n) for n in ['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/HAPTICS-ADAPTATION.md']},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/haptics-power-topology-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:6 stock power/GPIO topologies; no electrical enable or motor claim')
if __name__=='__main__':main()
