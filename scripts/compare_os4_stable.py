#!/usr/bin/env python3
"""Compare verified OS4 samples and bind stable-profile evidence; static checks only."""
import hashlib,json
from pathlib import Path
from firmware_facts import ROOT,SAMPLES,haptics_module
from compare_firmware import modules,crc_delta
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 names=['os4-current','os4-stable'];facts={n:json.loads((SAMPLES/n/'analysis/facts.json').read_text()) for n in names}
 old,new=[facts[n] for n in names];a,b=modules(old),modules(new);common=a.keys()&b.keys()
 conflicts={n:crc_delta(a[n]['facts']['imports'],b[n]['facts']['imports']) for n in sorted(common)};conflicts={n:v for n,v in conflicts.items() if v}
 categories={}
 for group,predicate in {
  'crypto':lambda p:p.startswith(('vendor/bin/tee-supplicant','vendor/bin/hw/android.hardware.security.keymint','vendor/bin/hw/android.hardware.gatekeeper','vendor/mitee/ta/')),
  'touch_haptic_firmware':lambda p:p.startswith(('vendor/firmware/','odm/firmware/')) and (Path(p).name.startswith('cs40l26') or 'synaptics' in p or 'syna_thp' in p),
  'fstab':lambda p:'fstab' in p,
  'security_init_vintf':lambda p:p.startswith('vendor/etc/') and any(t in p for t in ['mitee','keymint','gatekeeper']),
 }.items():
  paths={p for f in [old,new] for p in f['files'] if predicate(p)}
  categories[group]=dict(unchanged=[],changed=[],added=[],removed=[])
  for p in sorted(paths):
   if p not in old['files']:kind='added'
   elif p not in new['files']:kind='removed'
   else:kind='unchanged' if old['files'][p]['sha256']==new['files'][p]['sha256'] else 'changed'
   categories[group][kind].append(p)
 crypto=json.loads((ROOT/'docs/crypto-compatibility.json').read_text())['profiles']
 assert all(crypto[n]['status']=='S1 dependency/symbol checks passed' for n in names)
 profile=ROOT/'dtsrc/O1_asic_dual/profiles/os4-stable'
 for name in ['profile.json','selection.conf','selection-sources.json','module-sources.json','modules.plan','runtime-files.list','crypto.prop']:assert (profile/name).is_file()
 def asset_delta(group):
  x,y=[crypto[n][group] for n in names];return {k:dict(old=x.get(k,{}).get('sha256'),new=y.get(k,{}).get('sha256')) for k in sorted(x.keys()|y.keys()) if x.get(k,{}).get('sha256')!=y.get(k,{}).get('sha256')}
 sources=[SAMPLES/n/'inventory.json' for n in names]+[SAMPLES/n/'analysis/facts.json' for n in names]+[SAMPLES/n/'analysis/system-resources.json' for n in names]+[ROOT/'docs/crypto-compatibility.json']+list(profile.iterdir())
 report=dict(status='PASS',grade='S0/S1',scope='Verified partition metadata, parsed module imports and matched userspace symbol closure. Not kernel load or hardware decryption.',kernels={n:facts[n]['headers']['boot']['kernel_release'] for n in names},recovery_headers_equal=old['headers']['recovery']['header_without_ramdisk_size_sha256']==new['headers']['recovery']['header_without_ramdisk_size_sha256'],common_module_count=len(common),changed_module_bytes=[n for n in sorted(common) if set(a[n]['hashes'])!=set(b[n]['hashes'])],conflicting_module_import_crcs=conflicts,changed_import_sets=[n for n in sorted(common) if a[n]['facts']['imports'].keys()!=b[n]['facts']['imports'].keys()],categories=categories,crypto_identity={n:crypto[n]['proposed_crypto_identity'] for n in names},changed_crypto_assets=asset_delta('assets'),changed_private_dsos=asset_delta('private_dsos'),haptics_module={n:haptics_module(facts[n])[0] for n in names},sources={str(p):sha(p) for p in sources if p.is_file()},test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'scripts/firmware_facts.py',ROOT/'scripts/compare_firmware.py']})
 assert report['recovery_headers_equal'],'Recovery format conflict: keep outside unified candidate'
 out=ROOT/'logs/os4-stable-comparison.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('PASS: compared OS4 samples;',len(report['changed_module_bytes']),'changed module bytes;',len(conflicts),'module import CRC conflicts;',len(report['changed_crypto_assets']),'changed security assets;',len(report['changed_private_dsos']),'changed private DSOs')
if __name__=='__main__':main()
