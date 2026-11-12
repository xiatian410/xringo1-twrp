#!/usr/bin/env python3
"""Execute original OS4 app-info/configuration/IRQ/probe and parser functions.

Controller commands provide explicit synthetic responses, never phone data.
Kernel allocation, IRQ, GPIO and panel/cdev registration are fixtures; original
CFI checks execute. Probe uses the original connect function and original
app-info/config acquisition, but panel setup and disconnect cleanup are hooks.
No real SPI, kernel boot, driver bind, calibration or physical touch is tested.
"""
import json
from pathlib import Path
import struct

from touch_startup_emulation import Interrupt, CTX, CORE, HW, INPUT, FW, PLATFORM, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

CONFIG = bytes([6,8,7,8,8,16,9,16,11,8,12,8,0])
RESPONSE, SAVED = FW+0x5000, FW+0x6000


class Configuration(Interrupt):
    def __init__(self,path):
        super().__init__(path)
        for name in ['syna_tcm_get_app_info','syna_tcm_preserve_touch_report_config',
                     'syna_tcm_parse_touch_report','syna_dev_request_irq']:
            del self.hooks[self.symbols[name]]
        self.commands, self.irq_requests, self.frees = [], [], []
        self.config=CONFIG
        self.command_error=0
        self.config_command_error=0
        self.response_capacity=4096
        self.response_null=False
        self.alloc_fail=False
        self.managed=PLATFORM
        self.irq_result=0
        self.irq_number=76
        self.app_status=0
        self.object_count=10
        self.app_length=48
        self.intercept('syna_request_managed_device')
        self.put64(PLATFORM+0xa0,HW)
        # Correct type hash for the original indirect send_command boundary.
        address=0x300d000
        self.put32(address-4,0x79ed098b)
        self.hooks[address]='fixture_send_command'
        self.put64(CORE+0x340,address)
        self.put32(HW+0x58,76)
        self.put64(HW+0x60,0x2002)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(7)]
        if name=='fixture_send_command':
            self.commands.append(args)
            if args[1]==0x25: response=self.config
            elif args[1]==0x20:
                response=bytearray(48)
                struct.pack_into('<H',response,2,self.app_status)
                struct.pack_into('<HHH',response,32,1440,3200,self.object_count)
                struct.pack_into('<HH',response,40,17,38)
                response=bytes(response[:self.app_length])
            else: raise AssertionError(('unexpected command',args))
            self.uc.mem_write(RESPONSE,response or b'\0')
            self.put64(CORE+0x100,0 if self.response_null else RESPONSE)
            self.put32(CORE+0x108,self.response_capacity)
            self.put32(CORE+0x10c,len(response))
            self.uc.mem_write(args[5],b'\1')
            result=self.command_error or (self.config_command_error if args[1]==0x25 else 0)
        elif name=='syna_request_managed_device': result=self.managed
        elif name=='devm_kmalloc': result=0 if self.alloc_fail else SAVED
        elif name=='devm_kfree':
            self.frees.append(args[1]); result=0
        elif name in ['memcpy','memset']:
            assert args[2]<=4096
            blob=bytes(uc.mem_read(args[1],args[2])) if name=='memcpy' else bytes([args[1]&255])*args[2]
            if blob: uc.mem_write(args[0],blob)
            result=args[0]
        elif name=='gpiod_to_irq': result=self.irq_number
        elif name=='devm_request_threaded_irq':
            self.irq_requests.append(args)
            result=self.irq_result
        elif name=='dev_pm_qos_add_request': result=0
        else: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))

    def acquire(self): return self.run('syna_tcm_preserve_touch_report_config',CORE)


class Probe(Configuration):
    def __init__(self,path):
        super().__init__(path)
        self.allocate_error=0
        self.core_null=False
        self.probe_alloc_fail=False
        self.cdev_error=0
        self.cleaned=[]
        self.allocated=[]
        for name in ['syna_tcm_allocate_device','syna_cdev_create','syna_dev_disconnect',
                     'syna_tcm_remove_device','syna_tcm_set_reset_occurrence_callback',
                     'syna_tcm_change_resp_read']:
            self.intercept(name)
        # Probe must initialize context, not inherit an artificially ready input.
        self.uc.mem_write(CTX,b'\0'*0x750)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(5)]
        if name=='devm_kmalloc' and args[1]==0x750:
            result=0 if self.probe_alloc_fail else CTX
        elif name=='syna_tcm_allocate_device':
            self.allocated.append(args[:3])
            self.put64(args[0],0 if self.core_null else CORE)
            result=self.allocate_error
        elif name=='syna_cdev_create': result=self.cdev_error
        elif name in ['syna_dev_disconnect','syna_tcm_remove_device','debugfs_remove']:
            self.cleaned.append(name);result=0
        elif name in ['device_set_wakeup_capable','device_wakeup_enable',
                      '__init_swait_queue_head','syna_tcm_set_reset_occurrence_callback',
                      'syna_tcm_change_resp_read']: result=0
        else: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


