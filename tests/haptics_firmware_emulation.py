#!/usr/bin/env python3
"""Execute stock OS4 Cirrus DSP create/header/firmware/coeff-init instructions.

Exact normal/calibration wmfw bytes are used. Allocations, memcpy and regmap
are bounded kernel fixtures; reads supply explicitly synthetic algorithm tables
or errors. No DSP execution, I2C, probe, IRQ, kernel boot or motor is simulated.
Unknown imports and instruction/time budget exhaustion fail closed.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from haptics_driver_emulation import (Module, ROOT, DEPS, MASK, sha, LAYOUTS,
    UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30)

IMAGE=0x4300000
FW=0x4090000
DEV=0x4060000
REG=0x4070000


def digest(raw): return hashlib.sha256(raw).hexdigest()


def inventory(blob):
    assert blob[:4] == b'WMFW' and len(blob)%4 == 0
    offset=40; writes=[]; coeffs=0; regions=[]; algorithms=[]
    maps={5:(0x2800000,4),6:(0x3400000,4),16:(0x3800000,5),17:(0x2000000,3),18:(0x2c00000,3)}
    while offset < len(blob):
        tag,length=struct.unpack_from('<II',blob,offset)
        payload=blob[offset+8:offset+8+length]; assert len(payload)==length
        typ=tag>>24; regions.append(dict(offset=offset,type=typ,length=length))
        if typ in maps:
            base,multiplier=maps[typ]; address=base+(tag&0xffffff)*multiplier
            for start in range(0,length,4096):
                raw=payload[start:start+4096]
                writes.append(dict(address=address+start,length=len(raw),sha256=digest(raw)))
        elif typ==242:
            # Independent container inventory, not a replacement for ARM64 parse.
            name_len=payload[4]; desc=8+(name_len&~3)
            desc_len=struct.unpack_from('<H',payload,desc)[0]
            count_at=desc+4+(desc_len&~3)
            coeffs+=struct.unpack_from('<I',payload,count_at)[0]
            algorithms.append(struct.unpack_from('<I',payload)[0])
        else: assert typ==255
        offset+=8+((length+3)&~3)
    assert offset==len(blob)
    return dict(regions=regions,writes=writes,coefficients=coeffs,metadata_algorithms=algorithms)


class Firmware(Module):
    def __init__(self,path,blob):
        super().__init__(path)
        self.uc.mem_map(IMAGE,0x20000); self.uc.mem_write(IMAGE,blob)
        self.put64(FW,len(blob)); self.put64(FW+8,IMAGE)
        self.raw=[]; self.reads=[]; self.read_error=-5; self.raw_failure=0
        self.read_failure=0; self.hardware={}; self.allocations=[]; self.frees=[]
        self.dsp=self.run('cl_dsp_create',DEV,REG)
        assert self.dsp==0x4100000 and self.u64(self.dsp)==DEV and self.u64(self.dsp+8)==REG
        assert self.u64(self.dsp+16)==self.dsp+16==self.u64(self.dsp+24)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if name is None: return
        a=[self.arg(i) for i in range(7)]
        if name in ['__kvmalloc_node_noprof','__kmalloc_noprof','devm_kmalloc']:
            n=a[1] if name=='devm_kmalloc' else a[0]
            assert 0<n<=0x20000
            r=self.alloc_cursor; self.alloc_cursor+=(n+15)&~15
            assert self.alloc_cursor<0x4200000
            self.allocations.append(dict(address=r,length=n))
        elif name=='memcpy':
            assert 0<=a[2]<=0x20000
            uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2]))); r=a[0]
        elif name=='strncmp':
            assert a[2]<=32
            left=bytes(uc.mem_read(a[0],a[2])).split(b'\0')[0]
            right=bytes(uc.mem_read(a[1],a[2])).split(b'\0')[0]
            r=(left>right)-(left<right)
        elif name in ['_dev_info','kvfree','kfree']:
            if name in ['kvfree','kfree']: self.frees.append(a[0])
            r=0
        elif name=='regmap_raw_write':
            assert a[0]==REG and 0<a[3]<=4096
            self.raw.append(dict(address=a[1],length=a[3],sha256=digest(bytes(uc.mem_read(a[2],a[3])))))
            r=-5 if len(self.raw)==self.raw_failure else 0
        elif name=='regmap_read':
            assert a[0]==REG
            r=-5 if len(self.reads)+1==self.read_failure else self.read_error
            value=None
            if not r:
                assert a[1] in self.hardware,('unknown DSP read',hex(a[1]))
                value=self.hardware[a[1]]; self.put32(a[2],value)
            self.reads.append(dict(address=a[1],value=value,result=r))
        else: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,r&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def records(self):
        head=self.dsp+16; node=self.u64(head); result=[]; previous=head
        while node!=head:
            assert len(result)<2048 and self.u64(node+8)==previous
            p=node-64; n=self.string(p+20)
            assert n and len(n)<32
            offset,kind=struct.unpack('<HH',self.uc.mem_read(p+16,4))
            result.append(dict(algorithm=self.u32(p),name=n,register=self.u32(p+52),offset=offset,type=kind))
            previous=node; node=self.u64(node)
        assert self.u64(head+8)==previous
        return result

    def zero_algorithms(self,marker=0xbedead):
        self.read_error=0
        self.hardware={0x2800024:0,0x2800028:marker}
        self.hardware.update({0x280000c+4*i:0 for i in range(6)})


def exercise(path,original):
    facts=inventory(original); results=[]
    labels=['write-read-error','parse-only-read-error','zero-algorithm-table','resolved-algorithm-table','bad-table-marker',
            'too-many-algorithms','algorithm-field-read-error','raw-first-error','raw-middle-error','raw-last-error',
            'bad-magic','bad-header-size','bad-format','bad-core','bad-version','unaligned-size']
    for label in labels:
        blob=bytearray(original)
        for key,off,value in [('bad-magic',0,0),('bad-header-size',4,0),('bad-format',9,2),
                              ('bad-core',10,3),('bad-version',11,2)]:
            if label==key: blob[off]=value
        if label=='unaligned-size': blob+=b'\0'
        m=Firmware(path,bytes(blob)); flags=int(label!='parse-only-read-error')
        if label in ['zero-algorithm-table','resolved-algorithm-table','bad-table-marker','too-many-algorithms','algorithm-field-read-error']:
            m.zero_algorithms(0 if label=='bad-table-marker' else 0xbedead)
            if label=='resolved-algorithm-table':
                # Synthetic firmware-algorithm row; this does not model DSP execution.
                m.hardware.update(dict(zip(range(0x280000c,0x2800024,4),[facts['metadata_algorithms'][-1],0,0x100,0x1000,0x200,0x1000])))
            if label=='too-many-algorithms':m.hardware[0x2800024]=33
            if label=='algorithm-field-read-error':m.read_failure=4
        if label.startswith('raw-'):
            m.raw_failure={'raw-first-error':1,'raw-middle-error':len(facts['writes'])//2,
                           'raw-last-error':len(facts['writes'])}[label]
        rc=m.run('cl_dsp_firmware_parse',m.dsp,FW,flags)
        malformed=label.startswith('bad-') and label!='bad-table-marker' or label=='unaligned-size'
        assert rc==(0 if label in ['zero-algorithm-table','resolved-algorithm-table'] else -22 if malformed or label in
                   ['bad-table-marker','too-many-algorithms'] else -5),(label,rc,m.messages)
        expected=[] if malformed or not flags else facts['writes'][:m.raw_failure or None]
        assert m.raw==expected,(label,m.raw,expected)
        records=m.records()
        if malformed:
            assert not records and not m.reads and len(m.allocations)==1
        elif m.raw_failure:
            assert not m.reads  # No coefficient initialization after a write error.
        else:
            assert len(records)==facts['coefficients']
            count=8 if label in ['zero-algorithm-table','resolved-algorithm-table','bad-table-marker'] else 4 if label=='algorithm-field-read-error' else 1
            assert len(m.reads)==count
            assert m.reads[0]['address']==0x2800024
        lookup=None
        if label in ['zero-algorithm-table','resolved-algorithm-table']:
            record=records[0]; assert record['algorithm']==facts['metadata_algorithms'][-1] and record['type'] in [5,6]
            m.uc.mem_write(0x4080000,record['name'].encode()+b'\0')
            lookup=m.run('cl_dsp_get_reg',m.dsp,0x4080000,record['type'],record['algorithm'],0x4080100)
            assert lookup==(-22 if label=='zero-algorithm-table' else 0)
            if lookup==0:
                expected=(0x2800000+4*(0x100+record['offset']) if record['type']==5 else
                          0x3400000+4*(0x200+record['offset']))
                assert record['register']==m.u32(0x4080100)==expected
        results.append(dict(case=label,status='PASS',result=rc,raw_writes=m.raw,reads=m.reads,
                            coefficients=len(records),coefficient_sample=records[:3],
                            allocations=len(m.allocations),lookup_result=lookup,messages=m.messages))
        print(label,rc,'writes',len(m.raw),'coefficients',len(records),'reads',len(m.reads),flush=True)
    return facts,results


def main():
    prior=json.loads((ROOT/'logs/haptics-pll-emulation.json').read_text())
    cases=[]; drivers={}; sources={}; inventories={}
    for sample in ['os4-current','os4-stable']:
        driver=prior['drivers'][sample]; path=ROOT/driver['path']
        assert sha(path)==driver['sha256'] and LAYOUTS[sha(path)]=='modern'
        drivers[sample]=driver; base=ROOT/'firmware/samples'/sample/'analysis'
        disasm=ROOT/'logs'/f'{sample}-haptics-firmware-core.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump','-dr',
            '--disassemble-symbols=cl_dsp_create,cl_dsp_header_parse,cl_dsp_firmware_parse,cl_dsp_coeff_init,cl_dsp_get_reg,cl_dsp_get_coeff',str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        for name in ['cs40l26.wmfw','cs40l26-calib.wmfw']:
            firmware=base/'odm/firmware'/name
            sources[str(firmware.relative_to(ROOT))]=sha(firmware)
            facts,current=exercise(path,firmware.read_bytes())
            inventories[sample+'/'+name]=facts
            cases.extend(dict(sample=sample,firmware=name,**c) for c in current)
    assert len(cases)==64
    tests=[Path(__file__).resolve(),ROOT/'tests/haptics_driver_emulation.py',ROOT/'scripts/firmware_facts.py',
           ROOT/'tests/haptics-emulator-dependencies.json']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/haptics-firmware-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,inventories=inventories,sources=sources,
        tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__': main()
