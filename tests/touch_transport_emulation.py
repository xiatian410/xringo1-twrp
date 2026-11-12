#!/usr/bin/env python3
"""Execute original OS4 SPI buffers/transfers and protocol-selection code.

spi_sync substitutes a controller, captures original transfer descriptors and
supplies deterministic synthetic bytes. Allocation, completion, locks and PM
are fixtures. Protocol-specific detect is a separately declared boundary.
No physical SPI, kernel scheduling, real controller response or device testing.
"""
import json
from pathlib import Path
import subprocess

from touch_spi_emulation import Spi, SPI, DEVICE
from touch_startup_emulation import CTX, CORE, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

BUFFER=0x4068000


class Transport(Spi):
    def __init__(self,path,properties,children):
        super().__init__(path,properties,children)
        self.transfers=[];self.freed=[];self.allocations=[]
        self.sync_error=0;self.allocation_fail=0;self.completion=0
        self.sync_error_at=0;self.install_ops=True
        self.protocol_results={};self.protocol_calls=[]
        assert self.run('syna_spi_probe',SPI)==0
        self.allocations=[];self.freed=[]
        self.put64(DEVICE+0xa8,CTX)
        self.put64(CORE+0x38,self.data+0x1d8)
        self.response=bytes(range(256))*260
        self.boundaries=[];self.calls=[]
        del self.hooks[self.symbols['syna_tcm_detect_device']]
        self.protocol_results={'syna_tcm_v1_detect':0,'syna_tcm_v2_detect':0}
        self.protocol_calls=[]
        for name in self.protocol_results:self.intercept(name)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(6)]
        if name=='devm_kmalloc':
            self.allocations.append(args[1])
            if len(self.allocations)==self.allocation_fail:result=0
            else:
                assert 0<args[1]<=0x10000
                result=self.alloc_cursor
                self.alloc_cursor+=(args[1]+4095)&~4095
                assert self.alloc_cursor<0x4200000
                uc.mem_write(result,b'\0'*args[1])
        elif name=='devm_kfree':self.freed.append(args[1]);result=0
        elif name in ['memset','memcpy']:
            assert args[2]<=0x10000
            payload=bytes([args[1]&255])*args[2] if name=='memset' else bytes(uc.mem_read(args[1],args[2]))
            if payload:uc.mem_write(args[0],payload)
            result=args[0]
        elif name=='spi_sync':
            assert args[0]==SPI
            head=args[1];link=self.u64(head);seen=set();offset=0;records=[]
            while link!=head:
                assert link not in seen and len(seen)<1024
                seen.add(link);transfer=link-0x78
                tx,rx,length=self.u64(transfer),self.u64(transfer+8),self.u32(transfer+0x10)
                assert 0<=length<=0xffff
                sent=bytes(uc.mem_read(tx,length)).hex() if tx else None
                sync_result=self.sync_error if self.sync_error_at in [0,len(self.transfers)+1] else 0
                if rx and not sync_result:
                    assert offset+length<=len(self.response)
                    uc.mem_write(rx,self.response[offset:offset+length])
                records.append(dict(length=length,tx=sent,rx=bool(rx)))
                offset+=length;link=self.u64(link)
            self.transfers.append(records);result=sync_result
        elif name=='wait_for_completion_timeout':
            if self.completion:uc.mem_write(CTX+0x6c8,b'\0')
            result=self.completion
        elif name in self.protocol_results:
            self.protocol_calls.append(dict(name=name,header=bytes(uc.mem_read(args[1],args[2])).hex()))
            result=self.protocol_results[name]
            if result==0:
                uc.mem_write(CORE+1,b'\1')
            if result==0 and self.install_ops:
                self.put64(CORE+0x330,self.symbols['syna_tcm_v1_read_message' if name.endswith('v1_detect') else 'syna_tcm_v2_read_message'])
                self.put64(CORE+0x340,self.symbols['syna_tcm_v1_write_message' if name.endswith('v1_detect') else 'syna_tcm_v2_write_message'])
        else:return super().on_code(uc,address,size,data)
        self.calls.append(name)
        self.boundaries.append(dict(name=name,args=args,result=result))
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def transfer(self,operation,length):
        return self.run('syna_spi_'+operation,self.data+0x1d8,BUFFER,length)