def exercise(path):
    cases=[]
    def passed(name,**details):cases.append(dict(case=name,status='PASS',**details))
    m=Configuration(path)
    assert m.run('syna_tcm_get_app_info',CORE,CORE+0x70)==0
    assert [m.u32(CORE+i) for i in [8,12,16,20,24]]==[1440,3200,10,17,38]
    assert m.commands[0][1]==0x20
    passed('original-app-info-decoding')
    for label,change in [('status',1),('object-clamp',15),('empty',0)]:
        m=Configuration(path)
        if label=='status':m.app_status=change
        if label=='object-clamp':m.object_count=change
        if label=='empty':m.app_length=change
        rc=m.run('syna_tcm_get_app_info',CORE,CORE+0x70)
        if label=='status':assert rc<0
        else:
            expected=(10 if LAYOUTS[sha(path)]=='os4-stable' else 15) if label=='object-clamp' else 0
            assert rc==0 and m.u32(CORE+16)==expected
        passed('original-app-info-'+label,result=rc,objects=m.u32(CORE+16))
    m=Configuration(path);assert m.acquire()==0
    assert m.commands[0][1]==0x25 and m.u32(CORE+0x18c)==len(CONFIG)
    assert bytes(m.uc.mem_read(m.u64(CORE+0x180),len(CONFIG)))==CONFIG
    packet=FW+0x4000;m.uc.mem_write(packet,struct.pack('<BBHHBB',0,1,644,1589,7,6))
    assert m.run('syna_tcm_parse_touch_report',CORE,packet,8,CTX+0x10)==0
    assert m.u32(CTX+0x1c)==644 and m.u32(CTX+0x20)==1589
    # Original config acquisition -> original parser -> original IRQ emission.
    m.put64(CTX+0x2c0,packet);m.put32(CTX+0x2cc,8)
    assert m.run('syna_dev_isr',0,CTX)==1
    assert [INPUT,3,53,64400] in m.events and [INPUT,3,54,158900] in m.events
    passed('acquire-parser-ISR',synthetic_controller_response=True)
    m=Configuration(path);m.put64(CORE+0x180,SAVED);m.put32(CORE+0x188,100)
    assert m.acquire()==0 and not m.frees
    passed('reuse-config-capacity')
    m=Configuration(path);m.put64(CORE+0x180,SAVED);m.put32(CORE+0x188,100);m.config=b''
    assert m.acquire()==0 and m.u32(CORE+0x18c)==0
    assert m.run('syna_tcm_parse_touch_report',CORE,FW,1,CTX+0x10)<0
    passed('empty-config-reused-buffer-success-parser-failure')
    m=Configuration(path);m.put64(CORE+0x180,SAVED+0x1000);m.put32(CORE+0x188,1)
    assert m.acquire()==0 and m.frees==[SAVED+0x1000]
    passed('grow-config-capacity')
    for name in ['command-error','no-device','allocation-error','null-response','short-response','empty-config','bootloader','no-core']:
        m=Configuration(path)
        if name=='command-error':m.command_error=-110
        if name=='no-device':m.managed=0
        if name=='allocation-error':m.alloc_fail=True
        if name=='null-response':m.response_null=True
        if name=='short-response':m.response_capacity=1
        if name=='empty-config':m.config=b''
        if name=='bootloader':m.uc.mem_write(CORE+1,b'\x0b')
        rc=m.run('syna_tcm_preserve_touch_report_config',0 if name=='no-core' else CORE)
        if name=='empty-config':
            assert rc<0  # No allocated pointer for a zero length initial response.
        else:assert rc<0
        assert m.u32(CORE+0x18c)==0
        passed('config-'+name,result=rc)
    for name in ['normal','missing-device','bad-gpio','irq-request-failure']:
        m=Configuration(path)
        if name=='missing-device':m.managed=0
        if name=='bad-gpio':m.put32(HW+0x58,-1)
        if name=='irq-request-failure':m.irq_result=-16
        rc=m.run('syna_dev_request_irq',CTX)
        assert (rc==0)==(name=='normal')
        if name in ['normal','irq-request-failure']:
            assert m.irq_requests[0][1:5]==[76,0,m.symbols['syna_dev_isr'],0x2002]
            assert m.irq_requests[0][6]==CTX
        else:assert not m.irq_requests
        assert bytes(m.uc.mem_read(HW+0x6c,1))==bytes([int(rc==0)])
        passed('IRQ-'+name,result=rc)
    for name in ['normal','missing-platform-data','allocation-failure','core-failure','null-core-success',
                 'connect-failure','config-command-failure','cdev-failure']:
        m=Probe(path)
        if name=='missing-platform-data':m.put64(PLATFORM+0xa0,0)
        if name=='allocation-failure':m.probe_alloc_fail=True
        if name=='core-failure':m.allocate_error=-12
        if name=='null-core-success':m.core_null=True
        if name=='connect-failure':m.results['fixture_setup']=-517
        if name=='config-command-failure':m.config_command_error=-110
        if name=='cdev-failure':m.cdev_error=-5
        rc=m.run('syna_dev_probe',PLATFORM)
        if name in ['normal','null-core-success','config-command-failure']:assert rc==0,(name,rc)
        else:assert rc<0,(name,rc)
        if name=='normal':
            assert m.u64(PLATFORM+0xa8)==CTX and m.u64(CTX)==CORE
            assert m.u32(CORE+0x18c)==len(CONFIG) and m.irq_requests and m.queued
            assert not m.inputs and m.u64(CTX+0x3b8)==0
            m.run('syna_dev_reflash_startup_work',CTX+0x3d0)
            assert m.inputs==[[0,143999,319999,64]] and m.u64(CTX+0x3b8)==INPUT
            packet=FW+0x4000
            m.uc.mem_write(packet,struct.pack('<BBHHBB',0,1,644,1589,7,6))
            m.put64(CTX+0x2c0,packet);m.put32(CTX+0x2cc,8)
            assert m.run('syna_dev_isr',0,CTX)==1
            assert [INPUT,3,53,64400] in m.events and [INPUT,3,54,158900] in m.events
            passed('probe-connect-config-background-parser-ISR',synthetic_controller_response=True)
        if name=='config-command-failure':assert m.queued and not m.inputs and m.u32(CORE+0x18c)==0
        if name=='null-core-success':assert not m.irq_requests and not m.queued
        if name=='cdev-failure':assert m.cleaned[:2]==['syna_tcm_remove_device','syna_dev_disconnect']
        passed('probe-'+name,result=rc,queued_work=len(m.queued),irq_requests=len(m.irq_requests),input_requests=len(m.inputs))
    for recovered in [False,True]:
        m=Probe(path);m.config_command_error=-110
        assert m.run('syna_dev_probe',PLATFORM)==0 and m.u32(CORE+0x18c)==0
        if recovered:
            m.config_command_error=0;m.uc.mem_write(CORE+1,b'\1')
        m.run('syna_dev_reflash_startup_work',CTX+0x3d0)
        assert m.inputs==[[0,143999,319999,64]]
        packet=FW+0x4000
        m.uc.mem_write(packet,struct.pack('<BBHHBB',0,1,644,1589,7,6))
        m.put64(CTX+0x2c0,packet);m.put32(CTX+0x2cc,8)
        m.run('syna_dev_isr',0,CTX)
        assert bool(m.events)==recovered
        assert bool(m.u32(CORE+0x18c))==recovered
        passed('probe-background-config-'+('recovered' if recovered else 'still-missing'),
               input_registered=True,event_output=bool(m.events),
               application_mode_restored_by_fixture=recovered)
    return cases


def main():
    cases,drivers=[],{}
    for sample in ['os4-current','os4-stable']:
        path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        current=exercise(path);cases.extend(dict(sample=sample,**c) for c in current)
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        print('PASS',sample,len(current),'cases',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/touch_startup_emulation.py',
           ROOT/'tests/haptics_driver_emulation.py',ROOT/'tests/haptics-emulator-dependencies.json']
    sources=[ROOT/'logs'/f'{s}-touch-config.disasm' for s in drivers]
    report=dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                sources={str(p.relative_to(ROOT)):sha(p) for p in sources},
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in sorted(DEPS.rglob('*'))
                                if p.is_file() and p.suffix in ('.py','.so')})
    (ROOT/'logs/touch-configuration-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':main()
