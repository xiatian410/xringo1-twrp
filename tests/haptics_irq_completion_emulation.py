#!/usr/bin/env python3
"""Execute original OS4 registered mailbox IRQ and vibration/completion state.

Probe/init and stock DSP metadata execute, followed by the exact registered
mailbox handler. An explicit mutable synthetic ring is supplied via regmap;
only its read-pointer ACK changes the ring fixture. This is not controller RAM
or DSP execution. Kernel mutex/input/PM/IRQ/completion/sysfs are fixture services.
No interrupt controller, concurrent kernel, real timing or motor is executed.
Unknown services and instruction/time exhaustion fail.
"""
import json
from pathlib import Path
import struct
import subprocess
from haptics_probe_selftest_emulation import SelfTest, ROOT, DEPS, CTX, sha, table, bin_writes, inventory
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

BASE=0x2807500
QUEUE=0x28073fc

class IRQ(SelfTest):
 def __init__(self,*args):
  self.locked=False;self.lock_ops=[];self.notifications=[];self.completed=[]
  self.ring=None;self.ring_reads=[];self.acks=[];self.ring_read_error=0;self.ack_error=0
  self.force_unlocked=False
  super().__init__(*args)
 def on_code(self,u,ad,z,d):
  n=self.hooks.get(ad);a=[self.arg(i) for i in range(7)] if n else []
  if n in ['mutex_lock','mutex_unlock','mutex_is_locked']:
   assert a[0]==CTX+0x18
   self.lock_ops.append([n,self.locked])
   if n=='mutex_lock':assert not self.locked;self.locked=True;r=0
   elif n=='mutex_unlock':assert self.locked;self.locked=False;r=0
   else:r=int(self.locked and not self.force_unlocked)
  elif n=='regmap_bulk_read':
   assert a[0]==0x4070000 and a[1]==QUEUE and a[3]==4 and self.ring is not None
   self.ring_reads.append(self.ring[:]);r=self.ring_read_error
   if not r:u.mem_write(a[2],struct.pack('<IIII',*self.ring))
  elif n=='regmap_write' and a[1]==0x2807408:
   assert self.ring is not None
   self.acks.append(dict(address=a[1],value=a[2],result=self.ack_error));r=self.ack_error
   if not r:self.ring[3]=a[2]
  elif n=='sysfs_notify':self.notifications.append([a[0],self.string(a[2])]);r=0
  elif n in ['complete','complete_all']:self.completed.append([n,a[0]]);r=0
  else:return super().on_code(u,ad,z,d)
  self.calls.append(n);u.reg_write(UC_ARM64_REG_X0,r&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))

 def supply(self,events,read_slot=0):
  assert 0<=read_slot<4 and len(events)<4
  self.ring=[BASE,4,BASE+4*((read_slot+len(events))%4),BASE+4*read_slot]
  self.hardware[QUEUE+16]=0
  for i,event in enumerate(events):self.hardware[BASE+4*((read_slot+i)%4)]=event

 def dispatch(self):
  registered=[s for s in self.irq_services if s['name']=='devm_request_threaded_irq' and s['args'][3]==self.symbols['cs40l26_handle_mbox_buffer']]
  assert len(registered)==1 and registered[0]['args'][1]==123
  return self.run('cs40l26_handle_mbox_buffer',registered[0]['args'][1],registered[0]['args'][6])

