#!/usr/bin/env python3
"""Original OS4 message read -> event copy -> parser -> ISR with synthetic bytes.

v1 executes original read_message, continued_read, buffer operations, transport
callback CFI and header retries. The callback supplies explicit byte fragments,
not physical SPI. v2 execute_cmd_request remains a declared boundary supplying
decoded command state; original read_message/dispatch/get_event_data execute.
Config acquisition uses the existing synthetic command boundary. Kernel input,
allocation, GPIO, IRQ, time, locks and completion are fixtures; no phone used.
"""
import json
from pathlib import Path
import struct
import subprocess

from touch_configuration_emulation import Configuration
from touch_startup_emulation import CORE, CTX, HW, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

READ_CALLBACK=0x300c000
EVENT_ID, OUTPUT=0x4070000, 0x4071000


class Message(Configuration):
    def __init__(self,path,protocol):
        super().__init__(path)
        del self.hooks[self.symbols['syna_tcm_get_event_data']]
        self.protocol=protocol;self.fragments=[];self.reads=[];self.boundaries=[]
        self.allocation_count=0;self.allocation_error=0;self.allocations=[]
        self.completed=[];self.waits=[];self.command_requests=[]
        self.v2_error=0;self.payload=b'';self.report=0x11;self.source_capacity=None
        self.response_status=0
        self.put32(READ_CALLBACK-4,0xcc41658f)
        self.hooks[READ_CALLBACK]='fixture_transport_read'
        self.put64(CORE+0x38,HW);self.put64(HW+0x118,READ_CALLBACK)
        self.put64(CORE+0x330,self.symbols[f'syna_tcm_v{protocol}_read_message'])
        if protocol==2:self.intercept('syna_tcm_v2_execute_cmd_request')

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(7)]
        if name=='fixture_transport_read':
            assert self.fragments,('unexpected transport read',args,self.calls)
            response=self.fragments.pop(0)
            if isinstance(response,int):result=response;payload=None
            else:
                assert len(response)==args[2],('fragment length',len(response),args)
                uc.mem_write(args[1],response);result=len(response);payload=response.hex()
            self.reads.append(dict(length=args[2],payload=payload,result=result))
        elif name=='devm_kmalloc':
            self.allocation_count+=1;self.allocations.append(args[1])
            assert 0<args[1]<=0x10000
            if self.allocation_count==self.allocation_error:result=0
            else:
                result=self.alloc_cursor;self.alloc_cursor+=(args[1]+4095)&~4095
                assert self.alloc_cursor<0x4200000
                uc.mem_write(result,b'\0'*args[1])
        elif name=='syna_tcm_v2_execute_cmd_request':
            assert args[1:5]==[10,0,0,0]
            self.command_requests.append(args[:5]);result=self.v2_error
            if result==0:
                data_address=0x4078000
                uc.mem_write(data_address,b'\0'*4+self.payload+b'\0'*16)
                self.put64(CORE+0x208,data_address)
                self.put32(CORE+0x210,self.source_capacity if self.source_capacity is not None else len(self.payload)+4)
                self.put32(CORE+0x1d8,len(self.payload))
                uc.mem_write(CORE+0x1d5,bytes([self.report]))
                uc.mem_write(CORE+0x1dc,bytes([self.response_status]))
        elif name=='usleep_range_state':self.waits.append(args[:3]);result=0
        elif name=='complete':self.completed.append(args[0]);result=0
        else:return super().on_code(uc,address,size,data)
        self.calls.append(name);self.boundaries.append(dict(name=name,args=args,result=result))
        uc.reg_write(UC_ARM64_REG_X0,result&MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def frame(self,report=0x11,payload=None,limit=0):
        self.report=report
        self.payload=payload if payload is not None else struct.pack('<BBHHBB',0,1,644,1589,7,6)
        self.put32(CORE+0x30,limit)
        if self.protocol==1:
            self.fragments=[bytes([0xa5,report])+struct.pack('<H',len(self.payload))]
            remaining=self.payload+b'\x5a'
            while remaining:
                size=min(limit-2,len(remaining)) if limit else len(remaining)
                assert size>0
                if size!=1:self.fragments.append(b'\xa5\x03'+remaining[:size])
                remaining=remaining[size:]

    def event(self):return self.run('syna_tcm_get_event_data',CORE,EVENT_ID,OUTPUT)


def exercise(path):
    cases=[]
    def passed(label,m,result,**details):
        assert all(m.uc.mem_read(CORE+i,1)==b'\0' for i in [0xf8,0x138,0x178,0x240,0x2c0])
        cases.append(dict(case=label,status='PASS',result=result,reads=m.reads,
                          allocations=m.allocations,completed=m.completed,waits=m.waits,
                          report_id=bytes(m.uc.mem_read(EVENT_ID,1)).hex(),
                          report_length=m.u32(CORE+0xcc),output_length=m.u32(OUTPUT+12),
                          isr_output_length=m.u32(CTX+0x2cc),
                          command_state=m.u32(CORE+0x1d0),
                          events=m.events,slots=m.slots,raw_frames=m.raw_frames,
                          boundaries=m.boundaries,**details))
    for protocol in [1,2]:
        for label in ['normal','raw-report','unknown-report','empty-report','read-error',
                      'invalid-marker','transient-marker','bad-continuation','fragmented',
                      'allocation-input','allocation-payload','allocation-report','allocation-output',
                      'no-config','null-core','null-code','no-output','no-input',
                      'ISR-press-release','ISR-read-error','ISR-raw-report']:
            if protocol==2 and label in ['invalid-marker','transient-marker','bad-continuation','fragmented','allocation-input']:continue
            m=Message(path,protocol)
            assert m.acquire()==0
            m.allocation_count=0;m.allocations=[];m.calls=[]
            report=0xc0 if label in ['raw-report','ISR-raw-report'] else 0x12 if label=='unknown-report' else 0x11
            m.frame(report,b'' if label=='empty-report' else None,6 if label=='fragmented' else 0)
            if label in ['read-error','ISR-read-error']:
                if protocol==1:m.fragments=[-110]
                else:m.v2_error=-110
            if label=='invalid-marker':m.fragments=[b'\0'*4]*20
            if label=='transient-marker':m.fragments=[b'\0'*4]*2+m.fragments
            if label=='bad-continuation':m.fragments[1]=b'\xa5\x02'+m.fragments[1][2:]
            if label.startswith('allocation-'):
                offset=1 if protocol==1 else 0
                m.allocation_error={'allocation-input':1,'allocation-payload':offset+1,
                                    'allocation-report':offset+2,'allocation-output':offset+3}[label]
            if label=='no-config':m.put32(CORE+0x18c,0)
            if label=='no-input':m.put64(CTX+0x3b8,0)
            if label=='ISR-raw-report':m.uc.mem_write(CTX+0x6ac,b'\1')
            if label.startswith('ISR-') or label in ['no-config','no-input']:
                rc=m.run('syna_dev_isr',0,CTX)
                assert rc==1
                if label=='ISR-press-release':
                    assert [INPUT,3,53,64400] in m.events and [INPUT,3,54,158900] in m.events
                    m.events=[];m.slots=[]
                    m.frame(payload=struct.pack('<BBHHBB',0,0,644,1589,0,0))
                    assert m.run('syna_dev_isr',0,CTX)==1
                    assert [INPUT,0,0,0] in m.events and any(s[2]==0 for s in m.slots)
                elif label in ['no-config','no-input','ISR-read-error']:
                    assert not m.events and not m.slots
                else:assert m.raw_frames and not m.events
            else:
                rc=m.run('syna_tcm_get_event_data',0 if label=='null-core' else CORE,
                         0 if label=='null-code' else EVENT_ID,0 if label=='no-output' else OUTPUT)
                if label in ['null-core','null-code']:assert rc==-241
                elif protocol==2 and label=='allocation-report':
                    # dispatch_report is void: allocation failure is logged but
                    # read_message/get_event_data still return zero, with no data.
                    assert rc==0 and m.u32(CORE+0xcc)==m.u32(OUTPUT+12)==0
                    assert m.allocation_count==m.allocation_error==2
                elif label in ['read-error','invalid-marker','bad-continuation'] or label.startswith('allocation-'):
                    assert rc<0,(protocol,label,rc,m.calls)
                else:
                    assert rc==0,(protocol,label,rc,m.calls)
                    assert bytes(m.uc.mem_read(EVENT_ID,1))==bytes([report])
                    if label not in ['no-output','empty-report']:
                        assert m.u32(OUTPUT+12)==len(m.payload)
                        assert bytes(m.uc.mem_read(m.u64(OUTPUT),len(m.payload)))==m.payload
            if label in ['normal','raw-report','unknown-report','fragmented','transient-marker','ISR-press-release']:
                assert not m.fragments
            if label=='invalid-marker':assert len(m.reads)==20 and len(m.waits)==20
            if label=='transient-marker':assert len(m.reads)==4 and len(m.waits)==3
            passed(f'v{protocol}-{label}',m,rc)
        # Reuse populated original buffers: a fresh zeroed context would hide
        # stale output lengths and the ISR's replay of an earlier touch packet.
        for label in ['reuse-empty','ISR-reuse-empty','pending-command-read-error',
                      'status4-suppressed-dispatch','short-source-buffer']:
            if protocol==1 and label in ['status4-suppressed-dispatch','short-source-buffer']:continue
            m=Message(path,protocol);assert m.acquire()==0;m.frame()
            is_isr=label.startswith('ISR-')
            assert (m.run('syna_dev_isr',0,CTX) if is_isr else m.event())==(1 if is_isr else 0)
            first_events=m.events.copy();m.events=[];m.slots=[]
            m.frame(payload=b'' if label in ['reuse-empty','ISR-reuse-empty'] else None)
            if label=='pending-command-read-error':
                m.put32(CORE+0x1d0,1)
                if protocol==1:m.fragments=[-110]
                else:m.v2_error=-110
            if label=='status4-suppressed-dispatch':m.response_status=4
            if label=='short-source-buffer':m.source_capacity=4
            rc=m.run('syna_dev_isr',0,CTX) if is_isr else m.event()
            if label=='ISR-reuse-empty':
                assert rc==1 and m.u32(CORE+0xcc)==0 and m.u32(CTX+0x2cc)==8
                assert m.events==first_events and m.slots==[[INPUT,0,1]]
            elif label=='reuse-empty':
                assert rc==0 and m.u32(CORE+0xcc)==0 and m.u32(OUTPUT+12)==8
                assert bytes(m.uc.mem_read(m.u64(OUTPUT),8))==struct.pack('<BBHHBB',0,1,644,1589,7,6)
            elif label=='pending-command-read-error':
                assert rc==-110 and m.u32(CORE+0x1d0)==0xffffffff
                assert m.completed==[CORE+0x1e8] and m.u32(OUTPUT+12)==8
                assert bytes(m.uc.mem_read(EVENT_ID,1))==b'\xff'
            elif label=='status4-suppressed-dispatch':
                assert rc==0 and bytes(m.uc.mem_read(EVENT_ID,1))==b'\xff'
                assert m.u32(CORE+0xcc)==m.u32(OUTPUT+12)==8
            else:assert rc==-22 and bytes(m.uc.mem_read(EVENT_ID,1))==b'\xff'
            passed(f'v{protocol}-{label}',m,rc,initial_events=first_events)
    return cases


def main():
    cases=[];drivers={};sources={}
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    functions=['syna_tcm_v1_read_message','syna_tcm_v1_continued_read','syna_tcm_v1_read',
               'syna_tcm_v2_read_message','syna_tcm_get_event_data','syna_tcm_buf_copy',
               'syna_tcm_v2_dispatch_report','syna_tcm_v2_dispatch_response','syna_dev_isr']
    for sample in ['os4-current','os4-stable']:
        path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        assert sha(path) in LAYOUTS;drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        disasm=ROOT/'logs'/f'{sample}-touch-message.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols='+','.join(functions),str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        results=exercise(path)
        for case in results:case['sample']=sample;cases.append(case)
        print('PASS',sample,len(results),'message/event/ISR cases',flush=True)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/name for name in ['touch_configuration_emulation.py',
           'touch_startup_emulation.py','haptics_driver_emulation.py','haptics-emulator-dependencies.json']]
    dependencies=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-message-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in dependencies}),indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
