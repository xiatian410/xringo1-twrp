#!/usr/bin/env python3
"""Join field A1 stock probe/config/selftest and production FF/IRQ/erase.

Original ARM64 and stock DT/firmware execute in one context. Registers, PM,
mailbox acknowledgements, all-FF sequences, kernel services, ordered scheduling
and a single-waiter completion model remain explicit fixtures. No DSP, real
kernel input/IRQ, calibration readback or motor output is executed. A1 PM state
reads explicitly change from pre-shutdown 3/1 to post-load 3/3; writes do not
synthesize that change. Unknown reads/imports and finite budget exhaustion fail.
"""
import inspect
import json
from pathlib import Path
import struct
import tempfile
from haptics_active_erase_emulation import Active, INPUT, EFFECT, EFFECTS
from haptics_probe_selftest_emulation import ROOT, CTX, sha, table, bin_writes, inventory
from haptics_driver_emulation import capture, SOURCE, DEPS

ROMS = {
 'A1': [0x2800370,0x2800378,0x2800350,0x2800fa8,0x2806fc4,0x2802154,0x28003e8,0x60d],
 'B2': [0x2801f98,0x2801fa0,0x2801f78,0x2806af8,0x2806fb0,0x2802f50,0x2802018,0x60d],
}

class Joined(Active):
 def __init__(self,path,blobs,properties,revision):
  self.resolved_rom=None;self.sequence_requests=[]
  super().__init__(path,blobs,properties)
  self.revision_name=revision
  self.hardware.update({0:0x40a260 if revision=='A1' else 0x40a270,4:0xa1 if revision=='A1' else 0xb2})
  self.rom=ROMS[revision][:]
  self.hardware.update({self.rom[0]:1,self.rom[1]+8:2,self.rom[3]:2,self.rom[2]+24:1})
  self.states=[3,1,3,3] if revision=='A1' else [3,1]
 def on_code(self,u,address,size,data):
  if hasattr(self,'revision_name'):
   if address==self.symbols['cs40l26_fw_upload']:
    p=self.u64(CTX+0x1af8);self.resolved_rom=[self.u32(p+4*i) for i in range(8)]
    assert self.resolved_rom==ROMS[self.revision_name]
   if address==self.symbols['cs40l26_wseq_write']:
    self.sequence_requests.append(dict(address=self.arg(1),value=self.arg(2)))
  return super().on_code(u,address,size,data)

def runtime(m,effect,done):
 m.runtime=True;m.completed.clear();m.notifications.clear();m.selftest_mail.clear();m.selftest_writes.clear()
 m.put32(CTX+0x200,0);m.put32(CTX+0x1d0,0)
 assert m.uc.mem_read(CTX+0x1d4,1)==b'\1'
 m.uc.mem_write(EFFECT,effect);m.uc.mem_write(EFFECTS+7*48,effect)
 assert m.runtime_call('cs40l26_upload_effect',INPUT,EFFECT,0)==0
 assert m.runtime_call('cs40l26_playback_effect',INPUT,7,1)==0
 m.flush_until(CTX+0xc0)
 m.supply([0x01000010]);assert m.runtime_call('cs40l26_handle_mbox_buffer',123,CTX)==1
 m.irq_at_wait=[0x01000000] if done else []
 rc=m.runtime_call('cs40l26_erase_effect',INPUT,7)
 assert rc==(0 if done else -62)
 assert len(m.wait_records)==1 and m.wait_records[0]['timeout']==580
 assert m.wait_records[0]['result']==int(done)
 assert (m.u64(CTX+0x58)==CTX+0x58)==done
 assert m.selftest_mail==[dict(command=0x1800081,result=0)]
 expected=[(0x280701c,20),(0x2807014,125),(0x2807018,64),(0x2802134,80),(0x28059f0,0)]
 assert [(w['address'],w['value']) for w in m.selftest_writes]==expected
 return dict(erase_result=rc,waits=m.wait_records,writes=m.selftest_writes,mailbox=m.selftest_mail,
             completions=m.completed,acks=m.acks,effect_list_empty=done)

