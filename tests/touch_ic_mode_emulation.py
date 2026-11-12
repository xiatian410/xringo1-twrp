#!/usr/bin/env python3
"""Execute original OS4 resume dispatch and IC mode-2 command generation.

Original notifier/workers cross the existing typed host bridge. Original
syna_set_ic_mode replaces its former success stub; command 0xc7 response,
managed allocation, IRQ, reset, no-gesture and all controller responses remain
explicit fixtures. Synthetic ISR coordinates do not prove controller mode or
physical touch. No kernel scheduling/concurrency or current root cause claimed.
"""
import json
from pathlib import Path
import subprocess
from touch_notifier_emulation import BridgeDisplay, Notify, Capture, CTX, CORE, HW, ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

class IC(BridgeDisplay):
    def __init__(self,path):
        super().__init__(path)
        del self.hooks[self.symbols['syna_set_ic_mode']]
        self.ic_commands=[];self.ic_result=0;self.ic_alloc_failure=False
        self.watch_ic=False

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if address==self.symbols['syna_set_ic_mode']:
            self.ic_modes.append([self.arg(0),self.arg(1)])
            self.watch_ic=True
        if name=='fixture_send_command' and self.arg(1)==0xc7:
            a=[self.arg(i) for i in range(7)]
            assert a[0]==CORE and a[3:5]==[3,3] and a[6]==0
            payload=bytes(uc.mem_read(a[2],a[3])).hex()
            assert payload=='310a00'
            self.ic_commands.append(dict(command=0xc7,payload=payload,result=self.ic_result))
            uc.mem_write(a[5],b'\1');result=self.ic_result
        elif name=='devm_kmalloc' and self.watch_ic and self.ic_alloc_failure:
            assert self.arg(1)==3;result=0
        else:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(wrapper,syna,properties,children):
    capture=Capture(syna,properties,children);capture.run('syna_xiaomi_touch_probe',CTX)
    cases=[]
    for label in ['normal','command-error','allocation-error','managed-missing','IRQ-off','inactive','bootloader']:
        s=IC(syna)
        if label=='command-error':s.ic_result=-110
        if label=='allocation-error':s.ic_alloc_failure=True
        if label=='managed-missing':s.managed=0
        if label=='IRQ-off':s.flag(HW+0x6c,0)
        if label=='inactive':s.put32(CTX+0x450,0)
        if label=='bootloader':s.flag(CORE+1,11)
        rc=s.run('syna_set_ic_mode',2,0)
        # The dispatch caller discards x0; the function has no uniform error
        # return contract. Do not interpret its residual register as success.
        assert s.ic_modes==[[2,0]]
        assert s.ic_commands==([dict(command=199,payload='310a00',result=-110 if label=='command-error' else 0)]
                              if label in ['normal','command-error'] else [])
        print(label,rc,s.ic_commands,flush=True)
        cases.append(dict(case='direct-'+label,status='PASS',residual_x0=rc,commands=s.ic_commands,events=[]))
    for label in ['normal','command-error','allocation-error','config-error']:
        s=IC(syna);m=Notify(wrapper,capture.panel_bytes,s);assert m.panel()==0
        m.notify(1);m.drain()
        if label=='command-error':s.ic_result=-110
        if label=='allocation-error':s.ic_alloc_failure=True
        if label=='config-error':s.config_command_error=-110
        m.notify(2);m.drain()
        expected=-110 if label=='config-error' else 0
        assert m.bridge==[[0,0],[1,expected]]
        assert m.suspended()==0 and s.ic_modes==[[2,0]]
        assert bool(s.ic_commands)==(label not in ['allocation-error'])
        if s.ic_commands:
            assert s.ic_commands==[dict(command=199,payload='310a00',result=-110 if label=='command-error' else 0)]
        delivered=s.emit()
        assert delivered==(label!='config-error')
        count=len(s.ic_commands);m.notify(2);m.drain();assert len(s.ic_commands)==count
        cases.append(dict(case='notifier-'+label,status='PASS',result=expected,bridge=m.bridge,
            commands=s.ic_commands,ic_modes=s.ic_modes,wrapper_suspended=m.suspended(),
            active=s.u32(CTX+0x450),config_length=s.u32(CORE+0x18c),events=s.events,
            repeated_on_skips_callback=True))
    return cases


def main():
    dtpath=ROOT/'logs/touch-devicetree-audit.json';dt=json.loads(dtpath.read_text())
    sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[];drivers={}
    for field in ['sources','tests','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for record in dt['cases']:
        sample=record['sample'];base=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules'
        wrapper=base/'xiaomi_touch_dijun.ko';syna=base/'synaptics_tcm2.ko'
        for kind,p in [('wrapper',wrapper),('synaptics',syna)]:drivers[sample+'-'+kind]=dict(path=str(p.relative_to(ROOT)),sha256=sha(p))
        disasm=ROOT/'logs'/f'{sample}-touch-ic-mode-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=syna_set_ic_mode,syna_tcm_resume_suspend',str(syna)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        props={k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children={n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        cases.extend(dict(sample=sample,**c) for c in exercise(wrapper,syna,props,children))
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['touch_notifier_emulation.py','touch_wrapper_emulation.py','touch_display_resume_emulation.py','touch_irq_emulation.py','touch_panel_emulation.py','touch_transport_emulation.py','touch_spi_emulation.py','touch_configuration_emulation.py','touch_startup_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-ic-mode-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)

if __name__=='__main__':main()
