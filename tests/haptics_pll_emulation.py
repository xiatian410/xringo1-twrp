#!/usr/bin/env python3
"""Execute original Cirrus PLL programming and OS4 chip identification.

Register reads/updates use explicit synthetic values and failures; no I2C or
physical PLL state is simulated. Joined probe cases execute original pre-PLL
setup then stop at real register failures/unknown-chip rejection. Remove remains
an explicit fixture. Firmware/DSP boot, IRQ and motor output remain excluded.
"""
import json
from pathlib import Path
import subprocess

from haptics_probe_emulation import Probe
from haptics_lifecycle_emulation import CTX
from haptics_driver_emulation import ROOT, DEPS, sha, MASK
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30


class Registers(Probe):
    def __init__(self,path,properties):
        super().__init__(path,properties)
        del self.hooks[self.symbols['cs40l26_set_pll_loop']]
        del self.results['cs40l26_set_pll_loop']
        self.update_results=[];self.updates=[];self.reads_hw=[]
        self.hardware={0:0x40a270,4:0xb2};self.read_failures={}
        self.put64(CTX+8,0x40b0000)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(7)]
        if name=='regmap_update_bits_base':
            assert args[0]==0x40b0000
            self.updates.append(dict(register=args[1],mask=args[2],value=args[3]))
            result=self.update_results.pop(0) if self.update_results else 0
        elif name=='regmap_read':
            assert args[0]==0x40b0000 and args[1] in self.hardware,('unknown read',args)
            result=self.read_failures.get(args[1],0)
            if not result:self.put32(args[2],self.hardware[args[1]])
            self.reads_hw.append(dict(register=args[1],value=self.hardware[args[1]],result=result))
        else:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path,properties):
    cases=[]
    def passed(label,m,rc):cases.append(dict(case=label,status='PASS',result=rc,
        updates=m.updates,reads=m.reads_hw,remove_calls=m.removed))
    for mode in [0,1,2]:
        m=Registers(path,properties);rc=m.run('cs40l26_set_pll_loop',CTX,mode)
        assert rc==(0 if mode<2 else -22)
        assert m.updates==([dict(register=0x2c04,mask=0x800,value=mode<<11)] if mode<2 else [])
        passed(f'PLL-mode-{mode}',m,rc)
    for failures in [1,2,3,4,5]:
        m=Registers(path,properties);m.update_results=[-5]*failures+[0]
        rc=m.run('cs40l26_set_pll_loop',CTX,1)
        assert rc==(-110 if failures==5 else 0)
        assert len(m.updates)==min(failures+1,5)
        passed(f'PLL-{failures}-failed-updates',m,rc)
    m=Registers(path,properties);m.update_results=[-5]*5
    rc=m.run('cs40l26_probe',CTX)
    assert rc==-110 and len(m.updates)==5 and m.removed==[CTX] and not m.registered
    passed('joined-probe-PLL-retry-exhaustion',m,rc)
    if not m.modern:return cases
    for device,revision in [(0x40a260,0xa1),(0x40a260,0xb0),(0x40a270,0xa1),
                            (0x40a270,0xb0),(0x40a270,0xb1),(0x40a270,0xb2),
                            (0x40a270,0xb3),(0,0)]:
        m=Registers(path,properties);m.hardware={0:device,4:revision}
        rc=m.run('cs40l26_part_num_resolve',CTX)
        valid=(device,revision) not in [(0x40a270,0xb3),(0,0)]
        assert rc==(0 if valid else -22),(device,revision,rc)
        assert len(m.reads_hw)==2
        if valid:
            assert bytes(m.uc.mem_read(CTX+0x10,4))==bytes([device&255,(device>>8)&255,(device>>16)&255,revision])
            assert m.u64(CTX+0x1af8) and m.u64(CTX+0x1b00)
        else:assert not m.u64(CTX+0x1af8) and not m.u64(CTX+0x1b00)
        passed(f'chip-{device:x}-{revision:x}',m,rc)
    for reg in [0,4]:
        m=Registers(path,properties);m.read_failures={reg:-5}
        rc=m.run('cs40l26_part_num_resolve',CTX)
        assert rc==-5 and len(m.reads_hw)==(1 if reg==0 else 2)
        passed(f'chip-read-error-{reg}',m,rc)
    for label in ['chip-ID-read-fails','chip-revision-read-fails','unknown-chip']:
        m=Registers(path,properties)
        if label=='chip-ID-read-fails':m.read_failures={0:-5}
        if label=='chip-revision-read-fails':m.read_failures={4:-5}
        if label=='unknown-chip':m.hardware={0:0,4:0}
        rc=m.run('cs40l26_probe',CTX)
        assert rc==(-22 if label=='unknown-chip' else -5)
        assert len(m.updates)==1 and m.removed==[CTX] and not m.registered
        passed('joined-probe-'+label,m,rc)
    return cases


def main():
    evidence=ROOT/'logs/haptics-probe-emulation.json';prior=json.loads(evidence.read_text())
    dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text())
    sources={str(evidence):sha(evidence),str(dtpath):sha(dtpath)}
    for record in [prior,dt]:
        for field in ['sources','libfdt_sources']:
            for name,expected in record.get(field,{}).items():
                p=Path(name) if Path(name).is_absolute() else ROOT/name
                assert sha(p)==expected;sources[str(p)]=expected
    cases=[];drivers={}
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for sample,driver in sorted(prior['drivers'].items()):
        path=ROOT/driver['path'];assert sha(path)==driver['sha256'];drivers[sample]=driver
        merged=next(c for c in dt['cases'] if c['sample']==sample and c['case']=='overlay-5')
        properties=merged['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
        names=['cs40l26_set_pll_loop','cs40l26_probe']
        if sample.startswith('os4-'):names.append('cs40l26_part_num_resolve')
        disasm=ROOT/'logs'/f'{sample}-haptics-pll-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols='+','.join(names),str(path)]))
        sources[str(disasm)]=sha(disasm)
        results=exercise(path,properties)
        for case in results:case['sample']=sample;cases.append(case)
        print('PASS',sample,len(results),'PLL/chip cases',flush=True)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/name for name in ['haptics_probe_emulation.py',
        'haptics_lifecycle_emulation.py','haptics_driver_emulation.py']]
    tests.extend([ROOT/'scripts/firmware_facts.py',ROOT/'scripts/audit_haptics_devicetree.py'])
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-pll-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p):sha(p) for p in tests},
        emulator_files={str(p):sha(p) for p in dependencies}),indent=2)+'\n')


if __name__=='__main__':main()
