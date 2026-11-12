#!/usr/bin/env python3
"""Join stock Xiaomi display notifier/workers to stock Synaptics resume/suspend.

Two isolated ARM64 address spaces cross a typed, explicit host callback bridge;
this does not emulate kernel symbol linking or concurrent workqueues. Original
panel parameters are captured using hash-bound DT evidence and original setup.
Work scheduling/empty queue flush, IPC, timestamps, IC-mode and driver services
remain fixtures. Original wrapper workers, Synaptics dispatch/display recovery,
configuration/parser/ISR run. No real display events, IRQ or fault cause claimed.
"""
import json
from pathlib import Path
import subprocess
from touch_wrapper_emulation import Wrapper, Capture, DEVICE, CALLBACKS
from touch_display_resume_emulation import Display, CTX, CORE, HW, PLATFORM
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30


class BridgeDisplay(Display):
    def __init__(self, path):
        super().__init__(path)
        self.ic_modes = []
        self.put64(PLATFORM+0xa8, CTX)  # dispatch passes platform device+0x10
        self.flag(CTX+0x6f0, 1)
        self.put64(CTX+0x5d8, self.symbols['syna_dev_resume'])
        self.put64(CTX+0x5e0, self.symbols['syna_dev_suspend'])
        self.intercept('syna_set_ic_mode')

    def on_code(self, uc, address, size, data):
        if self.hooks.get(address) != 'syna_set_ic_mode':
            return super().on_code(uc, address, size, data)
        self.ic_modes.append([self.arg(0), self.arg(1)])
        self.calls.append('syna_set_ic_mode')
        uc.reg_write(UC_ARM64_REG_X0, 0)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


class Notify(Wrapper):
    def __init__(self, path, params, syna):
        super().__init__(path, params, syna)
        self.pending, self.flushes, self.bridge, self.work_requests = [], [], [], []
        self.queue_result = 1
        self.ipc = []
        for name in ['xiaomi_notify_sensorhub_enable', 'driver_get_touch_mode', 'add_common_data_to_buf']:
            self.intercept(name)
        callback = 0x300d800
        self.put32(callback-4, 0x3463e8d3)
        self.hooks[callback] = 'fixture_resume_suspend'
        self.put64(CALLBACKS+0xd8, callback)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        if name is None:
            return
        args = [self.arg(i) for i in range(5)]
        if name == '__flush_workqueue':
            # No recursive execution of one Unicorn instance. Tests drain work
            # between events and fail if a flush would need pending work run.
            assert not self.pending, 'nonempty workqueue flush is outside scope'
            self.flushes.append(args[0]); result = 0
        elif name == 'queue_work_on':
            self.work_requests.append(dict(args=args[:3], accepted=self.queue_result))
            if self.queue_result:
                self.pending.append(args[2])
            result = self.queue_result
        elif name == 'fixture_resume_suspend':
            assert args[0] in [0, 1]
            self.synaptics.in_resume = True
            try:
                result = self.synaptics.run('syna_tcm_resume_suspend', args[0])
            finally:
                self.synaptics.in_resume = False
            self.bridge.append([args[0], result])
        elif name == 'xr_timestamp_gettime':
            result = 123456789
        elif name in ['ktime_get_real_ts64', 'time64_to_tm']:
            uc.mem_write(args[0] if name == 'ktime_get_real_ts64' else args[2],
                         b'\0'*(16 if name == 'ktime_get_real_ts64' else 56))
            result = 0
        elif name in ['xiaomi_notify_sensorhub_enable', 'add_common_data_to_buf']:
            self.ipc.append(dict(name=name,args=args)); result = 0
        elif name == 'driver_get_touch_mode':
            result = 0
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def notify(self, event, panel=0, null=False):
        self.put32(DEVICE, event)
        self.run('xiaomi_drm_panel_notifier_callback', 0, 0 if null else DEVICE, panel)

    def drain(self):
        while self.pending:
            work = self.pending.pop(0)
            assert work in [self.bss+0x10+0x28e8, self.bss+0x10+0x2908]
            name = 'xiaomi_touch_resume_work' if work == self.bss+0x10+0x2908 else 'xiaomi_touch_suspend_work'
            self.run(name, work)  # void: inspect callbacks/flags, never stale x0

    def suspended(self):
        return bytes(self.uc.mem_read(self.bss+0x10+0x28e0, 1))[0]


