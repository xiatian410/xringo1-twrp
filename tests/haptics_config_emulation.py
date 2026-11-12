#!/usr/bin/env python3
"""Join original OS4 upload/coefficients to DSP config and IRQ mask setup.

Algorithm tables come from exact stock wmfw bytes at an explicit regmap fixture.
PM state, HALO state, IRQ mask and write-sequence bytes are synthetic reads;
all-FF sequences contain an immediate terminator, not a real controller dump.
Original memchunk/wseq/populate/write, DSP config and IRQ mask code executes.
Debugfs init, mailbox and kernel/regmap services remain explicit fixtures.
Every scenario ends at an injected failure or invalid state; no DSP execution,
complete probe/IRQ delivery, hardware state changes or motor output is claimed.
"""
import json
from pathlib import Path
import subprocess
from haptics_coefficients_emulation import Upload, ROOT, DEPS, CTX, sha, table
from haptics_upload_emulation import REG
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC


class Config(Upload):
    def __init__(self,path,blobs,filename):
        super().__init__(path,blobs,filename)
        self.hardware.update(table(blobs[filename])[0]);self.rawreads=[];self.bulk=[]
        # These explicit synthetic values do not follow automatically from writes.
        self.hardware.update({0x2800370:3,0x2800378:2,0x2800fa8:2,0x10110:0xffffffff})
        self.rawread_failure=0;self.bulk_failure=0;self.failed_write_address=None;self.debugfs=[]
        self.intercept('cs40l26_debugfs_init')
        self.watch.extend(['cs40l26_wseq_populate','cs40l26_wseq_write','cs40l26_irq_update_mask','cs40l26_gpio_config'])

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if name is None:return super().on_code(uc,address,size,data)
        a=[self.arg(i) for i in range(7)];r=None
        if name=='regmap_update_bits_base':
            assert a[0]==REG
            self.updates.append(dict(address=a[1],mask=a[2],value=a[3]));r=0
        elif name=='cs40l26_debugfs_init':self.debugfs.append(a[0]);r=0
        elif name=='regmap_raw_read':
            assert a[0]==REG and a[3] in [132,516]
            r=-5 if len(self.rawreads)+1==self.rawread_failure else 0
            self.rawreads.append(dict(address=a[1],length=a[3],result=r,fixture='all-FF-immediate-terminator'))
            if not r:uc.mem_write(a[2],b'\xff'*a[3])
        elif name=='regmap_bulk_write':
            assert a[0]==REG and 0<a[3]<=32
            raw=bytes(uc.mem_read(a[2],a[3]*4))
            r=-5 if len(self.bulk)+1==self.bulk_failure else 0
            self.bulk.append(dict(address=a[1],words=a[3],bytes=raw.hex(),result=r))
        elif name=='regmap_write' and a[1]==self.failed_write_address:
            self.writes.append(dict(address=a[1],value=a[2]));r=-5
        if r is None:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,r&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path,blobs,filename):
    results=[]
    labels=['call-ram-write-exhausted','active-sequence-read-error','power-sequence-read-error',
            'first-sequence-write-error','second-sequence-write-error','HALO-read-error','HALO-invalid-state',
            'IRQ-mask-read-error','GPIO-read-error']
    for label in labels:
        m=Config(path,blobs,filename)
        if label=='call-ram-write-exhausted':m.failed_write_address=0x2800ff8
        if label=='active-sequence-read-error':m.rawread_failure=1
        if label=='power-sequence-read-error':m.rawread_failure=2
        if label=='first-sequence-write-error':m.bulk_failure=1
        if label=='second-sequence-write-error':m.bulk_failure=2
        if label=='HALO-read-error':m.read_errors[0x2800fa8]=-5
        if label=='HALO-invalid-state':m.hardware[0x2800fa8]=0
        if label=='IRQ-mask-read-error':m.read_errors[0x10110]=-5
        if label=='GPIO-read-error':m.read_errors[0x381c]=-5
        rc=m.run('cs40l26_fw_upload',CTX)
        assert rc==(-62 if label=='call-ram-write-exhausted' else -22 if label=='HALO-invalid-state' else -5),(filename,label,rc,m.messages)
        assert m.updates[0]==dict(address=0x2900,mask=2,value=2)
        loaded=bytes(m.uc.mem_read(CTX+0x1ca,1))[0]
        assert loaded==int(label!='call-ram-write-exhausted')
        assert m.released==[m.fwmap[n] for n in m.requests]
        assert len(m.raw)==(68 if filename=='cs40l26.wmfw' else 63)
        if label=='call-ram-write-exhausted':
            assert len([w for w in m.writes if w['address']==0x2800ff8])==20
            assert len(m.sleeps)==20 and not m.rawreads and not m.bulk and not m.debugfs
        else:
            assert m.debugfs==[CTX]
            assert len(m.rawreads)==(1 if label=='active-sequence-read-error' else 2)
            assert len(m.bulk)==(0 if 'sequence-read-error' in label else 1 if label=='first-sequence-write-error' else
                                5 if label=='GPIO-read-error' else 2)
        irq='cs40l26_irq_update_mask' in m.entries
        assert irq==(label in ['IRQ-mask-read-error','GPIO-read-error'])
        assert ('cs40l26_gpio_config' in m.entries)==(label=='GPIO-read-error')
        print(filename,label,rc,'loaded',loaded,'rawread',len(m.rawreads),'bulk',len(m.bulk),flush=True)
        results.append(dict(case=label,status='PASS',result=rc,fw_loaded=loaded,raw_reads=m.rawreads,
            bulk_writes=m.bulk,writes=m.writes,updates=m.updates,mailbox=m.mail,reads=m.reads,
            sleeps=m.sleeps,entries=m.entries,debugfs=m.debugfs,messages=m.messages))
    return results


def main():
    prior=json.loads((ROOT/'logs/haptics-coefficients-emulation.json').read_text());cases=[];drivers={};sources={}
    for sample in ['os4-current','os4-stable']:
        record=prior['drivers'][sample];path=ROOT/record['path'];assert sha(path)==record['sha256'];drivers[sample]=record
        files=sorted((ROOT/'firmware/samples'/sample/'analysis/odm/firmware').glob('cs40l26*'))
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in files});blobs={p.name:p.read_bytes() for p in files}
        disasm=ROOT/'logs'/f'{sample}-haptics-config-core.disasm'
        names=['cs40l26_dsp_config','cs40l26_wseq_populate','cs40l26_wseq_write','cl_dsp_memchunk_create',
               'cl_dsp_memchunk_end','cl_dsp_memchunk_read','cs40l26_irq_update_mask','cs40l26_gpio_config']
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr',
            '--disassemble-symbols='+','.join(names),str(path)]));sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        for filename in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
            cases.extend(dict(sample=sample,firmware=filename,**c) for c in exercise(path,blobs,filename))
    assert len(cases)==36
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in ['haptics_coefficients_emulation.py',
        'haptics_upload_emulation.py','haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]
    tests.append(ROOT/'scripts/firmware_facts.py')
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-config-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