def main():
 dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());sources={str(dtpath.relative_to(ROOT)):sha(dtpath)}
 for group in ['sources','libfdt_sources']:
  for name,digest in dt[group].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name
   assert sha(p)==digest;sources[str(p)]=digest
 cases=[]
 with tempfile.TemporaryDirectory(prefix='dijun-a1-joined-') as temp:
  effect=next(e for n,e,event in capture(Path(temp)) if n==80)
  assert int.from_bytes(effect[2:4],'little')==7
  for sample in ['os4-current','os4-stable']:
   base=ROOT/'firmware/samples'/sample/'analysis';path=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
   files=sorted((base/'odm/firmware').glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files}
   for p in files+[path]:sources[str(p.relative_to(ROOT))]=sha(p)
   props=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
   expected=inventory(blobs['cs40l26.wmfw'])['writes'][:];rows=table(blobs['cs40l26.wmfw'])[1]
   for name in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:expected+=bin_writes(blobs[name],rows)
   for label in ['A1-probe-selftest','B2-control','A1-stale-PM-state','A1-errata-sequence-error','A1-Q-write-error','A1-firmware-write-error','A1-production-done','A1-production-missing-done']:
    revision='B2' if label=='B2-control' else 'A1';m=Joined(path,blobs,props,revision)
    if label=='A1-stale-PM-state':m.states=[3,1]
    if label=='A1-errata-sequence-error':m.bulk_failure=3
    if label=='A1-Q-write-error':m.failed_write_address=0x2802150
    if label=='A1-firmware-write-error':m.raw_failure=1
    rc=m.run('cs40l26_probe',CTX)
    failed=label in ['A1-stale-PM-state','A1-errata-sequence-error','A1-Q-write-error','A1-firmware-write-error']
    assert rc==(-22 if label=='A1-stale-PM-state' else -5 if failed else 0),(sample,label,rc,m.messages)
    assert m.resolved_rom==ROMS[revision] and bytes(m.uc.mem_read(CTX+0x13,1))==bytes([0xa1 if revision=='A1' else 0xb2])
    assert m.removed==([CTX] if failed else [])
    if label!='A1-firmware-write-error':assert m.raw==expected and len(m.raw)==68
    if failed:assert 'cs40l26_input_init' not in m.entries and not m.workers
    else:
     assert m.threads==m.virqs==27 and len(m.bulk)==25
     assert m.workers==['cs40l26_upload_worker','cs40l26_vibe_start_worker','cs40l26_erase_worker']
     assert not m.queue and m.u64(CTX+0x58)==CTX+0x58
     assert len(m.effects)==1 and int.from_bytes(bytes.fromhex(m.effects[0])[10:12],'little')==100
     assert m.selftest_mail==[dict(command=0x1800081,result=0)]
     assert dict(address=0x2802128,value=130<<14) in m.writes
     assert (dict(address=0x2802150,value=0) in m.writes)==(revision=='A1')
     assert (0x3000009 in m.mail)==(revision=='B2')
    errata=[list(struct.unpack('<III',m.uc.mem_read(m.symbols['cs40l26_a1_errata']+i*12,12))) for i in range(5)]
    if revision=='A1' and not failed:
     assert dict(address=errata[0][0],value=errata[0][1]) in m.sequence_requests
     # This stock-DT branch uses only the first table row; later boost
     # configuration also writes key/clip registers, with different values.
     assert not any(dict(address=a,value=v) in m.sequence_requests for a,v,delay in errata[3:4])
    rt=runtime(m,effect,label=='A1-production-done') if label.startswith('A1-production-') else None
    cases.append(dict(sample=sample,case=label,status='PASS',revision=revision,probe_result=rc,resolved_rom=m.resolved_rom,
      runtime=rt,errata_table=errata,writes=m.writes,sequence_requests=m.sequence_requests,reads=m.reads,
      raw_write_count=len(m.raw),bulk_write_count=len(m.bulk),workers=m.workers,entries=m.entries,remove_calls=m.removed,
      fw_loaded=int.from_bytes(m.uc.mem_read(CTX+0x1ca,1),'little'),messages=m.messages))
    print(sample,label,rc,flush=True)
 for p in [SOURCE,SOURCE.with_suffix('.h'),ROOT/'tests/haptics_driver_capture.cpp']:sources[str(p)]=sha(p)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))}
 for cls in Joined.mro():
  if cls is object:continue
  p=Path(inspect.getfile(cls)).resolve();tests[str(p.relative_to(ROOT))]=sha(p)
 for name in ['haptics_coefficients_emulation.py','haptics-emulator-dependencies.json']:
  p=ROOT/'tests'/name;tests[str(p.relative_to(ROOT))]=sha(p)
 p=ROOT/'scripts/firmware_facts.py';tests[str(p.relative_to(ROOT))]=sha(p)
 field=ROOT/'imgs/built/1/touch-dmesg-before.txt';identity=[l for l in field.read_bytes().decode('utf-16').splitlines() if 'Cirrus Logic CS40L26 ID:' in l]
 assert len(identity)==1 and '0x40A260, Revision: 0xA1' in identity[0];sources[str(field.relative_to(ROOT))]=sha(field)
 report=dict(status='PASS',scope=__doc__,count=len(cases),cases=cases,production_effect=effect.hex(),field_identity=identity[0],
  sources=sources,tests=tests,emulator_files={str(p.relative_to(ROOT)):sha(p) for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name)})
 (ROOT/'logs/haptics-A1-joined-review.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS',len(cases),'joined cases; motor unverified')
if __name__=='__main__':main()
