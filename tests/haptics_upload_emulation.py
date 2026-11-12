#!/usr/bin/env python3
"""Execute stock OS4 firmware upload, PM shutdown, parser and firmware identity.

Uses exact ODM wmfw/bin bytes and original chip resolver, DSP pre-config,
PM transition, state-get, wavetable-create, parser, coefficient loader and
firmware-ID/revision functions. Mailbox acknowledgement, regmap reads/writes,
algorithm rows, allocations, firmware requests and sleeps are explicit fixtures.
Coefficient revisions are synthetic and may be rejected by original bin parser.
Joined uploads stop on actual failures, including first MEM_RDY update failure;
no successful DSP boot, complete probe, IRQ, physical I2C or motor is claimed.
"""
import json
from pathlib import Path
import struct
import subprocess
from haptics_firmware_emulation import Firmware, ROOT, DEPS, FW, DEV, REG, inventory, sha
from haptics_driver_emulation import MASK, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30, UC_ARM64_REG_SP

CTX=0x4000000


class Upload(Firmware):
    def __init__(self,path,blobs,filename):
        self.rom=[]; self.states=[]
        super().__init__(path,blobs[filename])
        self.put64(CTX,DEV); self.put64(CTX+8,REG)
        self.read_error=0; self.hardware={0:0x40a270,4:0xb2}
        self.writes=[]; self.mail=[]; self.sleeps=[]; self.requests=[]; self.released=[]; self.updates=[]
        self.mail_error=0; self.write_failure=0; self.read_errors={}; self.missing=set(); self.entries=[]
        self.watch=['cs40l26_dsp_pre_config','cs40l26_pm_state_transition','cs40l26_dsp_state_get',
                    'cl_dsp_firmware_parse','cs40l26_get_fw_params','cs40l26_coeff_load','cl_dsp_coeff_file_parse','cs40l26_dsp_config']
        self.fwmap={}; offset=0x40b0000
        for name,raw in sorted(blobs.items()):
            desc=offset; address=offset+32
            self.uc.mem_write(address,raw); self.put64(desc,len(raw)); self.put64(desc+8,address)
            self.fwmap[name]=desc; offset+=((len(raw)+4095)&~4095)+4096
        assert offset<0x4100000
        self.intercept('cs40l26_mailbox_write')
        assert self.run('cs40l26_part_num_resolve',CTX)==0
        rom=self.u64(CTX+0x1af8); self.rom=[self.u32(rom+4*i) for i in range(8)]
        assert self.rom[:4]==[0x2801f98,0x2801fa0,0x2801f78,0x2806af8]
        self.states=[3,1]
        self.hardware.update({self.rom[0]:1,self.rom[1]+8:2,self.rom[3]:2,self.rom[2]+24:1})
        self.facts=inventory(blobs[filename]); ids=self.facts['metadata_algorithms']
        self.revision=0x0707ea if filename=='cs40l26.wmfw' else 0x010123
        cursor=0x280000c
        self.hardware[0x2800024]=len(ids)-1
        for i,aid in enumerate(ids):
            row=[aid,self.revision,0x1000+i*0x1000,0x1000,0x2000+i*0x1000,0x1000]
            self.hardware.update(dict(zip(range(cursor,cursor+24,4),row)))
            cursor+=28 if i==0 else 24
        self.hardware[cursor]=0xbedead
        self.uc.mem_write(CTX+0x1cb,bytes([filename=='cs40l26-calib.wmfw']))
        self.reads=[]

    def run(self,name,*args):
        if name!='cs40l26_fw_upload':return super().run(name,*args)
        # Full coefficient list walks exceed the isolated parser's 100k limit.
        # Keep an explicit finite budget; exhaustion always fails.
        for i,v in enumerate(args):self.uc.reg_write(UC_ARM64_REG_X0+i,v&MASK)
        self.uc.reg_write(UC_ARM64_REG_SP,0x5020000-16)
        self.uc.reg_write(UC_ARM64_REG_X30,self.return_address)
        self.uc.emu_start(self.symbols[name],self.return_address,timeout=10000000,count=1000000)
        assert self.uc.reg_read(UC_ARM64_REG_PC)==self.return_address,('upload budget',name)
        r=self.arg(0)&0xffffffff
        return r if r<0x80000000 else r-0x100000000

    def on_code(self,uc,address,size,data):
        if hasattr(self,'watch'):
            for symbol in self.watch:
                if address==self.symbols[symbol]:self.entries.append(symbol)
        name=self.hooks.get(address)
        if name is None:return
        a=[self.arg(i) for i in range(7)]; r=None
        if name=='regmap_read' and self.rom:
            if a[1]==self.rom[0] and self.states:self.hardware[a[1]]=self.states.pop(0)
            if a[1] in self.read_errors:
                r=self.read_errors[a[1]];self.reads.append(dict(address=a[1],value=None,result=r))
        if r is not None:pass
        elif name=='cs40l26_mailbox_write':self.mail.append(a[1]);r=self.mail_error
        elif name=='__kmalloc_cache_noprof':
            assert 0<a[2]<=0x20000
            r=self.alloc_cursor;self.alloc_cursor+=(a[2]+15)&~15;assert self.alloc_cursor<0x4200000
        elif name=='regmap_update_bits_base':
            assert a[0]==REG
            self.updates.append(dict(address=a[1],mask=a[2],value=a[3]));r=-5
        elif name=='regmap_write':
            assert a[0]==REG
            self.writes.append(dict(address=a[1],value=a[2]));r=-5 if len(self.writes)==self.write_failure else 0
        elif name=='_dev_warn':r=0
        elif name=='usleep_range_state':self.sleeps.append(a[:3]);r=0
        elif name=='request_firmware':
            filename=self.string(a[1]);self.requests.append(filename)
            assert filename in self.fwmap
            self.put64(a[0],0 if filename in self.missing else self.fwmap[filename])
            r=-2 if filename in self.missing else 0
        elif name=='release_firmware':self.released.append(a[0]);r=0
        elif name in ['strlen','strnlen']:
            bound=128 if name=='strlen' else a[1];assert bound<=128
            r=len(bytes(uc.mem_read(a[0],bound)).split(b'\0')[0])
        elif name=='sized_strscpy':
            assert 0<a[2]<=32
            raw=bytes(uc.mem_read(a[1],a[2])).split(b'\0')[0]
            assert len(raw)<a[2];uc.mem_write(a[0],raw+b'\0');r=len(raw)
        if r is None:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,r&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path,blobs,filename):
    results=[]
    labels=['request-missing','pre-mailbox-error','pre-PM-stuck','pre-shutdown-wrong','pre-state-stuck',
            'pre-core-write-error','bad-firmware-magic','raw-first-error','algorithm-count-read-error',
            'unknown-firmware-ID','old-firmware-revision','config-MEM_RDY-error']
    for label in labels:
        m=Upload(path,blobs,filename)
        if label=='request-missing':m.missing={filename}
        if label=='pre-mailbox-error':m.mail_error=-5
        if label=='pre-PM-stuck':m.states=[0]*5
        if label=='pre-shutdown-wrong':m.hardware[m.rom[3]]=0
        if label=='pre-state-stuck':m.states=[3]*11
        if label=='pre-core-write-error':m.write_failure=1
        if label=='bad-firmware-magic':m.uc.mem_write(m.u64(m.fwmap[filename]+8),b'FAIL')
        if label=='raw-first-error':m.raw_failure=1
        if label=='algorithm-count-read-error':m.read_errors[0x2800024]=-5
        if label=='unknown-firmware-ID':m.hardware[0x280000c]=0
        if label=='old-firmware-revision':m.hardware[0x2800010]=0x07022a if filename=='cs40l26.wmfw' else 0x010122
        rc=m.run('cs40l26_fw_upload',CTX)
        expected=(-2 if label=='request-missing' else -110 if label=='pre-PM-stuck' else -22 if label in
            ['pre-shutdown-wrong','pre-state-stuck','bad-firmware-magic','unknown-firmware-ID','old-firmware-revision'] else -5)
        assert rc==expected,(filename,label,rc,m.messages)
        assert m.requests[0]==filename
        pre_failure=label in ['pre-mailbox-error','pre-PM-stuck','pre-shutdown-wrong','pre-state-stuck','pre-core-write-error']
        # Original upload returns directly on pre-config failure, bypassing the
        # firmware release used after parser return. Preserve that observation.
        assert m.released==([0] if label=='request-missing' else [] if pre_failure else
                            [m.fwmap[name] for name in m.requests]),(label,m.requests,m.released)
        if label=='request-missing':assert not m.mail and not m.writes and not m.raw
        elif label in ['pre-mailbox-error','pre-PM-stuck','pre-shutdown-wrong','pre-state-stuck','pre-core-write-error']:
            assert not m.raw and 'cl_dsp_firmware_parse' not in m.entries
        elif label=='bad-firmware-magic':assert not m.raw and len(m.writes)==1
        elif label=='raw-first-error':assert m.raw==m.facts['writes'][:1]
        else:assert m.raw==m.facts['writes']
        if label=='pre-PM-stuck':assert len(m.mail)==5 and len(m.sleeps)==5
        if label=='pre-state-stuck':assert len(m.mail)==1 and len(m.sleeps)==10
        if label=='config-MEM_RDY-error':
            assert m.updates==[dict(address=0x2900,mask=2,value=2)]
            assert 'cs40l26_get_fw_params' in m.entries and 'cs40l26_dsp_config' in m.entries
            assert 'cs40l26_coeff_load' in m.entries and 'cl_dsp_coeff_file_parse' in m.entries
            assert len(m.requests)>1
        else:assert not m.updates and 'cs40l26_dsp_config' not in m.entries
        # fw_loaded must never be set by these failed startup paths.
        assert bytes(m.uc.mem_read(CTX+0x1ca,1))==b'\0'
        results.append(dict(case=label,status='PASS',result=rc,requests=m.requests,released=m.released,
            raw_writes=m.raw,reads=m.reads,writes=m.writes,updates=m.updates,mailbox=m.mail,
            sleeps=m.sleeps,entries=m.entries,messages=m.messages,fw_loaded=0))
        print(filename,label,rc,'raw',len(m.raw),'requests',len(m.requests),flush=True)
    return results


