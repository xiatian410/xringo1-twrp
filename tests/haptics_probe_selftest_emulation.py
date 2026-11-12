#!/usr/bin/env python3
"""Execute original OS4 probe through built-in upload/play/erase self-test.

Stock firmware, DT and original functions execute. Kernel input/FF/MFD, IRQ
registration, runtime PM, mailbox ACK, registers and all-FF sequences are
explicit fixtures. A bounded sequential workqueue driver handles flush_work;
it is not concurrent kernel scheduling. The original ordered-workqueue flags
and max_active=1 are checked; a reversed-order model is explicitly rejected.
Probe zero only describes original control flow under those fixtures,
not working DSP, IRQ/completion, successful hardware boot or motor output.
"""
import json
from pathlib import Path
import subprocess
from haptics_wave_irq_emulation import Waves, ROOT, DEPS, CTX, sha, table, bin_writes, inventory
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30, UC_ARM64_REG_SP

class SelfTest(Waves):
 def __init__(self,*args):
  self.queue=[];self.pending_flush=None;self.workers=[];self.current_worker=None
  self.order='before';self.worker_pm_failure=None;self.worker_write_failure=None;self.start_mail_error=0
  self.workqueue_spec=[]
  self.selftest_writes=[];self.selftest_mail=[];self.effects=[];self.work_results=[];self.requests_work=[]
  super().__init__(*args)
  self.irq_chip_error=0;self.input_mode='success'
  self.watch+=['cs40l26_upload_effect','cs40l26_playback_effect','cs40l26_erase_effect','cs40l26_upload_worker','cs40l26_vibe_start_worker','cs40l26_erase_worker','cs40l26_vibe_state_update']
 def on_code(self,u,ad,z,d):
  if ad==self.symbols['cs40l26_upload_effect']:
   self.effects.append(bytes(u.mem_read(self.arg(1),48)).hex())
  name=self.hooks.get(ad);a=[self.arg(i) for i in range(7)] if name else []
  if name=='alloc_workqueue_noprof':
   assert a[1:3]==[0x20012,1]
   self.workqueue_spec.append(dict(name=self.string(a[0]),flags=a[1],max_active=a[2]));r=0x4080000
  elif name=='__pm_runtime_resume' and self.current_worker==self.worker_pm_failure and self.current_worker is not None:
   self.pm_services.append(dict(name=name,args=a[:4],result=-5));r=-5
  elif name=='regmap_write' and self.current_worker:
   self.selftest_writes.append(dict(worker=self.current_worker,address=a[1],value=a[2],result=-5 if self.worker_write_failure==a[1] else 0))
   if self.worker_write_failure!=a[1]:return super().on_code(u,ad,z,d)
   self.writes.append(dict(address=a[1],value=a[2]));r=-5
  elif name=='cs40l26_mailbox_write' and self.current_worker:
   assert self.current_worker=='cs40l26_vibe_start_worker' and a[1]==0x1800081
   self.mail.append(a[1]);self.selftest_mail.append(dict(command=a[1],result=self.start_mail_error));r=self.start_mail_error
  elif name=='devm_mfd_add_devices':
   assert a[0]==0x4060000 and a[3]==1;r=0
  elif name=='input_ff_create':
   self.put64(0x40a9000+0x78,0x40aa000)
   return super().on_code(u,ad,z,d)
  elif name=='queue_work_on':
   assert a[1]==0x4080000 and a[2] in [CTX+0x120,CTX+0xc0,CTX+0x140]
   assert a[2] not in self.queue
   self.queue.append(a[2]);self.requests_work.append(a[2]);r=1
  elif name=='flush_work':
   assert a[0] in self.queue
   self.pending_flush=a[0];r=1
  else:return super().on_code(u,ad,z,d)
  self.calls.append(name);u.reg_write(UC_ARM64_REG_X0,r&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))
  if name=='flush_work':u.emu_stop()
 def run(self,name,*args):
  if name!='cs40l26_probe':return super().run(name,*args)
  for i,v in enumerate(args):self.uc.reg_write(UC_ARM64_REG_X0+i,v&MASK)
  self.uc.reg_write(UC_ARM64_REG_SP,0x501fff0);self.uc.reg_write(UC_ARM64_REG_X30,self.return_address)
  start=self.symbols[name]
  for _ in range(3):
   self.uc.emu_start(start,self.return_address,timeout=10000000,count=1000000)
   if self.pending_flush is None:
    assert self.uc.reg_read(UC_ARM64_REG_PC)==self.return_address
    r=self.arg(0)&0xffffffff;return r if r<0x80000000 else r-0x100000000
   target=self.pending_flush;self.pending_flush=None;saved=self.uc.context_save()
   while self.queue:
    assert self.order=='before','ordered workqueue rejects reverse model'
    w=self.queue.pop(0);worker={CTX+0x120:'cs40l26_upload_worker',CTX+0xc0:'cs40l26_vibe_start_worker',CTX+0x140:'cs40l26_erase_worker'}[w]
    self.workers.append(worker);self.current_worker=worker
    self.uc.reg_write(UC_ARM64_REG_X0,w);self.uc.reg_write(UC_ARM64_REG_SP,0x500fff0);self.uc.reg_write(UC_ARM64_REG_X30,self.return_address)
    self.uc.emu_start(self.symbols[worker],self.return_address,timeout=2000000,count=100000)
    assert self.uc.reg_read(UC_ARM64_REG_PC)==self.return_address,('worker budget',worker)
    assert self.pending_flush is None
    self.work_results.append(dict(worker=worker,upload_status=self.u32(CTX+0x1f8),erase_status=self.u32(CTX+0x1fc)))
    self.current_worker=None
    if w==target:break
   else:raise AssertionError('missing target')
   self.uc.context_restore(saved);start=self.uc.reg_read(UC_ARM64_REG_PC)
  raise AssertionError('flush budget')

