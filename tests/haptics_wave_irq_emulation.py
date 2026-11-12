#!/usr/bin/env python3
"""Join stock OS4 probe to waveform diagnostics, IRQ setup and input allocation.

Runtime PM/HALO/logger, wave counts 5/0, mailbox ACK, all-FF sequences, regmap,
IRQ domains and kernel services are explicit fixtures, not a booted DSP/kernel.
Original stock bytes/parser/config execute; writes never change supplied reads.
Every case ends in a deliberate IRQ/input/MFD or earlier error. Kernel input
registration and FF allocation are service fixtures, not a real evdev node. No
successful full probe, real cleanup, IRQ delivery or motor output is claimed.
"""
import json
from pathlib import Path
import subprocess
from haptics_runtime_config_emulation import Runtime, ROOT, DEPS, CTX, sha, table, bin_writes, inventory
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

class Waves(Runtime):
    def __init__(self,*args):
        self.irq_services=[];self.irq_chip_error=-5;self.virq_error_at=0;self.thread_error_at=0
        self.virqs=0;self.threads=0;self.input_allocations=[];self.b2_error=0
        self.input_mode='allocation-error';self.capabilities=[];self.input_services=[]
        super().__init__(*args)
        self.hardware.update({0x2802140:5,0x2805368:0})
        self.watch+=['cs40l26_num_waves','cs40l26_num_ram_waves','cs40l26_num_owt_waves','cs40l26_request_irq']

    def on_code(self,u,address,size,data):
        name=self.hooks.get(address);a=[self.arg(i) for i in range(7)] if name else []
        if name=='_dev_info':self.messages.append(self.string(a[1]));result=0
        elif name=='cs40l26_mailbox_write' and a[1]==0x03000009:
            self.mail.append(a[1]);result=self.b2_error
        elif name=='devm_regmap_add_irq_chip':
            assert a[:5]==[0x4060000,0x4070000,0,0x2088,0xffffffff]
            assert a[6]==CTX+0x1bf8
            result=self.irq_chip_error
            if not result:self.put64(a[6],0x4090000)
        elif name=='regmap_irq_get_virq':
            self.virqs+=1;assert a[0]==0x4090000
            result=-5 if self.virqs==self.virq_error_at else 100+self.virqs
        elif name=='devm_request_threaded_irq':
            self.threads+=1
            assert a[:3]==[0x4060000,100+self.threads,0] and a[4]==0x2088 and a[6]==CTX
            result=-5 if self.threads==self.thread_error_at else 0
        elif name=='devm_input_allocate_device':
            self.input_allocations.append(a[0]);assert a[0]==0x4060000
            result=0 if self.input_mode=='allocation-error' else 0x40a8000
        elif name=='input_set_capability':
            assert a[0]==0x40a8000;self.capabilities.append(a[1:3]);result=0
        elif name=='input_ff_create':
            assert a[:2]==[0x40a8000,96]
            result=-12 if self.input_mode=='FF-error' else 0
            if not result:
                self.put64(0x40a8000+0xf8,0x40a9000)
                self.put64(0x40a8000+0xc0,1<<16)
        elif name=='input_register_device':
            assert a[0]==0x40a8000;result=-5 if self.input_mode=='register-error' else 0
        elif name=='sysfs_create_groups':
            assert a[0]==0x40a8000+0x228;result=-5 if self.input_mode=='sysfs-error' else 0
        elif name=='devm_mfd_add_devices':
            assert a[0]==0x4060000 and a[3]==1;result=-5
        else:return super().on_code(u,address,size,data)
        if name in ['devm_regmap_add_irq_chip','regmap_irq_get_virq','devm_request_threaded_irq']:
            self.irq_services.append(dict(name=name,args=a,result=result))
        if name in ['devm_input_allocate_device','input_ff_create','input_register_device','sysfs_create_groups','devm_mfd_add_devices']:
            self.input_services.append(dict(name=name,args=a,result=result))
        self.calls.append(name);u.reg_write(UC_ARM64_REG_X0,result&MASK);u.reg_write(UC_ARM64_REG_PC,u.reg_read(UC_ARM64_REG_X30))


