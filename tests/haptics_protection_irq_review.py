#!/usr/bin/env python3
"""Execute original OS4 protection IRQ handlers with explicit regmap fixtures.

This is not hardware IRQ delivery or electrical protection simulation. Reads
supply one fixed register, writes record requests without changing readback.
Log-only brownout notifications must not be called software gain restoration.
"""
import json
from pathlib import Path
import subprocess
from haptics_driver_emulation import Module,ROOT,DEPS,MASK,sha,UC_ARM64_REG_X0,UC_ARM64_REG_PC,UC_ARM64_REG_X30

CTX=0x4000000
class Protection(Module):
    def __init__(self,path):
        super().__init__(path)
        self.put64(CTX,0x4060000);self.put64(CTX+8,0x4070000)
        self.reads=[];self.writes=[];self.read_error=0;self.write_failure=0
        self.initial=0xa5a5001e
        self.logs=[]
    def on_code(self,u,address,size,data):
        name=self.hooks.get(address)
        if name=='regmap_read':
            assert self.arg(0)==0x4070000 and self.arg(1)==0x2034
            result=self.read_error
            if not result:self.put32(self.arg(2),self.initial)
            self.reads.append(dict(address=self.arg(1),value=None if result else self.initial,result=result))
        elif name=='regmap_write':
            assert self.arg(0)==0x4070000 and self.arg(1)==0x2034
            result=-5 if len(self.writes)+1==self.write_failure else 0
            self.writes.append(dict(address=self.arg(1),value=self.arg(2),result=result))
        elif name in ['_dev_err','_dev_printk']:
            self.logs.append(self.string(self.arg(1 if name=='_dev_err' else 2)))
            result=0
        else:return super().on_code(u,address,size,data)
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0,result&MASK)
        u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))

def main():
    cases=[];sources={}
    handlers={'cs40l26_bst_ovp_err':3,'cs40l26_bst_uv_err':4,'cs40l26_bst_short':2,'cs40l26_amp_short':1}
    for sample in ['os4-current','os4-stable']:
        path=ROOT/f'firmware/samples/{sample}/analysis/vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        assert sha(path)=='969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        sources[str(path.relative_to(ROOT))]=sha(path)
        for handler,bit in handlers.items():
            for label in ['success','read-error','write1-error','write2-error','write3-error']:
                m=Protection(path)
                if label=='read-error':m.read_error=-5
                if label.startswith('write'):m.write_failure=int(label[5])
                result=m.run(handler,123,CTX)
                assert result==int(label=='success')
                values=[m.initial&~(1<<bit),m.initial|(1<<bit),m.initial&~(1<<bit)]
                expected=[] if m.read_error else values[:m.write_failure or None]
                assert [w['value'] for w in m.writes]==expected
                assert len(m.reads)==1 and m.reads[0]['result']==m.read_error
                assert all(w['result']==(-5 if i+1==m.write_failure else 0) for i,w in enumerate(m.writes))
                cases.append(dict(sample=sample,handler=handler,case=label,status='PASS',
                                  result=result,error_release_bit=bit,initial_register_fixture=m.initial,
                                  reads=m.reads,writes=m.writes,logs=m.logs))
        for handler,text in [('cs40l26_vbbr_flag','VBST voltage has dropped below brownout threshold'),
                             ('cs40l26_vbst_att_clr','Cleared attenuation caused by VBST brownout')]:
            m=Protection(path);result=m.run(handler,123,CTX)
            assert result==1 and not m.reads and not m.writes
            assert len(m.logs)==1 and text in m.logs[0]
            assert m.calls==(['_dev_err'] if handler.endswith('flag') else ['_dev_printk'])
            cases.append(dict(sample=sample,handler=handler,case='log-only',status='PASS',
                              result=result,reads=m.reads,writes=m.writes,logs=m.logs))
        disasm=ROOT/'logs'/(sample+'-haptics-protection-irq.disasm')
        names=list(handlers)+['cs40l26_error_release','cs40l26_vbbr_flag','cs40l26_vbst_att_clr']
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump',
            '-dr','--disassemble-symbols='+','.join(names),str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
    tests=[Path(__file__).resolve(),ROOT/'tests/haptics_driver_emulation.py',ROOT/'scripts/firmware_facts.py',ROOT/'tests/haptics-emulator-dependencies.json']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    report=dict(status='PASS',scope=__doc__,cases=cases,sources=sources,
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps})
    (ROOT/'logs/haptics-protection-irq-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:',len(cases),'original IRQ handler cases; brownout notifications log only; no electrical conclusion')
if __name__=='__main__':main()
