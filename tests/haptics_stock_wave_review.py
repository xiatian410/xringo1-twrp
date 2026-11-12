#!/usr/bin/env python3
"""Check stock WMDR wave records against original post-probe parser and CUSTOM.

WMDR inventory is independently decoded. Original A1 probe/parser fills the
wavetable; its count is supplied at the regmap boundary (not DSP execution).
Original service FF bytes enter worker after explicit user-copy boundary; no
privileged copy, real input core/gain/stop timer, DSP or motor is executed.
"""
import inspect,json,struct,hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from haptics_a1_joined_review import Joined,ROOT,CTX,sha,DEPS
from haptics_active_erase_emulation import INPUT,EFFECTS
from haptics_service_request_emulation import service_request
from haptics_driver_emulation import MASK,UC_ARM64_REG_X0,UC_ARM64_REG_PC,UC_ARM64_REG_X30

def inventory(blob):
 assert blob[:4]==b'WMDR';pos=16;found=[]
 while pos<len(blob):
  off,kind,algo,rev,rate,n=struct.unpack_from('<HHIIII',blob,pos)
  if kind==5 and algo&0xffff==0xbd:
   assert off==0x34 and rev==0x3070000
   payload=blob[pos+20:pos+20+n];records=[]
   for i in range(254):
    h=payload[i*12:(i+1)*12];assert len(h)==12
    typ=h[3];flags=int.from_bytes(h[1:3],'big')
    if typ==255:break
    offset=int.from_bytes(h[5:8],'big');length=int.from_bytes(h[9:12],'big')
    data=payload[offset*4:(offset+length)*4];assert len(data)==length*4
    records.append(dict(type=typ,flags=flags,offset=offset,length=length,data_sha256=hashlib.sha256(data).hexdigest()))
   else:raise AssertionError('no terminator')
   found.append(dict(region_offset=pos,payload_offset=pos+20,payload_size=n,records=records,terminator_index=i))
  pos+=20+((n+3)&~3)
 assert pos==len(blob) and len(found)==1;return found[0]

class Stock(Joined):
 def on_code(self,u,ad,z,d):
  n=self.hooks.get(ad)
  if self.runtime and n=='cs40l26_mailbox_write' and self.current_worker=='cs40l26_vibe_start_worker':
   command=self.arg(1);assert command in [0x100001f,0x100002a]
   self.selftest_mail.append(dict(command=command,result=0));r=0
   self.calls.append(n);u.reg_write(UC_ARM64_REG_X0,r);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30));return
  return super().on_code(u,ad,z,d)

def main():
 dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[]
 for sample in ['os4-current','os4-stable']:
  base=ROOT/'firmware/samples'/sample/'analysis';files=sorted((base/'odm/firmware').glob('cs40l26*'));module=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko';xml=base/'odm/etc/waveform_conf.xml';service=base/'odm/bin/hw/vendor.xring.hardware.vibratorfeature.service';disasm=ROOT/'logs'/f'{sample}-vibrator-service.disasm';blobs={p.name:p.read_bytes() for p in files}
  for p in files+[module,xml,service,disasm]:sources[str(p.relative_to(ROOT))]=sha(p)
  wave=inventory(blobs['cs40l26.bin']);assert len(wave['records'])==wave['terminator_index']==43
  long_id=int(ET.fromstring(xml.read_bytes()).findtext('long_vib_id/data'));assert long_id==31
  ops,_=service_request(service,disasm.read_text(),long_id,80);effect=bytearray.fromhex(ops[1]['effect']);custom=bytes.fromhex(ops[1]['custom']);assert custom==struct.pack('<HH',0,31)
  props=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
  for label in ['stock-long31','last-wave42','outside43','empty-count','count-read-error']:
   m=Stock(module,blobs,props,'A1');assert m.run('cs40l26_probe',CTX)==0
   wt=m.u64(m.u64(CTX+0x50)+0x358);count=m.u32(wt+0x1850);assert count==43
   buffer=m.u64(wt+0x1858);actual=[]
   for i,expected in enumerate(wave['records']):
    e=wt+0x80+i*24;typ,flags,offset,length=struct.unpack('<IIII',m.uc.mem_read(e,16));p=m.u64(e+16)
    assert p-buffer==wave['payload_offset']+offset*4
    row=dict(type=typ,flags=flags,offset=offset,length=length,data_sha256=hashlib.sha256(m.uc.mem_read(p,length*4)).hexdigest());assert row==expected;actual.append(row)
   # Runtime value comes from parsed stock bytes, not old count5/32 constants.
   m.hardware[0x2802140]=0 if label=='empty-count' else count
   if label=='count-read-error':m.read_errors[0x2802140]=-5
   selected=42 if label=='last-wave42' else 43 if label=='outside43' else long_id
   request=bytearray(effect);struct.pack_into('<h',request,2,7)
   m.uc.mem_write(CTX+0x78,bytes(request));m.put64(CTX+0xb0,0x40f0000);m.put32(CTX+0xb8,2);m.uc.mem_write(0x40f0000,struct.pack('<HH',0,selected));m.uc.mem_write(EFFECTS+7*48,bytes(request))
   read_start=len(m.reads)
   m.runtime=True;m.selftest_mail.clear();m.selftest_writes.clear();m.current_worker='cs40l26_upload_worker'
   m.runtime_call('cs40l26_upload_worker',CTX+0x120);m.current_worker=None
   result=m.u32(CTX+0x1f8);result=result if result<0x80000000 else result-0x100000000
   good=label in ['stock-long31','last-wave42'];assert result==(0 if good else -22 if label=='outside43' else -61 if label=='empty-count' else -62),(label,result)
   count_reads=[r for r in m.reads[read_start:] if r['address']==0x2802140]
   assert len(count_reads)==(20 if label=='count-read-error' else 2 if label in ['stock-long31','last-wave42'] else 1),(label,count_reads)
   assert all(r['result']==(-5 if label=='count-read-error' else 0) for r in count_reads)
   if good:
    assert m.runtime_call('cs40l26_playback_effect',INPUT,7,1)==0;m.flush_until(CTX+0xc0)
    assert m.selftest_mail==[dict(command=0x1000000+selected,result=0)]
    assert [w['value'] for w in m.selftest_writes]==[0,0]
   else:assert not m.selftest_mail and not m.selftest_writes
   cases.append(dict(sample=sample,case=label,status='PASS',stock_wave_count=count,long_id=long_id,selected=selected,upload_result=result,wave_inventory=wave,parsed_records=actual,count_reads=count_reads,mailbox=m.selftest_mail,writes=m.selftest_writes))
   print(sample,label,result,flush=True)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))}
 for cls in Stock.mro():
  if cls is object:continue
  p=Path(inspect.getfile(cls)).resolve();tests[str(p.relative_to(ROOT))]=sha(p)
 for n in ['haptics_service_request_emulation.py','haptics_coefficients_emulation.py']:
  p=ROOT/'tests'/n;tests[str(p.relative_to(ROOT))]=sha(p)
 report=dict(status='PASS',scope=__doc__,cases=cases,sources=sources,tests=tests,emulator_files={str(p.relative_to(ROOT)):sha(p) for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name)})
 (ROOT/'logs/haptics-stock-wave-review.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'cases; no DSP or motor result')
if __name__=='__main__':main()
