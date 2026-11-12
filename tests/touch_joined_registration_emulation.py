#!/usr/bin/env python3
"""Join original OS4 Synaptics startup to original Xiaomi panel/input registration.

Panel parameter bytes come directly from original Synaptics DT/panel setup.
Two original ELF modules execute in separate ARM64 address spaces with typed
host bridges. The wrapper callback table remains explicit, so this is neither
kernel linking nor a complete shared object/pointer model. Kernel input/slots,
allocators, threads, mode/proc setup and notifier services remain fixtures.
Transport ID/app/config/report responses, lockdown and firmware-request failure
are explicit fixtures. No kernel, physical SPI, IRQ or device is executed.
"""
import json
from pathlib import Path
import subprocess
from touch_v2_panel_startup_emulation import PanelStartup, frames, identity, appinfo, CONFIG
from touch_wrapper_emulation import Wrapper, INPUT as WRAPPER_INPUT
from touch_startup_emulation import CTX, CORE, INPUT
from haptics_driver_emulation import ROOT, MASK, sha, UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30
from unicorn import UC_HOOK_MEM_INVALID, UC_MEM_WRITE_UNMAPPED, UC_ERR_WRITE_UNMAPPED, UcError


class Joined(PanelStartup):
    def __init__(self, path, wrapper_path, props, children, label):
        self.wrapper_path = wrapper_path
        self.wrapper = None
        self.label = label
        self.registration_calls = []
        self.invalid_accesses = []
        super().__init__(path, props, children)
        self.uc.hook_add(UC_HOOK_MEM_INVALID, self.invalid_access)

    def invalid_access(self, uc, access, address, size, value, data):
        self.invalid_accesses.append(dict(access=access, address=address, size=size,
                                         value=value, pc=uc.reg_read(UC_ARM64_REG_PC),
                                         x0=uc.reg_read(UC_ARM64_REG_X0)))
        return False  # do not map a null page or let the failing path continue

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        if name not in ['register_touch_panel', 'register_xiaomi_input_dev']:
            return super().on_code(uc, address, size, data)
        args = [self.arg(i) for i in range(4)]
        if name == 'register_touch_panel':
            assert self.wrapper is None and args[1] == 0
            params = bytes(uc.mem_read(args[2], 0xd6))
            self.wrapper = Wrapper(self.wrapper_path, params, self)
            w = self.wrapper
            if self.label == 'panel-workqueue-error':
                w.workqueue_error = True
            if self.label == 'panel-mode-error-ignored':
                w.mode_error = -5
            if self.label == 'panel-thread-error':
                w.thread_error = -12
            if self.label == 'input-allocation-error':
                w.input_allocate_error = True
            if self.label == 'input-registration-error':
                w.input_register_error = -12
            if self.label == 'input-slots-error-ignored':
                w.slot_error = -12
            result = w.panel()
            self.panels.append(dict(width=int.from_bytes(params[:2], 'little'),
                                    height=int.from_bytes(params[2:4], 'little'),
                                    parameters=params.hex(), result=result))
        else:
            assert self.wrapper is not None
            self.inputs.append(args)
            result = self.wrapper.pointer('register_xiaomi_input_dev', *args)
            assert result in [0, WRAPPER_INPUT] and WRAPPER_INPUT == INPUT
        self.registration_calls.append(dict(name=name, args=args, result=result))
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def exercise(syna, wrapper, props, children):
    cases = []
    for label in ['normal', 'input-allocation-error', 'input-registration-error',
                  'input-slots-error-ignored', 'panel-workqueue-error',
                  'panel-mode-error-ignored', 'panel-thread-error', 'config-timeout']:
        m = Joined(syna, wrapper, props, children, label)
        m.responses = frames(0x10, identity()) + frames(1) + frames(1, appinfo())
        m.responses += ([-110] + frames(0x10, identity(11))) if label == 'config-timeout' else frames(1, CONFIG)
        if label != 'config-timeout':
            m.responses += frames(1)*2
        assert m.run('syna_dev_connect', CTX) == 0 and not m.responses
        assert len(m.panels) == len(m.queued) == len(m.irq_requests) == 1
        assert m.panels[0]['width'] == 1440 and m.panels[0]['height'] == 3200
        m.request_error = -2
        failed_input = label in ['input-allocation-error', 'input-registration-error']
        try:
            m.run('syna_dev_reflash_startup_work', CTX+0x3d0)
        except UcError as error:
            assert failed_input and error.errno == UC_ERR_WRITE_UNMAPPED
            assert len(m.invalid_accesses) == 1
            fault = m.invalid_accesses[0]
            assert fault['access'] == UC_MEM_WRITE_UNMAPPED and fault['address'] == 0x2c0
            assert fault['size'] == 8 and fault['value'] == CTX and fault['x0'] == 0
            # Original str x19,[x0,#0x2c0] occurs before the later cbz x0.
            assert bytes(m.uc.mem_read(fault['pc'], 4)).hex() == '136001f9'
        else:
            assert not failed_input and not m.invalid_accesses
        assert m.requests == ['synaptics_spi_dijun.img'] and not m.updates
        assert len(m.inputs) == 1 and len(m.registration_calls) == 2
        w = m.wrapper
        panel_result = m.registration_calls[0]['result']
        assert panel_result == (-1 if label == 'panel-workqueue-error' else 0), (label, panel_result)
        assert m.u64(CTX+0x3b8) == (0 if failed_input else INPUT)
        assert w.input_allocations == 1 and w.input_registrations == int(label != 'input-allocation-error')
        assert w.frees == ([INPUT] if label == 'input-registration-error' else [])
        assert bool(bytes(w.uc.mem_read(w.bss+0xa, 1))[0] & 1) == (label != 'panel-workqueue-error')
        if not failed_input:
            m.report_frames()
            assert m.run('syna_dev_isr', 0, CTX) == 1
        delivered = [INPUT, 3, 53, 64400] in m.events
        assert delivered == (not failed_input and label != 'config-timeout'), (label, m.events)
        # A worker fault is terminal in this model. Never run ISR afterward.
        assert not m.responses
        if not failed_input:
            assert m.u64(INPUT+0x2c0) == CTX
            assert w.axes[:2] == [[INPUT, 53, 0, 143999, 0, 0], [INPUT, 54, 0, 319999, 0, 0]]
            assert w.slots == [[INPUT, 10, 2]]
        print('PASS', label, 'panel', panel_result, 'input', hex(m.u64(CTX+0x3b8)), 'events', len(m.events), flush=True)
        cases.append(dict(case=label, status='PASS', connect_result=0,
                          registration_calls=m.registration_calls, panels=m.panels,
                          input_pointer=m.u64(CTX+0x3b8), input_allocations=w.input_allocations,
                          input_registrations=w.input_registrations, input_frees=w.frees,
                          axes=w.axes, slots=w.slots, wrapper_boundaries=w.boundaries,
                          panel_mask=bytes(w.uc.mem_read(w.bss+0xa, 1)).hex(),
                          config_length=m.u32(CORE+0x18c), delivered=delivered,
                          worker_returned=not failed_input, invalid_accesses=m.invalid_accesses,
                          input_private_context=m.u64(INPUT+0x2c0) if not failed_input else None,
                          events=m.events, remaining_report_responses=len(m.responses),
                          requests=m.requests, writes=m.writes))
    return cases