def parameters(path,blobs):
    # Original fw identity functions perform actual regmap-read calls.
    rows=[(0x1800d4,0x07022b,0),(0x1800d4,0x07022a,-22),(0x1800d4,0x270216,0),
          (0x1800d4,0x270215,-22),(0x1800d4,0x0a0000,0),(0x1800da,0x010123,0),
          (0x1800da,0x010122,-22),(0x1800da,0x21010d,0),(0x1800da,0x21010c,-22),
          (0x1800da,0x0a0000,0),(0x1800d4,0x080000,-22),(0,0x07022b,-22)]
    cases=[]
    for identity,revision,expected in rows:
        m=Upload(path,blobs,'cs40l26.wmfw');m.put64(CTX+0x50,m.dsp)
        m.hardware[0x280000c]=identity;m.hardware[0x2800010]=revision
        rc=m.run('cs40l26_get_fw_params',CTX)
        assert rc==expected and [r['address'] for r in m.reads]==[0x2800010,0x280000c]
        assert m.u32(CTX+0x1c4)==(identity if rc==0 else 0)
        cases.append(dict(case=f'ID-{identity:x}-revision-{revision:x}',status='PASS',result=rc,
                          reads=m.reads,stored_id=m.u32(CTX+0x1c4)))
    return cases