def exercise(wrapper_path, syna_path, properties, children):
    capture = Capture(syna_path, properties, children)
    capture.run('syna_xiaomi_touch_probe', CTX)

    def fresh():
        m = Notify(wrapper_path, capture.panel_bytes, BridgeDisplay(syna_path))
        assert m.panel() == 0
        return m

    cases = []
    def passed(label, m, **details):
        s = m.synaptics
        cases.append(dict(case=label, status='PASS', bridge=m.bridge,
            wrapper_suspended=m.suspended(), synaptics_state=s.u32(CTX+0x450),
            config_length=s.u32(CORE+0x18c), work_requests=m.work_requests,
            flushes=m.flushes, commands=[a[1] for a in s.commands],
            events=s.events, ic_modes=s.ic_modes, ipc=m.ipc, **details))

    m = fresh()
    for event in [1, 2, 2, 3, 2]:
        m.notify(event); m.drain()
    assert m.bridge == [[0,0],[1,0],[0,0],[1,0]]
    assert len(m.work_requests) == len(m.flushes) == 5
    assert m.suspended() == 0 and m.synaptics.emit()
    passed('ordered-off-on-duplicate-early-off-on', m)

    for label in ['config-error', 'power-error', 'disabled-dispatch', 'missing-callback']:
        m = fresh(); s = m.synaptics
        m.notify(1); m.drain()
        assert m.suspended() == 1 and s.u32(CTX+0x450) == 0
        if label == 'config-error': s.config_command_error = -110
        if label == 'power-error': s.flag(CTX+0x6f1,1); s.results['fixture_power'] = -5
        if label == 'disabled-dispatch': s.flag(CTX+0x6f0,0)
        if label == 'missing-callback': m.put64(m.bss+0x8+0x53a8+0x250,0)
        m.notify(2); m.drain()
        expected = -110 if label == 'config-error' else -19 if label == 'power-error' else -1
        assert m.bridge == ([[0,0]] if label == 'missing-callback' else [[0,0],[1,expected]])
        assert m.suspended() == 0 and s.u32(CORE+0x18c) == 0
        assert s.u32(CTX+0x450) == int(label == 'config-error')
        assert not s.emit()
        failure_snapshot = dict(wrapper_suspended=m.suspended(),
            synaptics_state=s.u32(CTX+0x450), config_length=s.u32(CORE+0x18c),
            bridge=[a[:] for a in m.bridge], events=s.events[:])
        count = len(m.bridge); commands = len(s.commands)
        m.notify(2); m.drain()
        assert len(m.bridge) == count and len(s.commands) == commands
        assert not s.emit()
        if label == 'config-error':
            s.config_command_error = 0
            m.notify(3); m.drain(); m.notify(2); m.drain()
            assert m.bridge[-2:] == [[0,0],[1,0]] and s.emit()
        passed(label+'-worker-clears-flag', m, repeated_on_skips_callback=True,
               failure_snapshot=failure_snapshot)

    for event in [0,4,7,8]:
        m = fresh(); m.notify(event); m.drain()
        assert not m.work_requests and not m.bridge
        passed('ignored-event-'+str(event), m)
    for label, panel, null in [('invalid-panel',2,False),('negative-panel',MASK,False),
                               ('null-notification',0,True),('unregistered-panel',1,False)]:
        m = fresh(); m.notify(1,panel,null); m.drain()
        assert not m.work_requests and not m.bridge
        passed(label,m)
    for label, event in [('reject-suspend',1),('reject-resume',2)]:
        m = fresh()
        if event == 2:
            m.notify(1);m.drain()
        before = len(m.bridge); flag = m.suspended()
        m.queue_result = 0;m.notify(event);m.drain()
        assert len(m.bridge) == before and m.suspended() == flag
        assert m.work_requests[-1]['accepted'] == 0
        passed(label,m)
    return cases


def main():
    dtpath = ROOT/'logs/touch-devicetree-audit.json'
    dt = json.loads(dtpath.read_text())
    sources = {str(dtpath.relative_to(ROOT)):sha(dtpath)}
    for field in ['sources','tests','libfdt_sources']:
        for name, expected in dt[field].items():
            p = Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p) == expected
            sources[str(p)] = expected
    cases,drivers=[],{}
    tool='/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    for record in dt['cases']:
        sample=record['sample'];base=ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules'
        path=base/'xiaomi_touch_dijun.ko';syna=base/'synaptics_tcm2.ko'
        for kind,p in [('wrapper',path),('synaptics',syna)]:
            drivers[sample+'-'+kind]=dict(path=str(p.relative_to(ROOT)),sha256=sha(p))
        props={k:bytes.fromhex(v) if isinstance(v,str) else v for k,v in record['canonical_touch_properties'].items()}
        children={n:{k:bytes.fromhex(v) for k,v in p.items()} for n,p in record['touch_child_properties'].items()}
        disasm=ROOT/'logs'/f'{sample}-touch-notifier-core.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=schedule_resume_suspend_work,xiaomi_drm_panel_notifier_callback,xiaomi_touch_suspend_work,xiaomi_touch_resume_work',str(path)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        disasm=ROOT/'logs'/f'{sample}-touch-notifier-dispatch.disasm'
        disasm.write_bytes(subprocess.check_output([tool,'-dr','--disassemble-symbols=syna_tcm_resume_suspend',str(syna)]))
        sources[str(disasm.relative_to(ROOT))]=sha(disasm)
        result=exercise(path,syna,props,children)
        cases.extend(dict(sample=sample,**c) for c in result)
        print('PASS',sample,len(result),'notifier scenarios',flush=True)
    tests=[Path(__file__).resolve()]+[ROOT/'tests'/name for name in [
        'touch_wrapper_emulation.py','touch_display_resume_emulation.py','touch_irq_emulation.py',
        'touch_panel_emulation.py','touch_transport_emulation.py','touch_spi_emulation.py',
        'touch_configuration_emulation.py','touch_startup_emulation.py','haptics_driver_emulation.py',
        'haptics-emulator-dependencies.json']]+[ROOT/'scripts/firmware_facts.py']
    deps=sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py','.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-notifier-emulation.json').write_text(json.dumps(dict(status='PASS',scope=__doc__.strip(),
        cases=cases,drivers=drivers,sources=sources,tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}),indent=2)+'\n')
    print('PASS',len(cases),'scenarios',flush=True)


if __name__=='__main__':main()
