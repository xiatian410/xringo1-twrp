#!/usr/bin/env python3
"""Execute stock Xiaomi panel setup with original parsed DT configuration.

Flash contents, firmware-completion waits, panel/notifier/TUI registration and
debugfs are explicit fixtures. Original name selection, parameter population
and report-mode switching execute. This does not run the wrapper's registration
implementation, the flash protocol, kernel scheduling or physical touch.
"""
import json
from pathlib import Path
import subprocess

from touch_transport_emulation import Transport
from touch_startup_emulation import CTX, CORE
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

FLASH=0x4070000


class Panel(Transport):
    def __init__(self,path,properties,children):
        super().__init__(path,properties,children)
        self.put64(CTX+0x300,self.data+0x1d8)
        del self.hooks[self.symbols['syna_xiaomi_touch_probe']]
        self.intercept('syna_tcm_read_flash_area')
        self.flash_error=0;self.panel_error=0;self.notifier_error=0
        self.valid_after=0
        self.flash_reads=0;self.panels=[];self.notifiers=[];self.sleeps=[]
        # Synthetic lockdown matches no cfg vendor except the stock zero
        # fallback. It is not read from a physical panel.
        self.uc.mem_write(FLASH,b'\0'*128)
        self.uc.mem_write(FLASH+120,bytes([0x53,0x42,0x32,0x30,0x4f,2,0x72,0]))

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(6)]
        if name=='syna_tcm_read_flash_area':
            assert args[:2]==[CORE,2]
            self.flash_reads+=1
            if self.valid_after and self.flash_reads>=self.valid_after:
                uc.mem_write(FLASH+120,bytes([0x53,0x42,0x32,0x30,0x4f,2,0x72,0]))
            if not self.flash_error:self.put64(args[2],FLASH)
            result=self.flash_error
        elif name=='strlen':result=len(self.string(args[0]).encode())
        elif name=='register_touch_panel':
            assert args[1]==0
            params=args[2]
            self.panels.append(dict(width=self.u16(params),height=self.u16(params+2),
                config=self.string(params+0x15),driver=self.string(params+0x55)))
            result=self.panel_error
        elif name=='xiaomi_register_panel_notifier':
            self.notifiers.append(args[:4]);result=self.notifier_error
        elif name in ['register_tpd_tui_request','__init_swait_queue_head']:
            result=0
        elif name=='debugfs_create_dir':result=0
        elif name=='msleep':self.sleeps.append(args[0]);result=0
        else:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        self.boundaries.append(dict(name=name,args=args,result=result))
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def u16(self,where):return int.from_bytes(self.uc.mem_read(where,2),'little')


def exercise(path,properties,children):
    cases=[]
    for label in ['normal','flash-fails','empty-lockdown','empty-then-valid-lockdown','unmatched-vendor',
                  'panel-registration-fails','notifier-registration-fails',
                  'first-mode-command-fails','second-mode-command-fails',
                  'both-mode-commands-fail','firmware-wait-timeout']:
        m=Panel(path,properties,children)
        if label=='flash-fails':m.flash_error=-110
        if label in ['empty-lockdown','empty-then-valid-lockdown']:m.uc.mem_write(FLASH,b'\0'*128)
        if label=='empty-then-valid-lockdown':m.valid_after=3
        if label=='unmatched-vendor':m.uc.mem_write(FLASH+127,b'\x7f')
        if label=='panel-registration-fails':m.panel_error=-12
        if label=='notifier-registration-fails':m.notifier_error=-517
        if label=='first-mode-command-fails':m.report_results=[-110,0]
        if label=='second-mode-command-fails':m.report_results=[0,-110]
        if label=='both-mode-commands-fail':m.report_results=[-110,-110]
        if label=='firmware-wait-timeout':m.put32(CORE+0x328,1)
        # The original function is void: its leftover return register is not
        # interpreted as success. Check actual registration and command effects.
        budget=False
        try:m.run('syna_xiaomi_touch_probe',CTX)
        except AssertionError as error:
            if label!='empty-lockdown' or error.args!=(('emulation budget','syna_xiaomi_touch_probe'),):raise
            budget=True
        if label=='empty-lockdown':
            assert budget and m.flash_reads>100 and not m.panels and not m.reports and not m.sleeps
            cases.append(dict(case=label,status='PASS',observed='instruction budget exhausted before registration',
                flash_reads=m.flash_reads,scope='Budget proves repeated path only; physical flash response unknown.'))
            continue
        assert len(m.panels)==len(m.notifiers)==1,(label,m.calls)
        panel=m.panels[0]
        assert (panel['width'],panel['height'])==(1440,3200)
        assert panel['config']=='dijun_syna_thp_config.ini',panel
        assert panel['driver'].startswith('synaptics:'),panel
        assert m.reports==[[CORE,0xc0,0],[CORE,0x11,1]],(label,m.reports)
        assert bytes(m.uc.mem_read(CTX+0x6ac,1))==b'\0'
        expected=0 if label=='firmware-wait-timeout' else 5 if label=='flash-fails' else 3 if label=='empty-then-valid-lockdown' else 1
        assert m.flash_reads==expected,(label,m.flash_reads)
        if label in ['flash-fails','firmware-wait-timeout']:assert m.sleeps==[1000]*5
        cases.append(dict(case=label,status='PASS',panel=panel,flash_reads=m.flash_reads,
            reports=m.reports,boundaries=m.boundaries,sleeps=m.sleeps))
    return cases


def main():
    evidence=ROOT/'logs/touch-devicetree-audit.json';dt=json.loads(evidence.read_text())
    sources={str(evidence):sha(evidence)}
    for field in ['sources','tests','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    cases=[];drivers={}
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for record in dt['cases']:
        sample=record['sample'];path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        properties={k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children={n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        disasm=ROOT/'logs'/f'{sample}-touch-panel-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=syna_xiaomi_touch_probe',str(path)]))
        sources[str(disasm)]=sha(disasm)
        results=exercise(path,properties,children)
        for case in results:case['sample']=sample;cases.append(case)
        print('PASS',sample,len(results),'panel setup cases',flush=True)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/name for name in ['touch_transport_emulation.py',
        'touch_spi_emulation.py','touch_configuration_emulation.py','touch_startup_emulation.py','haptics_driver_emulation.py']]
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-panel-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p):sha(p) for p in tests},
        emulator_files={str(p):sha(p) for p in dependencies}),indent=2)+'\n')


if __name__=='__main__':main()