def exercise(path,blobs,properties):
 expected=inventory(blobs['cs40l26.wmfw'])['writes'][:];rows=table(blobs['cs40l26.wmfw'])[1]
 for n in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:expected+=bin_writes(blobs[n],rows)
 cases=[]
 for label in ['start-before-erase','reject-reverse-queue-model','upload-PM-error','start-PM-error','erase-PM-error',
               'start-duration-write-error','start-mailbox-error','upload-parameter-write-error']:
  m=SelfTest(path,blobs,properties)
  if label=='reject-reverse-queue-model':
   m.order='after'
   try:m.run('cs40l26_probe',CTX)
   except AssertionError as error:
    assert str(error)=='ordered workqueue rejects reverse model'
   else:raise AssertionError('illegal queue model accepted')
   assert not m.workers and m.queue==[CTX+0x120]
   cases.append(dict(case=label,status='PASS',model_rejected=True,workqueue_spec=m.workqueue_spec))
   continue
  if label in ['upload-PM-error','start-PM-error','erase-PM-error']:
   m.worker_pm_failure={'upload-PM-error':'cs40l26_upload_worker','start-PM-error':'cs40l26_vibe_start_worker','erase-PM-error':'cs40l26_erase_worker'}[label]
  if label=='start-duration-write-error':m.worker_write_failure=0x2802134
  if label=='upload-parameter-write-error':m.worker_write_failure=0x280701c
  if label=='start-mailbox-error':m.start_mail_error=-5
  rc=m.run('cs40l26_probe',CTX)
  print(label,rc,m.workers,'status',hex(m.u32(CTX+0x1f8)),hex(m.u32(CTX+0x1fc)),'pending',m.queue,'mail',m.selftest_mail,'writes',m.selftest_writes,flush=True)
  assert rc==0 and not m.removed and m.raw==expected and len(m.raw)==68
  assert m.released==[m.fwmap[n] for n in m.requests]
  assert m.uc.mem_read(CTX+0x16c,1)==b'\1' and m.uc.mem_read(CTX+0x1ca,1)==b'\1'
  assert m.virqs==m.threads==27 and len(m.bulk)==25
  assert len(m.effects)==1
  effect=bytes.fromhex(m.effects[0])
  assert len(effect)==48 and effect[:4]==bytes.fromhex('51000000')
  assert int.from_bytes(effect[10:12],'little')==100
  assert int.from_bytes(effect[16:18],'little')==0x5a and int.from_bytes(effect[18:20],'little')==8
  assert int.from_bytes(effect[20:22],'little')==45
  assert m.requests_work==[CTX+0x120,CTX+0xc0,CTX+0x140]
  assert m.workers==['cs40l26_upload_worker','cs40l26_vibe_start_worker','cs40l26_erase_worker']
  assert not m.queue and len(m.workqueue_spec)==1
  if label in ['upload-PM-error','erase-PM-error']:
   assert any(s['name']=='__pm_runtime_set_status' for s in m.pm_services)
  if label in ['start-before-erase','erase-PM-error','start-mailbox-error']:
   assert m.selftest_mail==[dict(command=0x1800081,result=-5 if label=='start-mailbox-error' else 0)]
  if label in ['start-PM-error','upload-PM-error','start-duration-write-error','upload-parameter-write-error']:
   assert not m.selftest_mail
  expected_writes=[dict(worker='cs40l26_upload_worker',address=a,value=v,result=0) for a,v in [(0x280701c,25),(0x2807014,125),(0x2807018,45)]]
  if label=='upload-PM-error':expected_writes=[]
  elif label=='upload-parameter-write-error':expected_writes=[dict(worker='cs40l26_upload_worker',address=0x280701c,value=25,result=-5)]
  elif label!='start-PM-error':
   expected_writes.append(dict(worker='cs40l26_vibe_start_worker',address=0x2802134,value=100,result=-5 if label=='start-duration-write-error' else 0))
   if label!='start-duration-write-error':expected_writes.append(dict(worker='cs40l26_vibe_start_worker',address=0x28059f0,value=0,result=0))
  assert m.selftest_writes==expected_writes
  assert m.u32(CTX+0x1f8)==(0xfffffffb if label=='upload-parameter-write-error' else 0)
  assert m.u32(CTX+0x1fc)==(0xffffffc3 if label in ['upload-PM-error','upload-parameter-write-error'] else 0)
  assert (m.u64(CTX+0x58)==CTX+0x58)==(label!='erase-PM-error')
  cases.append(dict(case=label,status='PASS',result=rc,fw_loaded=1,input_registered_flag=1,
    entries=m.entries,raw_writes=m.raw,workers=m.workers,work_results=m.work_results,
    work_requests=m.requests_work,pending=m.queue,workqueue_spec=m.workqueue_spec,selftest_effect=m.effects[0],selftest_writes=m.selftest_writes,
    selftest_mailbox=m.selftest_mail,mailbox=m.mail,pm_services=m.pm_services,
    upload_status=m.u32(CTX+0x1f8),erase_status=m.u32(CTX+0x1fc),
    effect_list_empty=m.u64(CTX+0x58)==CTX+0x58,remove_calls=m.removed,messages=m.messages))
 return cases


