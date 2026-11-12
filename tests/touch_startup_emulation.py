#!/usr/bin/env python3
"""Run exact stock OS4 ARM64 connect, report-mode, reflash, ISR and parser.

SPI, firmware request/update, IRQ, Xiaomi panel/input registration and kernel
services are explicit fixtures. ISR tests use either a decoded-object fixture
or the original parser with synthetic configuration/packets. Does not emulate
probe, a controller, a booted kernel or real touch. Unknown boundaries and
execution-budget exhaustion fail.
"""
import json
from pathlib import Path
import struct

from haptics_driver_emulation import Module, ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

CTX, CORE, HW, INPUT, FW, PLATFORM, WQ = [0x4000000+i*0x10000 for i in range(7)]
LAYOUTS = {
    'dc2b7631bdac52d6c2152abb465aab7842e232da1bbf20958113b6c26d94b7bf': 'os4-current',
    '8fecca0cfad0cdef274356a28dc3f06ee9f8025ba244d313ee9bf8d1f58ffc3f': 'os4-stable',
}


class Touch(Module):
    def __init__(self, path):
        assert sha(path) in LAYOUTS, 'unanalyzed touch layout'
        super().__init__(path)
        self.results = {}
        self.reports, self.updates, self.inputs, self.queued = [], [], [], []
        self.requests, self.released, self.power = [], [], []
        self.prints = []
        self.report_results, self.update_results = [], [0]
        self.request_error = 0
        self.put64(CTX, CORE)
        self.put64(CTX+8, PLATFORM)
        self.put64(CTX+0x300, HW)
        self.uc.mem_write(CORE+1, b'\1')
        self.uc.mem_write(CORE+0x86, b'07')
        self.put64(FW, 128)
        self.put64(FW+8, FW+0x1000)
        bss = next(i for i,s in enumerate(self.sections) if s.name == '.bss')
        self.put64(self.bases[bss]+0x1868, CTX)
        # Values normally populated by the Xiaomi panel setup boundary.
        self.put32(self.bases[bss]+0x1874,1440)
        self.put32(self.bases[bss]+0x1878,3200)
        self.put32(self.bases[bss]+0x18ac,100)
        # Original indirect calls execute their CFI signature comparisons.
        for offset, name, signature in [(0x128,'fixture_power',0x5f30282b),
                                        (0x148,'fixture_setup',0xe426c340),
                                        (0x130,'fixture_reset',0x4e021508)]:
            address = 0x300e000+offset*16
            self.put32(address-4, signature)
            self.hooks[address] = name
            self.put64(HW+offset,address)
        for name in ['syna_tcm_detect_device','syna_tcm_get_app_info',
                     'syna_tcm_preserve_touch_report_config','syna_dev_request_irq',
                     'syna_xiaomi_touch_probe','syna_tcm_switch_fw_mode',
                     'syna_tcm_enable_report','syna_tcm_do_fw_update',
                     'syna_dev_free_input_events','xiaomi_get_firmware_image_name']:
            self.intercept(name)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        if name is None: return
        args = [self.arg(i) for i in range(5)]
        self.calls.append(name)
        if name == '_printk':
            self.prints.append(self.string(args[0]))
            result = 0  # void callers do not use this value
        elif name in ['fixture_power','fixture_reset','fixture_setup']:
            if name == 'fixture_power': self.power.append(args[1])
            result = self.results.get(name,0)
        elif name == 'syna_tcm_detect_device': result = self.results.get(name,1)
        elif name == 'syna_tcm_switch_fw_mode':
            self.uc.mem_write(CORE+1,bytes([args[1]]))
            result = self.results.get(name,0)
        elif name in ['syna_tcm_get_app_info','syna_tcm_preserve_touch_report_config',
                      'syna_dev_request_irq','syna_xiaomi_touch_probe']:
            result = self.results.get(name,0)
        elif name in ['__mutex_init','timer_init_key','mutex_lock','mutex_unlock',
                      'syna_dev_free_input_events','pm_stay_awake','pm_relax',
                      'xiaomi_touch_mievent_report_int','xiaomi_touch_mievent_report_str',
                      'unregister_xiaomi_input_dev']:
            result = 0
        elif name == 'alloc_workqueue_noprof': result = WQ
        elif name == 'queue_delayed_work_on':
            self.queued.append(args[:4])
            result = 1
        elif name == 'syna_tcm_enable_report':
            self.reports.append(args[:3])
            result = self.report_results.pop(0) if self.report_results else 0
        elif name == 'xiaomi_get_firmware_image_name':
            result = FW+0x2000
            self.uc.mem_write(result,b'synaptics_spi_dijun.img\0')
        elif name == 'request_firmware':
            self.requests.append(self.string(args[1]))
            self.put64(args[0],0 if self.request_error else FW)
            result = self.request_error
        elif name == 'release_firmware':
            self.released.append(args[0]); result = 0
        elif name == 'syna_tcm_do_fw_update':
            self.updates.append(args)
            assert self.update_results, 'unexpected extra update attempt'
            result = self.update_results.pop(0)
        elif name == 'register_xiaomi_input_dev':
            self.inputs.append(args[:4]); result = INPUT
        else: raise AssertionError(('unhandled touch boundary', name, args))
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


