#!/usr/bin/env python3
"""Execute upstream6.18 FF erase/flush C joined to original OS4 A1 callbacks.

The upstream input core is a versioned reference, not recovered vendor kernel
code. Its functions compile unchanged with explicit no-op lock/log fixtures.
ctypes callbacks bridge host C into original relocated ARM64 driver code. Stock
probe/firmware execute; PM/register/mailbox/kernel/workqueue/completion fixtures
remain. No actual input core/kernel/DSP/IRQ/motor or concurrent lock executes.
"""
import ctypes
import inspect
import json
from pathlib import Path
import subprocess
import tempfile
from backup_session_test import method
from haptics_a1_joined_review import Joined, ROOT, CTX, sha, SOURCE, DEPS
from haptics_active_erase_emulation import INPUT, EFFECT, EFFECTS
from haptics_driver_emulation import MASK,UC_ARM64_REG_X0,UC_ARM64_REG_PC,UC_ARM64_REG_X30

class Stop(Joined):
 def __init__(self,*args):
  self.stop_mail_error=0;self.stop_pm_error=0
  super().__init__(*args)
 def on_code(self,u,ad,z,d):
  n=self.hooks.get(ad)
  if self.runtime and n=='queue_work_on' and self.arg(2)==CTX+0xe0:
   assert self.arg(1)==0x4080000 and CTX+0xe0 not in self.queue
   self.queue.append(CTX+0xe0);r=1
  elif self.runtime and n=='__pm_runtime_resume' and self.current_worker=='cs40l26_vibe_stop_worker' and self.stop_pm_error:
   r=self.stop_pm_error
  elif self.runtime and n=='cs40l26_mailbox_write' and self.current_worker=='cs40l26_vibe_stop_worker':
   assert self.arg(1)==0x5000000
   self.selftest_mail.append(dict(command=self.arg(1),result=self.stop_mail_error));r=self.stop_mail_error
  else:return super().on_code(u,ad,z,d)
  self.calls.append(n);u.reg_write(UC_ARM64_REG_X0,r&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))
 def flush_until(self,target,depth=0):
  assert target in self.queue
  for _ in range(4):
   w=self.queue.pop(0);worker={CTX+0x120:'cs40l26_upload_worker',CTX+0xc0:'cs40l26_vibe_start_worker',CTX+0xe0:'cs40l26_vibe_stop_worker',CTX+0x140:'cs40l26_erase_worker'}[w]
   prev=self.current_worker;self.current_worker=worker;self.runtime_workers.append(worker)
   self.execute(worker,(w,),depth);self.current_worker=prev
   if w==target:return
  raise AssertionError('queue budget')

HARNESS=r'''
#include <errno.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
struct file {int tag;};struct input_dev;
typedef int (*play_fn)(struct input_dev*,int,int);
typedef int (*erase_fn)(struct input_dev*,int);
struct ff_device {int max_effects;struct file *effect_owners[8];play_fn playback;erase_fn erase;int mutex;};
struct input_dev {struct ff_device *ff;unsigned long evbit[1];int event_lock;int dev;};
#define EV_FF 21
#define test_bit(bit,ptr) ((*(ptr)>>(bit))&1)
#define guard(type) void *unused_lock __attribute__((unused)) =
#define scoped_guard(...) for(bool once=true;once;once=false)
#define dev_dbg(...) ((void)0)
// FUNCTIONS
static struct file owner={1},other={2};
static struct ff_device ff;static struct input_dev dev;
void setup(play_fn play,erase_fn erase){ff=(struct ff_device){.max_effects=8,.playback=play,.erase=erase};dev=(struct input_dev){.ff=&ff,.evbit={1UL<<EV_FF}};ff.effect_owners[7]=&owner;}
int invoke(int mode){return mode==2?input_ff_flush(&dev,&owner):input_ff_erase(&dev,7,mode?&other:&owner);}
int owned(void){return ff.effect_owners[7]==&owner;}
'''