def main():
    prior=json.loads((ROOT/'logs/haptics-firmware-emulation.json').read_text())
    cases=[];drivers={};sources={}
    for sample in ['os4-current','os4-stable']:
        driver=prior['drivers'][sample];path=ROOT/driver['path'];assert sha(path)==driver['sha256']
        drivers[sample]=driver;base=ROOT/'firmware/samples'/sample/'analysis/odm/firmware'
        files=sorted(base.glob('cs40l26*'));blobs={p.name:p.read_bytes() for p in files}
        sources.update({str(p.relative_to(ROOT)):sha(p) for p in files})
        disasm=ROOT/'logs'/f'{sample}-haptics-upload-core.disasm'
        names=['cs40l26_fw_upload','cs40l26_dsp_pre_config','cs40l26_pm_state_transition',
            'cs40l26_dsp_state_get','cl_dsp_wavetable_create','cs40l26_get_fw_params',
            'cl_dsp_fw_rev_get','cl_dsp_fw_id_get','cs40l26_coeff_load','cl_dsp_coeff_file_parse','cs40l26_dsp_config']
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr',
            '--disassemble-symbols='+','.join(names),str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        for filename in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
            cases.extend(dict(sample=sample,firmware=filename,**c) for c in exercise(path,blobs,filename))
        cases.extend(dict(sample=sample,firmware='identity-only',**c) for c in parameters(path,blobs))
    assert len(cases)==72
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/n for n in
        ['haptics_firmware_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]
    tests.append(ROOT/'scripts/firmware_facts.py')
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-upload-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in dependencies}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
