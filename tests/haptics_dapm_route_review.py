#!/usr/bin/env python3
"""Decode original OS4 DAPM topology and execute PCM widget events.

ELF relocations, original coefficient parser/get_reg and cs40l26_asp_rx execute.
Widget/component/device pointers, DAPM event scheduling, SVC readback, regmap
updates and mailbox ACKs are explicit fixtures. No ALSA dispatcher, audio PCM,
DSP or motor executes. PCM routing is not proof of an FF output prerequisite.
"""
import json
from pathlib import Path
import subprocess

from haptics_calibration_coefficients_emulation import Calibration, CTX, DEV, ROOT, DEPS
from haptics_driver_emulation import MASK, sha, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30


class PCM(Calibration):
    def __init__(self, path, blob):
        super().__init__(path, blob)
        self.updates=[]
        self.mailbox=[]
        self.update_failure=0
        self.mailbox_error=0
        self.component=0x4081000
        self.codec=0x4082000
        self.widget=0x4083000
        self.put64(self.widget+0x28,0x4084000)
        self.put64(self.component+0x10,DEV)
        self.put64(DEV+0x98,self.codec)
        self.put64(self.codec,CTX)
        self.put32(CTX+0x1c4,0x4013c)
        self.flags=next(r['register'] for r in self.records()
                        if r['algorithm']==0x4013c and r['name']=='FLAGS')
        self.hardware[self.flags]=0
        self.intercept('cs40l26_mailbox_write')

    def on_code(self,u,address,size,data):
        name=self.hooks.get(address)
        if name=='snd_soc_dapm_to_component':
            assert self.arg(0)==0x4084000
            result=self.component
        elif name=='regmap_update_bits_base':
            assert self.arg(0)==0x4070000
            result=-5 if len(self.updates)+1==self.update_failure else 0
            self.updates.append(dict(address=self.arg(1),mask=self.arg(2),value=self.arg(3),result=result))
        elif name=='cs40l26_mailbox_write':
            assert self.arg(0)==CTX
            result=self.mailbox_error
            self.mailbox.append(dict(value=self.arg(1),result=result))
        else:
            return super().on_code(u,address,size,data)
        self.calls.append(name)
        u.reg_write(UC_ARM64_REG_X0,result&MASK)
        u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))


def topology(m):
    """Pinned ELF data layouts, checked against all names and callback pointers."""
    symbols={s.name:s for s in m.symtab.iter_symbols() if s.name}
    assert symbols['cs40l26_dapm_routes']['st_size']==960
    assert symbols['cs40l26_dapm_widgets']['st_size']==2560
    routes=[]
    base=m.symbols['cs40l26_dapm_routes']
    for index in range(10):
        p=base+index*96
        routes.append([m.string(m.u64(p+offset)) if m.u64(p+offset) else None for offset in [0,8,16]])
        assert bytes(m.uc.mem_read(p+24,72))==bytes(72)
    expected=[['ASP Playback',None,'ASP Params'],['ASP Playback',None,'ASP PLL'],
              ['ASPRX1',None,'ASP Playback'],['ASPRX2',None,'ASP Playback'],
              ['PCM',None,'ASPRX1'],['PCM',None,'ASPRX2'],['A2H',None,'PCM'],
              ['Haptics Source','PCM','PCM'],['Haptics Source','A2H','A2H'],
              ['OUT',None,'Haptics Source']]
    assert routes==expected
    names=['ASP Params','ASP PLL','ASPRX1','ASPRX2','PCM','A2H','Haptics Source','OUT']
    callbacks=['cs40l26_asp_params','cs40l26_clk_en',None,None,'cs40l26_asp_rx','cs40l26_dsp_tx',None,None]
    widgets=[]
    base=m.symbols['cs40l26_dapm_widgets']
    for index,(name,callback) in enumerate(zip(names,callbacks)):
        p=base+index*320
        assert m.string(m.u64(p+8))==name
        assert m.u64(p+0x78)==(m.symbols[callback] if callback else 0)
        widgets.append(dict(name=name,event_callback=callback))
    texts=m.symbols['cs40l26_out_mux_texts']
    enum=[m.string(m.u64(texts+8*i)) for i in range(3)]
    assert enum==['Off','PCM','A2H']
    control=m.symbols['cs40l26_out_mux']
    assert m.u64(control+0x38)==m.externals['snd_soc_dapm_put_enum_double']
    assert m.u64(control+0x30)==m.externals['snd_soc_dapm_get_enum_double']
    assert m.u64(control+0x48)==m.symbols['cs40l26_out_mux_enum']
    assert m.u32(m.symbols['cs40l26_out_mux_enum'])==0xffffffff
    return dict(routes=routes,widgets=widgets,source_values=enum,
                setter='snd_soc_dapm_put_enum_double',register=0xffffffff)