def main():
 core=ROOT/'logs/upstream-linux-v6.18-ff-core.c';evdev=ROOT/'logs/upstream-linux-v6.18-evdev.c'
 text=core.read_text();code='\n'.join(method(text,s) for s in ['static int check_effect_access(', 'static int erase_effect(', 'int input_ff_erase(', 'int input_ff_flush('])
 assert 'return input_ff_erase(dev, (int)(unsigned long) p, file);' in evdev.read_text()
 dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());priorpath=ROOT/'logs/haptics-A1-joined-review.json';prior=json.loads(priorpath.read_text())
 effect=bytes.fromhex(prior['production_effect']);cases=[];sources={str(p.relative_to(ROOT)):sha(p) for p in [core,evdev,dtpath,priorpath]}
 for name,digest in prior['sources'].items():
  p=Path(name) if Path(name).is_absolute() else ROOT/name
  assert sha(p)==digest;sources[name]=digest
 with tempfile.TemporaryDirectory(prefix='dijun-ff-core-') as temp:
  temp=Path(temp);(temp/'core.c').write_text(HARNESS.replace('// FUNCTIONS',code));libpath=temp/'core.so'
  subprocess.run(['gcc','-std=gnu11','-O1','-g','-shared','-fPIC','-Wall','-Wextra','-Werror',str(temp/'core.c'),'-o',str(libpath)],check=True)
  lib=ctypes.CDLL(str(libpath));PLAY=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_int);ERASE=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_int)
  lib.setup.argtypes=[PLAY,ERASE];lib.invoke.argtypes=[ctypes.c_int];lib.invoke.restype=lib.owned.restype=ctypes.c_int
  for sample in ['os4-current','os4-stable']:
   base=ROOT/'firmware/samples'/sample/'analysis';path=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko';blobs={p.name:p.read_bytes() for p in (base/'odm/firmware').glob('cs40l26*')}
   props=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
   for label in ['natural-done','stop-then-done','stop-completion-only','stop-no-completion','stop-mail-error-done','stop-PM-error-done','close-stop-only','wrong-owner']:
    m=Stop(path,blobs,props,'A1');assert m.run('cs40l26_probe',CTX)==0
    m.runtime=True;m.selftest_mail.clear();m.selftest_writes.clear();m.put32(CTX+0x200,0);m.put32(CTX+0x1d0,0)
    m.uc.mem_write(EFFECT,effect);m.uc.mem_write(EFFECTS+7*48,effect)
    assert m.runtime_call('cs40l26_upload_effect',INPUT,EFFECT,0)==0
    assert m.runtime_call('cs40l26_playback_effect',INPUT,7,1)==0;m.flush_until(CTX+0xc0)
    m.supply([0x01000010]);assert m.runtime_call('cs40l26_handle_mbox_buffer',123,CTX)==1
    if label=='natural-done':
     m.supply([0x01000000]);assert m.runtime_call('cs40l26_handle_mbox_buffer',123,CTX)==1
    m.irq_at_wait=([0x01000012,0x01000000] if label=='stop-then-done' else [0x01000012] if label in ['stop-completion-only','close-stop-only'] else [0x01000000] if label in ['stop-mail-error-done','stop-PM-error-done'] else [])
    if label=='stop-mail-error-done':m.stop_mail_error=-5
    if label=='stop-PM-error-done':m.stop_pm_error=-5
    callbacks=[];errors=[]
    def playback(dev,eid,value):
     try:
      assert eid==7 and value==0;callbacks.append('playback0');return m.runtime_call('cs40l26_playback_effect',INPUT,eid,value)
     except BaseException as e:errors.append(e);return -999
    def erase(dev,eid):
     try:
      assert eid==7;callbacks.append('erase');return m.runtime_call('cs40l26_erase_effect',INPUT,eid)
     except BaseException as e:errors.append(e);return -999
    playcb,erasecb=PLAY(playback),ERASE(erase);lib.setup(playcb,erasecb)
    rc=lib.invoke(2 if label=='close-stop-only' else 1 if label=='wrong-owner' else 0)
    if errors:raise errors[0]
    good=label in ['natural-done','stop-then-done','stop-mail-error-done','stop-PM-error-done']
    assert callbacks==([] if label=='wrong-owner' else ['playback0','erase'])
    assert rc==(-13 if label=='wrong-owner' else 0 if good or label=='close-stop-only' else -62),(label,rc)
    assert lib.owned()==int(not good)
    assert (m.u64(CTX+0x58)==CTX+0x58)==good
    if label!='wrong-owner':
     assert m.runtime_workers[-2:]==['cs40l26_vibe_stop_worker','cs40l26_erase_worker']
     assert len(m.wait_records)==int(label!='natural-done')
     if m.wait_records:assert m.wait_records[0]['timeout']==580 and m.wait_records[0]['result']==int(good)
    if label in ['stop-completion-only','close-stop-only']:assert m.u32(CTX+0x208)==1 and m.u32(CTX+0x228)==0
    cases.append(dict(sample=sample,case=label,status='PASS',core_result=rc,owner_retained=bool(lib.owned()),callbacks=callbacks,workers=m.runtime_workers,mailbox=m.selftest_mail,waits=m.wait_records,completions=m.completed,effect_list_empty=good,messages=m.messages))
    print(sample,label,rc,'owner',lib.owned(),flush=True)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__)), 'tests/backup_session_test.py':sha(ROOT/'tests/backup_session_test.py')}
 for cls in Stop.mro():
  if cls is object:continue
  p=Path(inspect.getfile(cls)).resolve();tests[str(p.relative_to(ROOT))]=sha(p)
 tests.update(prior['tests'])
 r=dict(status='PASS',scope=__doc__,cases=cases,sources=sources,tests=tests,emulator_files=prior['emulator_files'],upstream_urls={'core':'https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/input/ff-core.c','evdev':'https://raw.githubusercontent.com/torvalds/linux/v6.18/drivers/input/evdev.c'})
 (ROOT/'logs/haptics-ff-core-review.json').write_text(json.dumps(r,indent=2)+'\n');print('PASS',len(cases),'cases; reference kernel, no motor claim')
if __name__=='__main__':main()
