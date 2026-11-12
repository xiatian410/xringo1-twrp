#!/usr/bin/env python3
"""Join four stock OS2/OS3 DSP parsers/resolvers to original FF upload callbacks.

Exact firmware executes on relocated original ARM64. Algorithm-table reads come
from independently decoded WMFW, not a running DSP. Original coefficient lookup
is no longer intercepted. Input/PM/allocation/ordered work-flush and regmap are
explicit fixtures. No full probe, parameter loading, start/IRQ or motor result.
"""
import inspect,json,struct,subprocess,tempfile
from pathlib import Path
from haptics_firmware_emulation import Firmware,ROOT,FW,DEV,REG,inventory,sha
from haptics_lifecycle_emulation import Lifecycle,CTX
from haptics_coefficients_emulation import table
from haptics_driver_emulation import capture,DEPS,SOURCE,MASK,UC_ARM64_REG_X0,UC_ARM64_REG_PC,UC_ARM64_REG_X30,UC_ARM64_REG_SP

class Legacy(Firmware,Lifecycle):
 def __init__(self,path,blob):
  super().__init__(path,blob)
  assert not self.modern
  del self.hooks[self.symbols['cl_dsp_get_coeff']]
  self.put64(CTX,DEV);self.put64(CTX+8,REG)
  self.put64(CTX+0x58,self.dsp)
  self.write_fail=0;self.resolver_calls=0
 def on_code(self,u,address,size,data):
  if address==self.symbols['cl_dsp_get_coeff']:self.resolver_calls+=1
  name=self.hooks.get(address)
  if name in ['kvmalloc_node','__kmalloc']:
   n=self.arg(0);assert 0<n<=0x20000
   result=self.alloc_cursor;self.alloc_cursor+=(n+15)&~15;assert self.alloc_cursor<0x4200000
   self.allocations.append(dict(address=result,length=n))
  elif name=='regmap_write':
   assert self.arg(0)==REG
   result=-5 if len(self.registers)+1==self.write_fail else 0
   self.registers.append(dict(address=self.arg(1),value=self.arg(2),result=result))
  else:return super().on_code(u,address,size,data)
  self.calls.append(name);u.reg_write(UC_ARM64_REG_X0,result&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))
 def parse(self,flags=1):
  for i,v in enumerate([self.dsp,FW,flags]):self.uc.reg_write(UC_ARM64_REG_X0+i,v)
  self.uc.reg_write(UC_ARM64_REG_SP,0x501fff0);self.uc.reg_write(UC_ARM64_REG_X30,self.return_address)
  self.uc.emu_start(self.symbols['cl_dsp_firmware_parse'],self.return_address,count=1000000,timeout=10000000)
  assert self.uc.reg_read(UC_ARM64_REG_PC)==self.return_address,'parser budget exhausted'
  r=self.arg(0)&0xffffffff;return r if r<0x80000000 else r-0x100000000

