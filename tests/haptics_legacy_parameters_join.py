#!/usr/bin/env python3
"""Execute four original OS2/OS3 coefficient loaders after exact firmware parse.

Original wavetable creation, firmware metadata, file selection, parameter parser
and loader execute in one ARM64 context. Regmap algorithm rows are independently
decoded file fixtures; firmware requests/strings/allocation and raw writes are
kernel boundaries. No full probe/config/start/IRQ/DSP or motor executes.
"""
import inspect,json,subprocess
from pathlib import Path
from haptics_legacy_firmware_join import Legacy,ROOT,CTX,FW,sha,table
from haptics_firmware_emulation import IMAGE
from haptics_coefficients_emulation import bin_writes
from haptics_driver_emulation import DEPS,MASK,UC_ARM64_REG_X0,UC_ARM64_REG_PC,UC_ARM64_REG_X30

class Parameters(Legacy):
 def __init__(self,path,blob,blobs):
  super().__init__(path,blob)
  self.requests=[];self.releases=[];self.fwmap={};self.missing=set();self.warnings=[];self.parser_results=[];self.parser_return=None;self.alloc_error=False
  at=0x40b0000
  for name,raw in sorted(blobs.items()):
   self.put64(at,len(raw));self.put64(at+8,at+32);self.uc.mem_write(at+32,raw);self.fwmap[name]=at;at+=((len(raw)+4095)&~4095)+4096
  assert at<0x4100000
  for at,text in [(0x4080000,b'WAVE_XM_TABLE\0'),(0x4080100,b'WAVE_YM_TABLE\0'),(0x4080200,b'cs40l26.bin\0')]:self.uc.mem_write(at,text)
  assert self.run('cl_dsp_wavetable_create',self.dsp,0x100bd,0x4080000,0x4080100,0x4080200)==0
  self.hardware.update(table(blob)[0]);self.read_error=0;assert self.parse()==0
  self.put32(CTX+0x21c,table(blob)[1][0][0]);self.raw.clear()
 def on_code(self,u,address,size,data):
  if hasattr(self,'parser_return'):
   if self.parser_return==address:
    value=self.arg(0)&0xffffffff;self.parser_results.append(dict(file=self.requests[-1],result=value if value<0x80000000 else value-0x100000000));self.parser_return=None
   if address==self.symbols['cl_dsp_coeff_file_parse']:
    assert self.parser_return is None;self.parser_return=u.reg_read(UC_ARM64_REG_X30)
  name=self.hooks.get(address)
  if name in ['strlen','strnlen']:
   n=128 if name=='strlen' else self.arg(1);assert 0<n<=128
   result=len(bytes(u.mem_read(self.arg(0),n)).split(b'\0')[0])
  elif name=='strscpy':
   n=self.arg(2);assert 0<n<=128
   raw=bytes(u.mem_read(self.arg(1),n)).split(b'\0')[0];assert len(raw)<n
   u.mem_write(self.arg(0),raw+b'\0');result=len(raw)
  elif name=='kmalloc_trace':
   n=self.arg(2);assert 0<n<4096
   result=0 if self.alloc_error else self.alloc_cursor
   if result:self.alloc_cursor+=(n+15)&~15;assert self.alloc_cursor<0x4200000
  elif name=='request_firmware':
   n=self.string(self.arg(1));assert n in self.fwmap;self.requests.append(n)
   self.put64(self.arg(0),0 if n in self.missing else self.fwmap[n]);result=-2 if n in self.missing else 0
  elif name=='release_firmware':self.releases.append(self.arg(0));result=0
  elif name=='_dev_warn':self.warnings.append(self.string(self.arg(1)));result=0
  else:return super().on_code(u,address,size,data)
  self.calls.append(name);u.reg_write(UC_ARM64_REG_X0,result&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))

def main():
 cases=[];sources={}
 for sample in ['os2-initial','os2-final','os3-initial','os3-final']:
  base=ROOT/'firmware/samples'/sample/'analysis';driver=base/'vendor_dlkm/lib/modules/xring_smartpa.ko';files=sorted((base/'odm/firmware').glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files}
  for p in files+[driver]:sources[str(p.relative_to(ROOT))]=sha(p)
  for fw in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
   rows=table(blobs[fw])[1]
   expected_names=['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin']+(['cs40l26-a2h.bin','cs40l26-dbc.bin'] if fw=='cs40l26.wmfw' else ['cs40l26-calib.bin'])
   for label in ['stock-parameters','main-missing','main-header-invalid','main-first-write-error','svc-first-write-error','loader-allocation-error']:
    m=Parameters(driver,blobs[fw],blobs)
    if label=='main-missing':m.missing={'cs40l26.bin'}
    if label=='main-header-invalid':m.uc.mem_write(m.u64(m.fwmap['cs40l26.bin']+8),b'FAIL')
    if label=='main-first-write-error':m.raw_failure=1
    if label=='svc-first-write-error':m.raw_failure=len(bin_writes(blobs['cs40l26.bin'],rows))+1
    if label=='loader-allocation-error':m.alloc_error=True
    result=m.run('cs40l26_coeff_load',CTX,0)
    assert result==(-12 if m.alloc_error else 0),(sample,fw,label,result,m.messages,m.warnings)
    assert m.requests==([] if m.alloc_error else expected_names)
    expected=[];results=[]
    for name in m.requests:
     writes=bin_writes(blobs[name],rows)
     if name in m.missing:continue
     rc=0
     if name=='cs40l26.bin' and label=='main-header-invalid':writes=[];rc=-22
     if (name=='cs40l26.bin' and label=='main-first-write-error') or (name=='cs40l26-svc.bin' and label=='svc-first-write-error'):writes=writes[:1];rc=-5
     expected+=writes;results.append(dict(file=name,result=rc))
    assert m.raw==expected,(sample,fw,label,len(m.raw),len(expected))
    assert m.parser_results==results
    assert m.releases==[m.fwmap[n] for n in m.requests if n not in m.missing]
    cases.append(dict(sample=sample,firmware=fw,case=label,status='PASS',loader_result=result,requests=m.requests,parser_results=m.parser_results,released=m.releases,raw_writes=m.raw,warnings=m.warnings,messages=m.messages))
    print(sample,fw,label,result,len(m.raw),flush=True)
  disasm=ROOT/'logs'/f'{sample}-haptics-legacy-parameters.disasm'
  disasm.write_bytes(subprocess.check_output(['/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr','--disassemble-symbols=cl_dsp_wavetable_create,cl_dsp_coeff_file_parse,cs40l26_coeff_load',str(driver)]));sources[str(disasm.relative_to(ROOT))]=sha(disasm)
 tests={str(Path(__file__).resolve().relative_to(ROOT)):sha(Path(__file__))}
 for cls in Parameters.mro():
  if cls is object:continue
  p=Path(inspect.getfile(cls)).resolve();tests[str(p.relative_to(ROOT))]=sha(p)
 for n in ['tests/haptics_coefficients_emulation.py','tests/haptics_upload_emulation.py','tests/haptics-emulator-dependencies.json','scripts/firmware_facts.py']:tests[n]=sha(ROOT/n)
 report=dict(status='PASS',scope=__doc__,count=len(cases),cases=cases,sources=sources,tests=tests,emulator_files={str(p.relative_to(ROOT)):sha(p) for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name)})
 (ROOT/'logs/haptics-legacy-parameters-join.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'legacy parameter loader joins; no DSP/motor')
if __name__=='__main__':main()