def main():
    cases=[];sources={};topologies={}
    labels=['A1-up','A1-down','B2-up-SVC0','B2-up-SVC1','B2-down-restore-SVC',
            'B2-down-keep-SVC','up-first-register-error','up-second-register-error',
            'down-mailbox-error','invalid-event']
    for sample in ['os4-current','os4-stable']:
        base=ROOT/'firmware/samples'/sample/'analysis'
        driver=base/'vendor_dlkm/lib/modules/xring_audio_hw_third.ko'
        firmware=base/'odm/firmware/cs40l26.wmfw'
        assert sha(driver)=='969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6'
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in [driver,firmware]})
        for label in labels:
            m=PCM(driver,firmware.read_bytes())
            if sample not in topologies:topologies[sample]=topology(m)
            revision=0xa1 if label.startswith('A1') else 0xb2
            m.uc.mem_write(CTX+0x13,bytes([revision]))
            event=4 if 'down' in label else 2
            if label=='invalid-event':event=1
            svc=int(label=='B2-up-SVC1')
            m.hardware[m.flags]=svc
            if label=='B2-down-restore-SVC':m.uc.mem_write(m.codec+0x59,b'\1')
            if label=='up-first-register-error':m.update_failure=1
            if label=='up-second-register-error':m.update_failure=2
            if label=='down-mailbox-error':m.mailbox_error=-5
            read_start=len(m.reads)
            result=m.run('cs40l26_asp_rx',m.widget,0,event)
            assert result==(-5 if 'error' in label else -22 if label=='invalid-event' else 0),(label,result)
            changes=[(u['address'],u['mask'],u['value']) for u in m.updates]
            up=[(0x4c00,0x7f,50),(0x4c20,0x7f,50),(0x4800,0x30003,0x30003)]
            down=[(0x4800,0x30003,0),(0x4c20,0x7f,24)]
            expected=(up+([(m.flags,5,5)] if revision==0xb2 and svc==0 else []) if event==2 else
                      ([(m.flags,5,0)] if label=='B2-down-restore-SVC' else [])+down if event==4 else [])
            if m.update_failure:expected=expected[:m.update_failure]
            if label=='down-mailbox-error':expected=[]
            assert changes==expected,(label,changes,expected)
            assert [c['value'] for c in m.mailbox]==([0x3000003] if event==4 else [])
            cases.append(dict(sample=sample,case=label,status='PASS',revision=revision,event=event,
                              result=result,updates=m.updates,mailbox=m.mailbox,
                              reads=m.reads[read_start:],SVC_fixture=svc,
                              SVC_restore_flag=bytes(m.uc.mem_read(m.codec+0x59,1))[0]))
        disasm=ROOT/'logs'/(sample+'-haptics-dapm-core.disasm')
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr',
            '--disassemble-symbols=cs40l26_asp_rx,cs40l26_asp_start',str(driver)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/name for name in [
        'haptics_calibration_coefficients_emulation.py','haptics_firmware_emulation.py',
        'haptics_coefficients_emulation.py','haptics_driver_emulation.py','haptics_upload_emulation.py',
        'haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    report=dict(status='PASS',scope=__doc__,topologies=topologies,cases=cases,sources=sources,
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps})
    (ROOT/'logs/haptics-dapm-route-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS:',len(cases),'original PCM event cases; Source1=PCM, no FF or motor conclusion')

if __name__=='__main__':main()
