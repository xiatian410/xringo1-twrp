#!/usr/bin/env python3
"""Verify stock CPU sensor identity evidence without asserting runtime numbering."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 path=ROOT/'logs/thermal-topology.json';r=json.loads(path.read_text());assert r['status']=='PASS' and len(r['cases'])==6
 for group in ['sources','tests']:
  for name,h in r[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name;assert sha(p)==h,name
 samples={p.parent.name for p in (ROOT/'dtsrc/O1_asic_dual/profiles').glob('*/profile.json')};assert {c['sample'] for c in r['cases']}==samples
 for c in r['cases']:
  assert c['status']=='PASS' and c['sysfs_zone_number'] is None
  cpu=c['cpu_zone'];assert cpu['path']=='/thermal-zones/cpu-crg' and cpu['sensor_id']==0
  assert cpu['sensor_path']=='/soc/tsensor@EB008000' and cpu['sensor_status']==['okay'] and cpu['sensor_compatible']==['xring,tsensor']
  physical=[z for z in c['zones'] if z['sensor_path']==cpu['sensor_path']]
  assert c['physical_sensor_count']==len(physical)==22 and {z['sensor_id'] for z in physical}==set(range(22))
  assert len(c['zones'])==38
  assert {'xr_soc_tm_probe','xr_virt_tm_probe','__xr_thermal_get_temp'}<=set(c['inspected_symbols'])
  assert any('devm_thermal_of_zone_register' in call for call in c['registration_calls'])
 index=json.loads((ROOT/'simulation-report.json').read_text());check,=[c for c in index['checks'] if c['name']=='six-profile-CPU-thermal-sensor-identity']
 assert check['count']==6 and check['evidence_sha256']==sha(path)
 assert index['status']=='in_progress' and len(index['not_yet_completed'])==12
 assert sha(Path(index['image']))==index['image_sha256']
 docs=['ADAPTATION-GOALS.md','MAINTENANCE.md','simulation-report.json','simulation-report.md','docs/STATUS-ADAPTATION.md']
 out=dict(status='PASS',scope=__doc__,profiles=6,evidence_sha256=sha(path),production_change=False,image_sha256=index['image_sha256'],documents={n:sha(ROOT/n) for n in docs},audit_script_sha256=sha(Path(__file__)))
 (ROOT/'logs/thermal-topology-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS:6 stock CPU thermal identities; sysfs numbering/GUI/hardware unverified')
if __name__=='__main__':main()