def main():
 dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[];drivers={}
 upstream=ROOT/'logs/upstream-linux-v6.18-workqueue.h'
 source=upstream.read_text();assert '__WQ_ORDERED\t\t= 1 << 17' in source and 'WQ_UNBOUND | __WQ_ORDERED | (flags), 1' in source
 sources[str(upstream.relative_to(ROOT))]=sha(upstream)
 for field in ['sources','libfdt_sources']:
  for name,expected in dt[field].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name
   assert sha(p)==expected;sources[str(p)]=expected
 tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
 for sample in ['os4-current','os4-stable']:
  base=ROOT/'firmware/samples'/sample/'analysis';path=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
  drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
  node=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43'];assert node['active']
  files=sorted((base/'odm/firmware').glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files};sources.update({str(p.relative_to(ROOT)):sha(p) for p in files})
  disasm=ROOT/'logs'/f'{sample}-haptics-probe-selftest-core.disasm'
  disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=cs40l26_probe,cs40l26_upload_effect,cs40l26_playback_effect,cs40l26_erase_effect,cs40l26_upload_worker,cs40l26_vibe_start_worker,cs40l26_erase_worker',str(path)]));sources[str(disasm.relative_to(ROOT))]=sha(disasm)
  cases.extend(dict(sample=sample,**c) for c in exercise(path,blobs,node['properties']))
 tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_wave_irq_emulation.py','haptics_runtime_config_emulation.py','haptics_postboost_emulation.py','haptics_probe_upload_emulation.py','haptics_config_emulation.py','haptics_coefficients_emulation.py','haptics_upload_emulation.py','haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
 deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
 (ROOT/'logs/haptics-probe-selftest-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
 print('PASS',len(cases),'cases',flush=True)

if __name__=='__main__':main()