def main():
 cases=[];sources={};layouts={}
 with tempfile.TemporaryDirectory(prefix='legacy-firmware-join-') as temp:
  effects=capture(Path(temp));effect=next(e for n,e,event in effects if n==80)
  for sample in ['os2-initial','os2-final','os3-initial','os3-final']:
   base=ROOT/'firmware/samples'/sample/'analysis';driver=base/'vendor_dlkm/lib/modules/xring_smartpa.ko'
   for filename in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
    path=base/'odm/firmware'/filename;blob=path.read_bytes();facts=inventory(blob);hw,rows=table(blob)
    for p in [path,driver]:sources[str(p.relative_to(ROOT))]=sha(p)
    labels=['stock-parser','parser-only','table-read-error','firmware-write-error','invalid-header']
    if filename=='cs40l26.wmfw':labels+=['production-upload','first-coefficient-write-error','second-coefficient-write-error','third-coefficient-write-error','missing-buzz-coefficient']
    for label in labels:
     m=Legacy(driver,blob);m.hardware.update(hw);m.read_error=0
     if label=='table-read-error':m.read_error=-5
     if label=='firmware-write-error':m.raw_failure=1
     if label=='invalid-header':m.uc.mem_write(m.u64(FW+8),b'FAIL')
     rc=m.parse(0 if label=='parser-only' else 1)
     expected=-5 if label in ['table-read-error','firmware-write-error'] else -22 if label=='invalid-header' else 0
     assert rc==expected,(sample,filename,label,rc,m.messages)
     raw=[] if label in ['parser-only','invalid-header'] else facts['writes'][:1] if label=='firmware-write-error' else facts['writes']
     assert m.raw==raw
     records=m.records();assert len(records)==(0 if label in ['invalid-header','firmware-write-error'] else facts['coefficients'])
     joined=None
     if label not in ['stock-parser','parser-only','table-read-error','firmware-write-error','invalid-header']:
      coeff={r['name']:r for r in records};names=['BUZZ_EFFECTS2_BUZZ_DURATION','BUZZ_EFFECTS2_BUZZ_FREQ','BUZZ_EFFECTS2_BUZZ_LEVEL']
      row,=[r for r in rows if r[0]==0x4f202]
      addresses=[0x2800000+4*(row[2]+offset) for offset in [5,3,4]]
      assert [coeff[n]['register'] for n in names]==addresses
      assert all(coeff[n]['algorithm']==0x4f202 for n in names)
      error_index={'first-coefficient-write-error':1,'second-coefficient-write-error':2,'third-coefficient-write-error':3}.get(label,0)
      m.write_fail=error_index
      if label=='missing-buzz-coefficient':
       # Mutate only the parsed name record, not module instructions or firmware.
       head=m.dsp+16;node=m.u64(head)
       while node!=head:
        if m.string(node-64+20)==names[0]:m.uc.mem_write(node-64+20,b'!');break
        node=m.u64(node)
       assert node!=head
      upload=m.upload_effect(effect)
      assert upload==(-14 if label=='missing-buzz-coefficient' else -5 if error_index else 0),(sample,label,upload,m.messages)
      writes=[dict(address=a,value=v,result=-5 if i==error_index else 0) for i,(a,v) in enumerate(zip(addresses,[20,125,64]),1)]
      expected_writes=[] if label=='missing-buzz-coefficient' else writes[:error_index or None]
      assert m.registers==expected_writes,(label,m.registers,expected_writes)
      assert m.resolver_calls==(1 if label=='missing-buzz-coefficient' else error_index or 3)
      joined=dict(result=upload,writes=m.registers,resolver_calls=m.resolver_calls,coefficient_registers=addresses,slots=m.slots(),pm_fixture_calls=m.calls.count('cs40l26_pm_enter'))
     cases.append(dict(sample=sample,firmware=filename,case=label,status='PASS',parser_result=rc,raw_writes=m.raw,coefficient_count=len(records),algorithm_rows=rows,joined=joined,messages=m.messages))
     print(sample,filename,label,rc,joined['result'] if joined else '',flush=True)
   disasm=ROOT/'logs'/f'{sample}-haptics-legacy-firmware-join.disasm'
   disasm.write_bytes(subprocess.check_output(['/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr','--disassemble-symbols=cl_dsp_create,cl_dsp_firmware_parse,cl_dsp_get_coeff,cs40l26_upload_effect,cs40l26_upload_worker',str(driver)]))
   sources[str(disasm.relative_to(ROOT))]=sha(disasm)
 for p in [SOURCE,SOURCE.with_suffix('.h'),ROOT/'tests/haptics_driver_capture.cpp']:sources[str(p)]=sha(p)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))}
 for cls in Legacy.mro():
  if cls is object:continue
  p=Path(inspect.getfile(cls)).resolve();tests[str(p.relative_to(ROOT))]=sha(p)
 for n in ['tests/haptics_coefficients_emulation.py','tests/haptics_upload_emulation.py','scripts/firmware_facts.py','tests/haptics-emulator-dependencies.json']:
  tests[n]=sha(ROOT/n)
 report=dict(status='PASS',scope=__doc__,count=len(cases),cases=cases,sources=sources,tests=tests,production_effect=effect.hex(),emulator_files={str(p.relative_to(ROOT)):sha(p) for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name)})
 (ROOT/'logs/haptics-legacy-firmware-join.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS',len(cases),'legacy parser/actual resolver/FF joins; hardware unverified')
if __name__=='__main__':main()