class Interrupt(Touch):
    """Original ISR, with an explicit decoded-object fixture at parser boundary."""
    def __init__(self,path):
        super().__init__(path)
        self.events, self.slots, self.raw_frames = [], [], []
        self.report_id=0x11
        self.parse_error=self.read_error=0
        self.lock_available=1
        self.gpio_value=0
        self.finger=1
        self.put64(CTX+0x3b8,INPUT)
        self.put32(CTX+0x450,1)
        self.put32(CORE+0x10,10)
        for name in ['syna_tcm_get_event_data','syna_tcm_parse_touch_report',
                     'syna_tcm_report_thp_frame']:
            self.intercept(name)

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        args=[self.arg(i) for i in range(5)]
        if name=='ktime_get': result=123456789
        elif name in ['sched_setscheduler_nocheck','dev_pm_qos_remove_request']: result=0
        elif name=='mutex_trylock': result=self.lock_available
        elif name=='gpio_to_desc': result=HW+0x800
        elif name=='gpiod_get_raw_value': result=self.gpio_value
        elif name=='xiaomi_get_sensorhub_status': result=0
        elif name=='syna_tcm_get_event_data':
            self.uc.mem_write(args[1],bytes([self.report_id]))
            result=self.read_error
        elif name=='syna_tcm_parse_touch_report':
            # No claim of parsing an actual controller packet: the parser result
            # is a controlled boundary; ISR slot/coordinate emission is original.
            self.uc.mem_write(args[3]+8,bytes([self.finger]))
            self.uc.mem_write(args[3]+12,struct.pack('<IIII',644,1589,7,6))
            result=self.parse_error
        elif name=='syna_tcm_report_thp_frame':
            self.raw_frames.append(args[:2]); result=0
        elif name=='input_event':
            self.events.append(args[:4]); result=0
        elif name=='input_mt_report_slot_state':
            self.slots.append(args[:3]); result=0
        else: return super().on_code(uc,address,size,data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0,result & MASK)
        uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))


class ParsedInterrupt(Interrupt):
    """Use the original parser with an explicitly synthetic report configuration."""
    def __init__(self,path):
        super().__init__(path)
        del self.hooks[self.symbols['syna_tcm_parse_touch_report']]
        self.config=FW+0x3000
        self.packet=FW+0x4000
        # Object index, classification, X/Y, width X/Y, END. Configuration is
        # synthetic, not claimed to have been read from a real touch controller.
        self.uc.mem_write(self.config,bytes([6,8,7,8,8,16,9,16,11,8,12,8,0]))
        self.put64(CORE+0x180,self.config)
        self.put32(CORE+0x18c,13)
        self.put64(CTX+0x2c0,self.packet)
        self.put32(CTX+0x2cc,8)
        self.uc.mem_write(self.packet,struct.pack('<BBHHBB',0,1,644,1589,7,6))

    def on_code(self,uc,address,size,data):
        name=self.hooks.get(address)
        if name=='memset':
            args=[self.arg(i) for i in range(3)]
            assert args[2]<=4096
            self.uc.mem_write(args[0],bytes([args[1]&255])*args[2])
            self.calls.append(name)
            uc.reg_write(UC_ARM64_REG_X0,args[0])
            uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_X30))
        else: super().on_code(uc,address,size,data)


