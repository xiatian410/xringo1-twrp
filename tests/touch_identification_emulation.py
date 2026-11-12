#!/usr/bin/env python3
"""Execute original OS4 protocol detection, ID parsing and transfer-size setup.

Message read/write/continued-read and v2 command execution are explicit fixtures;
they supply synthetic ID bytes, statuses and errors. This is not full protocol,
SPI, a controller or a booted kernel. Original detect/parse/size/CRC-update code
and operation-table installation execute; unknown boundaries fail.
"""
import json
from pathlib import Path
import struct
import subprocess

from haptics_driver_emulation import Module, ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30
from touch_startup_emulation import CORE, LAYOUTS

HEADER, DATA = 0x4050000, 0x4060000


def header_v2():
    # Synthetic zero-length identify header; polynomial x^6+x+1 represented
    # in the driver's high-six-bit convention. Original ARM64 validates it.
    for last in range(64):
        header=bytes([0x10,0,0,last]);crc=0xfc
        for value in header:
            crc ^= value
            for _ in range(8):
                crc=((crc<<1) ^ (0xc if crc&0x80 else 0))&255
        if crc&0xfc==0:return header
    raise AssertionError('no synthetic CRC header')


class Identification(Module):
    def __init__(self,path):
        assert sha(path) in LAYOUTS
        super().__init__(path)
        self.boundaries=[];self.errors={};self.statuses={};self.command_result=0
        self.write_results=[]
        self.payload=bytearray(48)
        self.payload[0:2]=bytes([1,1])
        self.payload[2:18]=b'SYNTHETIC-ID-0000'
        struct.pack_into('<IHHH',self.payload,18,4463140,256,512,256)
        self.payload_length=48;self.capacity=64
        self.put64(CORE+0x208,DATA)
        self.put32(CORE+0x210,self.capacity)
        for name in ['syna_tcm_v1_continued_read','syna_tcm_v1_write_message',
                     'syna_tcm_v2_read_message','syna_tcm_v2_write_message',
                     'syna_tcm_v2_execute_cmd_request']:
            self.intercept(name)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if name is None:return
        args=[self.arg(i) for i in range(7)]
        if name in ['_printk','mutex_lock','mutex_unlock']:result=0
        elif name=='memcpy':
            assert args[2]<=4096
            uc.mem_write(args[0],bytes(uc.mem_read(args[1],args[2])));result=args[0]
        elif name in ['syna_tcm_v1_continued_read','syna_tcm_v1_write_message',
                      'syna_tcm_v2_read_message','syna_tcm_v2_write_message']:
            result=(self.write_results.pop(0) if name.endswith('write_message') and self.write_results
                    else self.errors.get(name,0))
            if result==0:
                self.put32(CORE+0x1d8,self.payload_length)
                self.put32(CORE+0x210,self.capacity)
                uc.mem_write(DATA,b'\0'*4+bytes(self.payload)+b'\x5a'*16)
                if name=='syna_tcm_v2_read_message':uc.mem_write(args[1],bytes([self.statuses.get(name,0x10)]))
                elif name.endswith('write_message'):uc.mem_write(args[5],bytes([self.statuses.get(name,1)]))
        elif name=='syna_tcm_v2_execute_cmd_request':result=self.command_result
        else:raise AssertionError(('unknown identification boundary',name,args))
        self.calls.append(name);self.boundaries.append(dict(name=name,args=args,result=result))
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def detect(self,protocol,header=None,core=CORE,length=4):
        self.uc.mem_write(HEADER,header or (b'\xa5\x10\x30\0' if protocol==1 else header_v2()))
        return self.run(f'syna_tcm_v{protocol}_detect',core,HEADER,length)


