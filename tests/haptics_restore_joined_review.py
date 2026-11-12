#!/usr/bin/env python3
"""Join original OS4 service restore to original post-probe A1/B2 sysfs stores.

Two ARM64 spaces meet at an explicit fprintf/sysfs callback bridge. Formatting,
hex parsing, filesystem, input number and kernel PM/register operations remain
fixtures. Calibration values are synthetic examples, never device calibration.
Stock firmware/probe/parser/store and later production SINE execute in one
module context. Writes do not update hardware or execute the DSP/motor.
"""
import inspect,json
from pathlib import Path
from haptics_calibration_restore_emulation import restore,PERSIST
from haptics_a1_joined_review import Joined,runtime,ROOT,CTX,sha,DEPS
from haptics_driver_emulation import MASK,UC_ARM64_REG_X0,UC_ARM64_REG_PC,UC_ARM64_REG_X30

class Restored(Joined):
 def __init__(self,*args):
  self.restoring=False;self.store_error_address=None;self.store_pm_error=0;self.restore_writes=[];self.restore_pm=[]
  super().__init__(*args)
 def on_code(self,u,ad,z,d):
  n=self.hooks.get(ad)
  if not self.restoring:return super().on_code(u,ad,z,d)
  if n=='kstrtouint':
   assert self.arg(1)==16
   value=int(self.string(self.arg(0)).strip(),16);assert 0<=value<=0xffffffff
   self.put32(self.arg(2),value);r=0
  elif n in ['cs40l26_pm_enter','cs40l26_pm_exit']:
   r=self.store_pm_error if n.endswith('enter') else 0;self.restore_pm.append(dict(name=n,result=r))
  elif n=='regmap_write':
   r=-5 if self.arg(1)==self.store_error_address else 0
   self.restore_writes.append(dict(address=self.arg(1),value=self.arg(2),result=r))
  else:return super().on_code(u,ad,z,d)
  self.calls.append(n);u.reg_write(UC_ARM64_REG_X0,r&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))
 def store(self,path,text):
  key=Path(path).name;assert key in ['redc_stored','f0_stored','q_stored']
  dev=0x40f0000;buf=dev+0x1000;self.put64(dev+0x98,CTX);self.uc.mem_write(buf,text.encode()+b'\0')
  return self.run(key+'_store',dev,0,buf,len(text))

def main():
 priorpath=ROOT/'logs/haptics-A1-joined-review.json';prior=json.loads(priorpath.read_text())
 dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());sources={str(p.relative_to(ROOT)):sha(p) for p in [priorpath,dtpath]}
 cases=[]
 for sample in ['os4-current','os4-stable']:
  base=ROOT/'firmware/samples'/sample/'analysis';module=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko';service=base/'odm/bin/hw/vendor.xring.hardware.vibratorfeature.service';disasm=ROOT/'logs'/f'{sample}-vibrator-service.disasm'
  files=sorted((base/'odm/firmware').glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files}
  for p in files+[module,service,disasm]:sources[str(p.relative_to(ROOT))]=sha(p)
  props=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
  for label in ['A1-valid','B2-q-rejected','A1-f0-out-of-range','A1-q-write-error','A1-PM-error','A1-missing-files','A1-valid-then-production']:
   m=Restored(module,blobs,props,'B2' if label.startswith('B2') else 'A1');assert m.run('cs40l26_probe',CTX)==0
   values={PERSIST+'vib_cal_'+k:v+'\n' for k,v in [('z','28000'),('f0','208000'),('q','a000')]}
   if label=='A1-f0-out-of-range':values[PERSIST+'vib_cal_f0']='1\n'
   if label=='A1-missing-files':values={}
   m.restoring=True
   previous_hooks={m.symbols[n]:m.hooks.get(m.symbols[n]) for n in ['cs40l26_pm_enter','cs40l26_pm_exit']}
   for n in ['cs40l26_pm_enter','cs40l26_pm_exit']:m.intercept(n)
   if label=='A1-q-write-error':m.store_error_address=0x2802150
   if label=='A1-PM-error':m.store_pm_error=-5
   restored=restore(service,disasm.read_text(),values,write_callback=m.store)
   results=[w['driver_store_result'] for w in restored['writes']]
   expected=[] if label=='A1-missing-files' else [-5,-5,-5] if label=='A1-PM-error' else [6,-22,5] if label=='A1-f0-out-of-range' else [6,7,-1] if label=='B2-q-rejected' else [6,7,-5] if label=='A1-q-write-error' else [6,7,5]
   assert results==expected,(label,results)
   addresses=[w['address'] for w in m.restore_writes]
   assert addresses==([] if label in ['A1-missing-files','A1-PM-error'] else [0x280212c,0x2802128] if label=='B2-q-rejected' else [0x280212c,0x2802150] if label=='A1-f0-out-of-range' else [0x280212c,0x2802128,0x2802150]),(label,m.restore_writes)
   assert restored['readiness_flag']=='00'
   m.restoring=False
   for ad,name in previous_hooks.items():
    if name is None:m.hooks.pop(ad,None)
    else:m.hooks[ad]=name
   rt=runtime(m,bytes.fromhex(prior['production_effect']),True) if label=='A1-valid-then-production' else None
   cases.append(dict(sample=sample,case=label,status='PASS',service=restored,driver_writes=m.restore_writes,driver_pm=m.restore_pm,production=rt))
   print(sample,label,results,flush=True)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))}
 for cls in Restored.mro():
  if cls is object:continue
  p=Path(inspect.getfile(cls)).resolve();tests[str(p.relative_to(ROOT))]=sha(p)
 for n in ['haptics_calibration_restore_emulation.py','haptics_service_request_emulation.py','haptics_coefficients_emulation.py']:
  p=ROOT/'tests'/n;tests[str(p.relative_to(ROOT))]=sha(p)
 for group in ['sources','tests']:
  for n,h in prior[group].items():
   p=Path(n) if Path(n).is_absolute() else ROOT/n;assert sha(p)==h,n
   (sources if group=='sources' else tests)[n]=h
 report=dict(status='PASS',scope=__doc__,cases=cases,sources=sources,tests=tests,emulator_files=prior['emulator_files'])
 (ROOT/'logs/haptics-restore-joined-review.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS',len(cases),'joined restore cases; synthetic calibration, no motor result')
if __name__=='__main__':main()