def exercise(path):
    cases=[]
    def passed(name,**details): cases.append(dict(case=name,status='PASS',**details))
    for enabled in [0,1]:
        expected = [[CORE,0xc0,0],[CORE,0x11,1]] if not enabled else [[CORE,0x11,0],[CORE,0xc0,1]]
        for failures in [[0,0],[-5,0],[0,-110],[-5,-110]]:
            m=Touch(path);m.report_results=failures.copy()
            rc=m.run('syna_tcm_enable_touch_raw',enabled)
            assert rc==failures[1] and m.reports==expected
            assert bytes(m.uc.mem_read(CTX+0x6ac,1))==bytes([enabled])
            passed(f'report-mode-{enabled}-{failures}',result=rc,commands=m.reports,
                   first_failure_masked=failures[0]<0 and rc==0)
    m=Touch(path)
    bss=next(i for i,s in enumerate(m.sections) if s.name=='.bss')
    m.put64(m.bases[bss]+0x1868,0)
    assert m.run('syna_tcm_enable_touch_raw',0)==-22 and not m.reports
    passed('report-mode-no-context')
    for name,changes,expected in [
        ('normal',{},0),('setup-defer',{'fixture_setup':-517},-517),
        ('power-error',{'fixture_power':-5},-19),
        ('detect-error',{'syna_tcm_detect_device':-5},-5),
        ('irq-error',{'syna_dev_request_irq':-5},-5),
        ('app-info-error',{'syna_tcm_get_app_info':-5},0),
        ('config-error',{'syna_tcm_preserve_touch_report_config':-5},0),
        ('panel-error',{'syna_xiaomi_touch_probe':-5},0)]:
        m=Touch(path);m.results=changes
        assert m.run('syna_dev_connect',CTX)==expected
        assert not m.inputs and m.u64(CTX+0x3b8)==0
        if expected==0:
            assert m.queued==[[32,WQ,CTX+0x3d0,50]]
            assert m.u64(CTX+0x3e8)==m.symbols['syna_dev_reflash_startup_work']
            assert bytes(m.uc.mem_read(CTX+0x457,1))==b'\1'
        else: assert not m.queued
        if name in ['detect-error','irq-error']: assert m.power==[1,0]
        if name in ['app-info-error','config-error']:
            assert 'syna_tcm_switch_fw_mode' in m.calls
        passed('connect-'+name,result=expected,delayed_work=m.queued,input_registered=False)
    m=Touch(path);m.put32(CTX+0x450,3)
    assert m.run('syna_dev_connect',CTX)==0 and not m.queued and not m.inputs
    passed('connect-state-3-no-work-or-input')
    m=Touch(path);m.uc.mem_write(CTX+0x457,b'\1')
    assert m.run('syna_dev_connect',CTX)==0 and not m.queued and not m.power
    passed('connect-already-connected-no-retry')
    m=Touch(path);m.put64(CTX,0)
    assert m.run('syna_dev_connect',CTX)==-22 and not m.power
    passed('connect-no-core')
    for name,request,updates,app_error,mode in [
        ('normal',0,[0],0,1),('missing-firmware',-2,[],0,1),
        ('denied-firmware',-13,[],0,1),('update-retry',0,[-5,-5,0],0,1),
        ('update-exhausted',0,[-5,-5,-5],0,1),
        ('app-info-error',0,[0],-5,1),('missing-firmware-bootloader',-2,[],0,11)]:
        m=Touch(path);m.request_error=request;m.update_results=updates.copy()
        m.results['syna_tcm_get_app_info']=app_error
        m.uc.mem_write(CORE+1,bytes([mode]))
        # Execute the original delayed worker AND original reflash body.
        # A registration fixture returns an allocated input; no real probe.
        m.run('syna_dev_reflash_startup_work',CTX+0x3d0)
        assert m.inputs==[[0,143999,319999,64]]
        assert m.u64(CTX+0x3b8)==INPUT and m.u64(INPUT+0x2c0)==CTX
        assert m.requests==['synaptics_spi_dijun.img']
        assert len(m.updates)==len(updates)
        assert m.released==([] if request else [FW])
        assert not m.reports, 'reflash must not be assumed to restore normal report mode'
        passed('reflash-'+name,update_attempts=len(m.updates),input_request=m.inputs,
               normal_report_reenabled=False,controller_mode_fixture=mode)
    for name in ['normal','raw-flag-normal-report','raw-frame','raw-frame-disabled',
                 'unknown-report','read-error','parse-error','no-input','TUI-active',
                 'mutex-busy','gpio-inactive']:
        m=Interrupt(path)
        if name in ['raw-flag-normal-report','raw-frame']: m.uc.mem_write(CTX+0x6ac,b'\1')
        if name in ['raw-frame','raw-frame-disabled']: m.report_id=0xc0
        if name=='unknown-report': m.report_id=0x77
        if name=='read-error': m.read_error=-5
        if name=='parse-error': m.parse_error=-22
        if name=='no-input': m.put64(CTX+0x3b8,0)
        if name=='TUI-active': m.uc.mem_write(m.symbols['xiaomi_driver_data']+0x30,b'\1')
        if name=='mutex-busy': m.lock_available=0
        if name=='gpio-inactive': m.gpio_value=1
        assert m.run('syna_dev_isr',0,CTX)==1
        if name in ['normal','raw-flag-normal-report']:
            assert [INPUT,3,53,64400] in m.events and [INPUT,3,54,158900] in m.events
            assert [INPUT,1,330,1] in m.events and m.events[-1]==[INPUT,0,0,0]
            assert m.slots==[[INPUT,0,1]]
            m.finger=0;m.events.clear();m.slots.clear()
            m.run('syna_dev_isr',0,CTX)
            assert [INPUT,1,330,0] in m.events and m.slots==[[INPUT,0,0]]
            passed('ISR-'+name,press_release=True,x=64400,y=158900)
        else:
            assert not m.events and not m.slots
            assert bool(m.raw_frames)==(name=='raw-frame')
            if name in ['TUI-active','mutex-busy','gpio-inactive']:
                assert 'syna_tcm_get_event_data' not in m.calls
            passed('ISR-'+name,input_events=0,raw_frames=len(m.raw_frames))
    m=ParsedInterrupt(path)
    assert m.run('syna_tcm_parse_touch_report',CORE,m.packet,8,CTX+0x10)==0
    assert bytes(m.uc.mem_read(CTX+0x18,1))==b'\1'
    assert [m.u32(CTX+offset) for offset in [0x1c,0x20,0x24,0x28]]==[644,1589,7,6]
    passed('original-parser-synthetic-config',x=644,y=1589)
    assert m.run('syna_dev_isr',0,CTX)==1
    assert [INPUT,3,53,64400] in m.events and [INPUT,3,54,158900] in m.events
    m.uc.mem_write(m.packet+1,b'\0');m.events.clear();m.slots.clear()
    m.run('syna_dev_isr',0,CTX)
    assert [INPUT,1,330,0] in m.events and m.slots==[[INPUT,0,0]]
    passed('original-parser-ISR-press-release',synthetic_packet=True)
    for name,argchange in [('no-core',0),('no-report',1),('no-output',3)]:
        m=ParsedInterrupt(path);args=[CORE,m.packet,8,CTX+0x10];args[argchange]=0
        assert m.run('syna_tcm_parse_touch_report',*args)<0
        passed('original-parser-'+name)
    m=ParsedInterrupt(path);m.put64(CORE+0x180,0)
    assert m.run('syna_tcm_parse_touch_report',CORE,m.packet,8,CTX+0x10)<0
    passed('original-parser-no-config')
    return cases


def main():
    cases,drivers=[],{}
    for sample in ['os4-current','os4-stable']:
        path=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        current=exercise(path)
        cases.extend(dict(sample=sample,**c) for c in current)
        drivers[sample]=dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
        print('PASS',sample,len(current),'cases',flush=True)
    tests=[Path(__file__).resolve(),ROOT/'tests/haptics_driver_emulation.py',
           ROOT/'tests/haptics-emulator-dependencies.json']
    disassemblies=[ROOT/'logs'/name for name in [
        'os4-stable-touch-startup.disasm','os4-stable-touch-reflash.disasm',
        'os4-current-touch-reflash.disasm','os4-stable-touch-isr.disasm',
        'os4-current-touch-isr.disasm','os4-stable-touch-parser.disasm']]
    report=dict(status='PASS',scope=__doc__.strip(),cases=cases,drivers=drivers,
                tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
                sources={str(p.relative_to(ROOT)):sha(p) for p in disassemblies},
                emulator_files={str(p.relative_to(ROOT)):sha(p) for p in sorted(DEPS.rglob('*'))
                                if p.is_file() and p.suffix in ('.py','.so')})
    (ROOT/'logs/touch-startup-emulation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(cases),'cases',flush=True)


if __name__=='__main__':
    main()