def exercise(path,blobs,properties):
 expected=inventory(blobs['cs40l26.wmfw'])['writes'][:];rows=table(blobs['cs40l26.wmfw'])[1]
 for n in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:expected+=bin_writes(blobs[n],rows)
 cases=[]
 for label in ['empty','done','gpio-trigger','gpio-complete','start-gated','start-accepted','start-done-wrap',
               'done-saturates','stop-completion','unknown','bulk-read-error','pending-command',
               'message-read-error','ACK-write-error','state-lock-missing']:
  m=IRQ(path,blobs,properties);assert m.run('cs40l26_probe',CTX)==0
  assert m.raw==expected and len(m.raw)==68 and not m.removed and m.threads==27
  m.dsp=m.u64(CTX+0x50)
  coeff=[r for r in m.records() if r['name'] in ['QUEUE_BASE','QUEUE_LEN','QUEUE_WT','QUEUE_RD']]
  assert {r['name']:r['register'] for r in coeff}=={'QUEUE_BASE':QUEUE,'QUEUE_LEN':QUEUE+4,'QUEUE_WT':QUEUE+8,'QUEUE_RD':QUEUE+12}
  m.notifications.clear();m.completed.clear();m.lock_ops.clear()
  m.put32(CTX+0x200,0 if label in ['start-gated','start-accepted','start-done-wrap','done-saturates','empty','unknown','bulk-read-error','pending-command','message-read-error','ACK-write-error'] else 1)
  m.put32(CTX+0x1d0,int(m.u32(CTX+0x200)>0))
  m.uc.mem_write(CTX+0x1d4,bytes([int(label in ['start-accepted','start-done-wrap'])]))
  events=[] if label=='empty' else [0x01000011] if label=='gpio-trigger' else [0x01000001] if label=='gpio-complete' else [0x01000010] if label.startswith('start-') else [0x01000012] if label=='stop-completion' else [0x12345678] if label=='unknown' else [0x01000000]
  if label=='start-done-wrap':events=[0x01000010,0x01000000]
  m.supply(events,3 if label=='start-done-wrap' else 0)
  if label=='bulk-read-error':m.ring_read_error=-5
  if label=='pending-command':m.hardware[QUEUE+16]=1
  if label=='message-read-error':m.read_errors[BASE]=-5
  if label=='ACK-write-error':m.ack_error=-5
  if label=='state-lock-missing':m.force_unlocked=True
  rc=m.dispatch()
  print(label,rc,'count',m.u32(CTX+0x200),'state',m.u32(CTX+0x1d0),'acks',m.acks,'complete',m.completed,flush=True)
  assert rc==1 and not m.locked and m.lock_ops[0][0]=='mutex_lock' and m.lock_ops[-1][0]=='mutex_unlock'
  assert m.u32(CTX+0x200)==(2 if label=='gpio-trigger' else 1 if label in ['start-accepted','state-lock-missing','stop-completion'] else 0)
  assert m.u32(CTX+0x1d0)==int(label in ['gpio-trigger','start-accepted','state-lock-missing','stop-completion'])
  assert m.completed==([['complete_all',CTX+0x228]] if label in ['done','done-saturates','start-done-wrap','state-lock-missing'] else [['complete',CTX+0x208]] if label=='stop-completion' else [])
  assert len(m.acks)==(0 if label in ['empty','bulk-read-error','pending-command','message-read-error'] else 2 if label=='start-done-wrap' else 1)
  if m.acks:
   assert m.acks[-1]['result']==(-5 if label=='ACK-write-error' else 0)
   assert m.ring[3]==(BASE if label=='ACK-write-error' else m.ring[2])
  if label=='start-done-wrap':assert [a['value'] for a in m.acks]==[BASE,BASE+4]
  assert len(m.notifications)==(2 if label=='start-done-wrap' else 1 if label in ['done','done-saturates','gpio-trigger','gpio-complete','start-accepted'] else 0)
  cases.append(dict(case=label,status='PASS',result=rc,wave_coefficients=coeff,ring=m.ring,
   ring_reads=m.ring_reads,ack_writes=m.acks,lock_ops=m.lock_ops,completions=m.completed,
   notifications=m.notifications,event_count=m.u32(CTX+0x200),vibe_state=m.u32(CTX+0x1d0),
   raw_writes=m.raw,messages=m.messages))
 return cases


def main():
 dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[];drivers={}
 for field in ['sources','libfdt_sources']:
  for name,expected in dt[field].items():
   p=Path(name) if Path(name).is_absolute() else ROOT/name
   assert sha(p)==expected;sources[str(p)]=expected
 upstream=ROOT/'logs/upstream-linux-v6.18-workqueue.h';sources[str(upstream.relative_to(ROOT))]=sha(upstream)
 tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
 for sample in ['os4-current','os4-stable']:
  base=ROOT/'firmware/samples'/sample/'analysis';path=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
  drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
  node=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43'];assert node['active']
  files=sorted((base/'odm/firmware').glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files};sources.update({str(p.relative_to(ROOT)):sha(p) for p in files})
  disasm=ROOT/'logs'/f'{sample}-haptics-irq-completion-core.disasm'
  disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=cs40l26_handle_mbox_buffer,cs40l26_vibe_state_update,cs40l26_request_irq',str(path)]));sources[str(disasm.relative_to(ROOT))]=sha(disasm)
  cases.extend(dict(sample=sample,**c) for c in exercise(path,blobs,node['properties']))
 tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_probe_selftest_emulation.py','haptics_wave_irq_emulation.py','haptics_runtime_config_emulation.py','haptics_postboost_emulation.py','haptics_probe_upload_emulation.py','haptics_config_emulation.py','haptics_coefficients_emulation.py','haptics_upload_emulation.py','haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
 deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
 (ROOT/'logs/haptics-irq-completion-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
 print('PASS',len(cases),'cases',flush=True)

if __name__=='__main__':main()