def exercise(path):
    cases=[]
    for protocol in [1,2]:
        for label in ['normal','bootloader','zero-payload','short-capacity','missing-build-id',
                      'zero-write-size','zero-read-size','read-error','fallback-identify',
                      'fallback-reset','all-commands-fail','invalid-header','short-header','null-core',
                      'host-write-limit','host-read-limit','size-command-error']:
            if protocol==1 and label in ['zero-read-size','host-read-limit','size-command-error']:continue
            m=Identification(path)
            if label=='bootloader':m.payload[1]=11
            if label=='zero-payload':m.payload_length=0
            if label=='short-capacity':m.capacity=8
            if label=='missing-build-id':m.payload[18:22]=b'\0'*4
            if label=='zero-write-size':m.payload[22:24]=b'\0'*2
            if label=='zero-read-size':m.payload[24:28]=b'\0'*4
            if label=='host-write-limit':m.put32(CORE+0x2c,128)
            if label=='host-read-limit':m.put32(CORE+0x30,128)
            if label=='size-command-error':m.command_result=-110
            header=None
            if label=='zero-payload' and protocol==1:header=b'\xa5\x10\0\0'
            if label in ['read-error','fallback-identify','fallback-reset','all-commands-fail']:
                if protocol==1:header=b'\xa5\0\0\0'
                read='syna_tcm_v2_read_message' if protocol==2 else 'syna_tcm_v1_continued_read'
                if protocol==2:
                    if label=='fallback-identify':m.statuses[read]=0
                    else:m.errors[read]=-110
                if label in ['fallback-reset','all-commands-fail']:
                    m.errors[f'syna_tcm_v{protocol}_write_message']=-110
                if label=='fallback-reset':m.write_results=[-110,0]
                if label=='read-error' and protocol==1:
                    header=None;m.errors[read]=-110
            if label=='invalid-header':header=b'\0\0\0\0'
            rc=m.detect(protocol,header,core=0 if label=='null-core' else CORE,
                        length=3 if label=='short-header' else 4)
            success=label in ['normal','bootloader','fallback-identify','fallback-reset','host-write-limit',
                              'host-read-limit'] or (protocol==2 and label in ['zero-write-size','zero-read-size','read-error'])
            assert (rc==0)==success,(protocol,label,rc,m.calls)
            if not success:
                expected=(-245 if label=='invalid-header' else
                          -241 if label in ['short-header','null-core'] else -242)
                assert rc==expected,(protocol,label,rc)
            if success:
                assert m.uc.mem_read(CORE,2)==bytes([protocol,11 if label=='bootloader' else 1])
                assert m.u32(CORE+4)==4463140
                assert m.u64(CORE+0x330)==m.symbols[f'syna_tcm_v{protocol}_read_message']
                assert m.u64(CORE+0x340)==m.symbols[f'syna_tcm_v{protocol}_write_message']
                if label=='host-write-limit':assert m.u32(CORE+0x2c)==128
                if label=='host-read-limit':assert m.u32(CORE+0x30)==128
                if label in ['zero-write-size','zero-read-size']:
                    assert m.u32(CORE+0x2c)==m.u32(CORE+0x30)==0
                if label=='fallback-reset':
                    commands=[c['args'][1] for c in m.boundaries if c['name'].endswith('write_message')]
                    assert commands==[2,4] and not m.write_results
            if label=='size-command-error':
                assert rc==-242 and m.u32(CORE+0x30)==256 and m.u64(CORE+0x330)==0
            for boundary in m.boundaries:
                if boundary['name']=='syna_tcm_v2_execute_cmd_request':
                    args=boundary['args']
                    assert args[1]==9 and args[3:5]==[2,2]
            cases.append(dict(case=f'v{protocol}-{label}',status='PASS',result=rc,
                              mode=bytes(m.uc.mem_read(CORE,2)).hex(),
                              max_write=m.u32(CORE+0x2c),max_read=m.u32(CORE+0x30),
                              boundaries=m.boundaries))
    return cases


def main():
    cases=[];drivers={};sources={}
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    functions=['syna_tcm_v1_detect','syna_tcm_v2_detect','syna_tcm_v1_parse_idinfo',
               'syna_tcm_v2_parse_idinfo','syna_tcm_v1_set_max_rw_size',
               'syna_tcm_v2_set_max_rw_size','syna_tcm_v1_update_crc','syna_tcm_v2_set_ops']
    for sample in ['os4-current','os4-stable']:
        path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        disasm=ROOT/'logs'/f'{sample}-touch-identification.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols='+','.join(functions),str(path)]))
        sources[str(disasm)]=sha(disasm)
        results=exercise(path)
        for case in results:case['sample']=sample;cases.append(case)
        print('PASS',sample,len(results),'identification cases',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/haptics_driver_emulation.py',ROOT/'tests/touch_startup_emulation.py']
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-identification-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,synthetic_v2_header=header_v2().hex(),
        tests={str(p):sha(p) for p in tests},emulator_files={str(p):sha(p) for p in dependencies}),indent=2)+'\n')


if __name__=='__main__':main()