def exercise(path,blobs,properties):
    expected=inventory(blobs['cs40l26.wmfw'])['writes'][:];rows=table(blobs['cs40l26.wmfw'])[1]
    for n in ['cs40l26.bin','cs40l26-svc.bin','cs40l26-dvl.bin','cs40l26-a2h.bin','cs40l26-dbc.bin']:expected+=bin_writes(blobs[n],rows)
    cases=[]
    for label in ['B2-mailbox-error','playback-config-write-error','IRQ-chip-error','RAM-count-error-then-IRQ-chip',
                  'OWT-count-error-then-IRQ-chip','IRQ-virq-error','IRQ-first-thread-error','IRQ-last-thread-error',
                  'input-allocation-error','input-FF-error','input-register-error','input-sysfs-error','MFD-error']:
        m=Waves(path,blobs,properties)
        if label=='B2-mailbox-error':m.b2_error=-5
        if label=='playback-config-write-error':m.failed_write_address=0x2802158
        if label=='RAM-count-error-then-IRQ-chip':m.read_errors[0x2802140]=-5
        if label=='OWT-count-error-then-IRQ-chip':m.read_errors[0x2805368]=-5
        input_case=label.startswith('input-') or label=='MFD-error'
        if label in ['IRQ-virq-error','IRQ-first-thread-error','IRQ-last-thread-error'] or input_case:m.irq_chip_error=0
        if input_case:m.input_mode=label[6:] if label.startswith('input-') else 'success'
        if label=='IRQ-virq-error':m.virq_error_at=1
        if label=='IRQ-first-thread-error':m.thread_error_at=1
        if label=='IRQ-last-thread-error':m.thread_error_at=27
        rc=m.run('cs40l26_probe',CTX)
        assert rc==(-12 if label in ['input-allocation-error','input-FF-error'] else -5),(label,rc)
        assert m.raw==expected and len(m.raw)==68 and m.removed==[CTX]
        assert m.released==[m.fwmap[n] for n in m.requests]
        assert m.uc.mem_read(CTX+0x1ca,1)==b'\1'
        assert len(m.bulk)==25 and m.mail[-1]==0x03000009
        assert m.pm_services[-1]['name']=='__pm_runtime_suspend'
        early=label in ['B2-mailbox-error','playback-config-write-error']
        assert bool(m.irq_services)==(not early)
        assert ('cs40l26_input_init' in m.entries)==input_case
        assert m.input_allocations==([0x4060000] if input_case else [])
        assert m.virqs==(27 if label=='IRQ-last-thread-error' or input_case else 1 if label in ['IRQ-virq-error','IRQ-first-thread-error'] else 0)
        assert m.threads==(27 if label=='IRQ-last-thread-error' or input_case else 1 if label=='IRQ-first-thread-error' else 0)
        if input_case and label!='input-allocation-error':
            assert m.capabilities==[[21,81],[21,93],[21,90],[21,96]]
            assert m.string(m.u64(0x40a8000))=='cs40l26_input' and m.u64(0x40a8000+0x2c0)==CTX
        if label in ['input-register-error','input-sysfs-error','MFD-error']:
            assert m.u64(0x40a8000+0xc0)&(1<<16)==0
            for offset,symbol in [(0,'cs40l26_upload_effect'),(8,'cs40l26_erase_effect'),(16,'cs40l26_playback_effect'),(24,'cs40l26_set_gain')]:
                assert m.u64(0x40a9000+offset)==m.symbols[symbol]
        assert bytes(m.uc.mem_read(CTX+0x16c,1))==bytes([int(label=='MFD-error')])
        failed_reads=[r for r in m.reads if r['result']]
        if label.startswith(('RAM-','OWT-')):
            target=0x2802140 if label.startswith('RAM-') else 0x2805368
            assert len(failed_reads)==40 and all(r['address']==target and r['result']==-5 for r in failed_reads)
            assert m.entries.count('cs40l26_num_ram_waves')==2
            assert m.entries.count('cs40l26_num_owt_waves')==(1 if label.startswith('RAM-') else 2)
            assert len(m.sleeps)>=40
        else:assert not failed_reads
        m.dsp=m.u64(CTX+0x50)
        coeff=[r for r in m.records() if r['name'] in ['NUM_OF_WAVES','OWT_NUM_OF_WAVES_XM']]
        assert {r['name']:r['register'] for r in coeff}=={'NUM_OF_WAVES':0x2802140,'OWT_NUM_OF_WAVES_XM':0x2805368}
        print(label,rc,'virq',m.virqs,'thread',m.threads,'read-errors',len(failed_reads),flush=True)
        cases.append(dict(case=label,status='PASS',result=rc,fw_loaded=1,entries=m.entries,raw_writes=m.raw,
            irq_services=m.irq_services,input_allocations=m.input_allocations,input_services=m.input_services,
            capabilities=m.capabilities,input_registered_flag=bytes(m.uc.mem_read(CTX+0x16c,1))[0],reads=m.reads,writes=m.writes,
            bulk_writes=m.bulk,mailbox=m.mail,pm_services=m.pm_services,sleeps=m.sleeps,
            wave_coefficients=coeff,remove_calls=m.removed,messages=m.messages))
    return cases


def main():
    dtpath=ROOT/'logs/haptics-devicetree-audit.json';dt=json.loads(dtpath.read_text());sources={str(dtpath.relative_to(ROOT)):sha(dtpath)};cases=[];drivers={}
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
        disasm=ROOT/'logs'/f'{sample}-haptics-wave-irq-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=cs40l26_num_waves,cs40l26_num_ram_waves,cs40l26_num_owt_waves,cs40l26_dsp_config,cs40l26_probe,cs40l26_request_irq,cs40l26_input_init',str(path)]));sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        cases.extend(dict(sample=sample,**c) for c in exercise(path,blobs,node['properties']))
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_runtime_config_emulation.py','haptics_postboost_emulation.py','haptics_probe_upload_emulation.py','haptics_config_emulation.py','haptics_coefficients_emulation.py','haptics_upload_emulation.py','haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-wave-irq-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)

if __name__=='__main__':main()