def main():
    prior_paths = [ROOT/'logs/touch-v2-panel-startup-emulation.json', ROOT/'logs/touch-wrapper-emulation.json']
    sources, tests, drivers, emulator = {}, {}, {}, {}
    for path in prior_paths:
        prior = json.loads(path.read_text())
        sources[str(path.relative_to(ROOT))] = sha(path)
        sources.update(prior['sources']); tests.update(prior['tests'])
        drivers.update(prior['drivers']); emulator.update(prior['emulator_files'])
    tests[str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__))
    for name in ['touch_v2_panel_startup_emulation.py', 'touch_wrapper_emulation.py']:
        tests['tests/'+name] = sha(ROOT/'tests'/name)
    for mapping in [sources, tests, emulator]:
        for name, expected in mapping.items():
            p = Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p) == expected, name
    for record in drivers.values():
        assert sha(ROOT/record['path']) == record['sha256']
    dt = json.loads((ROOT/'logs/touch-devicetree-audit.json').read_text())
    cases = []
    for record in dt['cases']:
        sample = record['sample']
        base = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules'
        disasm = ROOT/'logs'/f'{sample}-touch-joined-registration-core.disasm'
        tool = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
        disasm.write_bytes(subprocess.check_output([tool, '-dr', '--disassemble-symbols=syna_dev_reflash_startup,syna_dev_reflash_startup_work', str(base/'synaptics_tcm2.ko')]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        props = {k: bytes.fromhex(v) if isinstance(v, str) else v for k, v in record['canonical_touch_properties'].items()}
        children = {n: {k: bytes.fromhex(v) for k, v in p.items()} for n, p in record['touch_child_properties'].items()}
        cases.extend(dict(sample=sample, **c) for c in exercise(base/'synaptics_tcm2.ko', base/'xiaomi_touch_dijun.ko', props, children))
    (ROOT/'logs/touch-joined-registration-emulation.json').write_text(json.dumps(dict(
        status='PASS', scope=__doc__.strip(), sources=sources, tests=tests, drivers=drivers,
        emulator_files=emulator, cases=cases), indent=2)+'\n')
    print('PASS', len(cases), 'cases', flush=True)


if __name__ == '__main__':
    main()