def exercise(path,properties,children):
    cases=[]
    def passed(label,m,rc):
        cases.append(dict(case=label,status='PASS',result=rc,transfers=m.transfers,
                          allocations=m.allocations,freed=m.freed,protocol_calls=m.protocol_calls,
                          boundaries=m.boundaries))
    for operation in ['read','write']:
        for length in [1,4,64,257,258,320]:
            m=Transport(path,properties,children)
            payload=bytes((255-i)%256 for i in range(length));m.uc.mem_write(BUFFER,payload)
            rc=m.transfer(operation,length)
            assert rc==length,(operation,length,rc,m.calls)
            assert len(m.transfers)==1 and len(m.transfers[0])==1
            record=m.transfers[0][0]
            actual=length if operation=='write' or length<257 or length%64==0 else ((length+63)//64)*64
            assert record['length']==actual,(operation,length,record['length'])
            if operation=='read':
                assert bytes(m.uc.mem_read(BUFFER,length))==m.response[:length]
                assert record['tx'] is None # Bulk read uses controller dummy TX.
            else:assert record['tx']==payload.hex()
            passed(f'{operation}-{length}',m,rc)
        for label in ['suspended-timeout','suspended-completed','sync-error','allocation-error',
                      'tx-allocation-error','rx-allocation-error',
                      'missing-spi','missing-platform','missing-context','oversize']:
            m=Transport(path,properties,children);m.uc.mem_write(BUFFER,b'\xaa'*4)
            if label.startswith('suspended-'):
                m.uc.mem_write(CTX+0x6c8,b'\1')
                m.completion=int(label=='suspended-completed')
            if label=='sync-error':m.sync_error=-110
            if label=='allocation-error':m.allocation_fail=1
            if label=='tx-allocation-error':m.allocation_fail=2
            if label=='rx-allocation-error':m.allocation_fail=3
            if label=='missing-spi':m.put64(m.data+0x1d8,0)
            if label=='missing-platform':m.put64(m.bss+0xe0,0)
            if label=='missing-context':m.put64(DEVICE+0xa8,0)
            length=0xffff if label=='oversize' else 4
            rc=m.transfer(operation,length)
            if label=='suspended-completed':assert rc==4 and len(m.transfers)==1
            else:
                assert rc<0,(operation,label,rc)
                assert len(m.transfers)==int(label=='sync-error')
            if label in ['sync-error','allocation-error','tx-allocation-error','rx-allocation-error','suspended-timeout']:
                assert m.calls[-2:]==['pm_relax','mutex_unlock'],(label,m.calls)
                if operation=='read':assert bytes(m.uc.mem_read(BUFFER,4))==b'\xaa'*4
            passed(f'{operation}-{label}',m,rc)
        m=Transport(path,properties,children)
        m.uc.mem_write(BUFFER,b'\xaa'*320)
        assert m.transfer(operation,4)==4
        first=list(m.allocations)
        assert m.transfer(operation,4)==4
        assert m.allocations==first,('buffer reuse',operation,m.allocations)
        assert m.transfer(operation,320)==320
        assert m.allocations==first+[320,320]
        assert len(m.freed)==2
        passed(f'{operation}-reuse-then-grow',m,320)
    for label,v1,v2,expected_calls in [
        ('protocol-v2',0,0,['syna_tcm_v2_detect']),
        ('protocol-fallback-v1',0,-22,['syna_tcm_v2_detect','syna_tcm_v1_detect']),
        ('protocol-both-fail',-22,-22,['syna_tcm_v2_detect','syna_tcm_v1_detect']),
    ]:
        m=Transport(path,properties,children)
        m.protocol_results={'syna_tcm_v1_detect':v1,'syna_tcm_v2_detect':v2}
        rc=m.run('syna_tcm_detect_device',CORE,0,1)
        assert [r['name'] for r in m.protocol_calls]==expected_calls
        assert len(m.transfers)==2
        assert m.transfers[0][0]['tx']=='02'
        assert m.protocol_calls[0]['header']=='00010203'
        assert (rc>0)==(v1==0 or v2==0),(label,rc)
        passed(label,m,rc)
    for label in ['write-error','read-error','missing-read-callback','missing-write-callback',
                  'incomplete-protocol-ops','original-protocol-invalid-header']:
        m=Transport(path,properties,children)
        expected=-245
        if label in ['write-error','read-error']:
            m.sync_error=-110;m.sync_error_at=1 if label=='write-error' else 2;expected=-110
        if label=='missing-read-callback':m.put64(m.data+0x1d8+0x118,0)
        if label=='missing-write-callback':m.put64(m.data+0x1d8+0x120,0)
        if label=='incomplete-protocol-ops':
            m.install_ops=False;m.put64(CORE+0x330,0);m.put64(CORE+0x340,0)
        if label=='original-protocol-invalid-header':
            for name in m.protocol_results:del m.hooks[m.symbols[name]]
        rc=m.run('syna_tcm_detect_device',CORE,0,1)
        assert rc==expected,(label,rc,m.calls)
        if label=='original-protocol-invalid-header':assert not m.protocol_calls and len(m.transfers)==2
        elif label!='incomplete-protocol-ops':assert not m.protocol_calls
        passed('detect-'+label,m,rc)
    return cases


def main():
    evidence=ROOT/'logs/touch-devicetree-audit.json';dt=json.loads(evidence.read_text())
    sources={str(evidence):sha(evidence)}
    for field in ['sources','tests','libfdt_sources']:
        for name,expected in dt[field].items():
            p=Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p)==expected;sources[str(p)]=expected
    cases=[];drivers={}
    tool=Path('/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump')
    for record in dt['cases']:
        sample=record['sample'];path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        assert sha(path) in LAYOUTS;drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        properties={k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children={n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        disasm=ROOT/'logs'/f'{sample}-touch-transport-core.disasm'
        disasm.write_bytes(subprocess.check_output([str(tool),'-dr',
            '--disassemble-symbols=syna_spi_read,syna_spi_write,syna_spi_alloc_mem,syna_print_xfer_data,syna_tcm_detect_device,syna_tcm_v1_detect,syna_tcm_v2_detect',str(path)]))
        sources[str(disasm)]=sha(disasm)
        results=exercise(path,properties,children)
        for case in results:case['sample']=sample;cases.append(case)
        print('PASS',sample,len(results),'transport/protocol-selection cases',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/touch_spi_emulation.py',ROOT/'tests/touch_configuration_emulation.py',
           ROOT/'tests/touch_startup_emulation.py',ROOT/'tests/haptics_driver_emulation.py']
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-transport-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p):sha(p) for p in tests},
        emulator_files={str(p):sha(p) for p in dependencies}),indent=2)+'\n')


if __name__=='__main__':main()
