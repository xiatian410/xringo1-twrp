#!/usr/bin/env python3
"""Join original OS4 detect/connect/mode/config/background/ISR over v2 frames.

ID, app-info, config and event bytes are synthetic physical-transport fixtures.
Power/setup/reset callbacks, panel setup, firmware update, input registration,
IRQ registration and scheduling are explicit boundaries. Background work is
invoked sequentially, not by a kernel workqueue. No phone or real SPI is used.
"""
import json
from pathlib import Path
import struct
import subprocess

from touch_v2_command_emulation import Command, header, CONFIG
from touch_startup_emulation import CORE, CTX, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, sha, MASK
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30


def identity(mode=1):
    payload = bytearray(48)
    payload[:2] = bytes([1, mode])
    payload[2:18] = b'SYNTHETIC-ID-000'
    struct.pack_into('<IHHH', payload, 18, 4463140, 256, 512, 256)
    assert len(payload) == 48
    return bytes(payload)


def frames(code, payload=b''):
    return [(code, len(payload), b'', '')]+([(code, len(payload), payload, '')] if payload else [])


def appinfo():
    payload = bytearray(48)
    struct.pack_into('<HHH', payload, 32, 1440, 3200, 10)
    struct.pack_into('<HH', payload, 40, 17, 38)
    return bytes(payload)


class Startup(Command):
    def __init__(self, path):
        super().__init__(path)
        for name in ['syna_tcm_detect_device', 'syna_tcm_switch_fw_mode']:
            del self.hooks[self.symbols[name]]
        # Do not inherit ready protocol/mode/input values from isolated tests.
        self.uc.mem_write(CORE, b'\0\0')
        for offset in [0x330, 0x338, 0x340, 0x348]:
            self.put64(CORE+offset, 0)
        self.put32(CORE+0x2c, 0)
        self.put32(CORE+0x30, 0)
        for offset in [8, 12, 16]:
            self.put32(CORE+offset, 0)
        self.put64(CTX+0x3b8, 0)
        self.probe_write = True
        self.probe_read = True
        self.probe_header = header(0x10, 0, 0)
        self.probe_write_error = 0
        self.probe_read_error = 0
        self.probe_io = []
        self.panel_calls = 0

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(7)]
        if name == 'fixture_transport_write' and self.probe_write:
            assert args[2] == 1 and bytes(uc.mem_read(args[1], 1)) == b'\2'
            self.probe_write = False
            result = self.probe_write_error or 1
            self.probe_io.append(dict(operation='write', packet='02', result=result))
        elif name == 'fixture_transport_read' and self.probe_read:
            assert args[2] == 4
            self.probe_read = False
            result = self.probe_read_error or 4
            if not self.probe_read_error:
                uc.mem_write(args[1], self.probe_header)
            self.probe_io.append(dict(operation='read', packet=self.probe_header.hex(), result=result))
        elif name == 'syna_xiaomi_touch_probe':
            self.panel_calls += 1
            return super().on_code(uc, address, size, data)
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

def exercise(path):
    cases = []
    for label in ['detect-app', 'detect-bootloader', 'probe-write-error', 'probe-read-error',
                  'invalid-probe-header', 'identify-fallback', 'reset-fallback', 'size-command-error',
                  'connect-background-ISR', 'connect-config-timeout', 'connect-app-timeout-recovered',
                  'connect-app-timeout-exhausted',
                  'background-mode-only-missing-config', 'background-config-recovered',
                  'background-update-exhausted', 'connect-irq-error',
                  'mode-app', 'mode-app-stays-bootloader',
                  'mode-app-write-error', 'mode-bootloader', 'mode-bootloader-stays-app', 'mode-invalid']:
        m = Startup(path)
        m.responses = frames(0x10, identity(11 if label == 'detect-bootloader' else 1))+frames(1)
        if label == 'probe-write-error':
            m.probe_write_error = -110
        if label == 'probe-read-error':
            m.probe_read_error = -110
        if label == 'invalid-probe-header':
            m.probe_header = b'\0'*4
        if label in ['identify-fallback', 'reset-fallback']:
            m.responses = [-110]+([-110] if label == 'reset-fallback' else [])+frames(1, identity())+frames(1)
        if label == 'size-command-error':
            m.responses = frames(0x10, identity())+[-110]
        connected = label.startswith(('connect-', 'background-'))
        if connected:
            if label == 'connect-irq-error':
                m.irq_result = -5
            m.responses += frames(1, appinfo())
            if label == 'connect-config-timeout' or label.startswith('background-'):
                m.responses += [-110]+frames(0x10, identity(11))
            elif label.startswith('connect-app-timeout-'):
                # Original get_app_info drains three event reads before each
                # retry, and three more after the third failed command.
                m.responses = frames(0x10, identity())+frames(1)
                if label.endswith('recovered'):
                    m.responses += [-110]+frames(4)*3+frames(1, appinfo())+frames(1, CONFIG)
                else:
                    m.responses += [-110]*12+frames(0x10, identity(11))
            else:
                m.responses += frames(1, CONFIG)
            rc = m.run('syna_dev_connect', CTX)
        else:
            rc = m.run('syna_tcm_detect_device', CORE, 0, 1)
        modes = []
        assert len(m.responses) == (3 if label in ['probe-write-error', 'probe-read-error', 'invalid-probe-header'] else 0), label
        connect_writes = [int(w['packet'][:2], 16) for w in m.writes]
        worker_writes = []
        if label.startswith('mode-'):
            assert rc == 1
            if label.startswith('mode-app'):
                # Enter a bootloader state through original ID parsing first;
                # no direct mode write to emulate successful recovery.
                m.responses = frames(0x10, identity(11))
                assert m.event() == 0
                m.responses = [-110] if label == 'mode-app-write-error' else frames(0x10, identity(11 if label == 'mode-app-stays-bootloader' else 1))
                rc = m.run('syna_tcm_switch_fw_mode', CORE, 1, 200)
            elif label == 'mode-invalid':
                m.responses = []
                rc = m.run('syna_tcm_switch_fw_mode', CORE, 2, 200)
            else:
                m.responses = frames(0x10, identity(1 if label == 'mode-bootloader-stays-app' else 11))
                rc = m.run('syna_tcm_switch_fw_mode', CORE, 11, 200)
        if connected and rc == 0:
            modes.append(bytes(m.uc.mem_read(CORE+1, 1))[0])
            m.request_error = -2
            if label.startswith('background-'):
                m.responses = frames(0x10, identity())
                assert m.run('syna_tcm_switch_fw_mode', CORE, 1, 200) == 0
                assert not m.responses and m.u32(CORE+0x18c) == 0
            if label in ['background-config-recovered', 'background-update-exhausted']:
                m.request_error = 0
                m.update_results = [0] if label == 'background-config-recovered' else [-5]*3
            if label == 'background-config-recovered':
                m.responses = frames(1, appinfo())+frames(1, CONFIG)
            else:
                m.responses = []
            before_worker = len(m.writes)
            m.run('syna_dev_reflash_startup_work', CTX+0x3d0)
            assert not m.responses, label
            worker_writes = [int(w['packet'][:2], 16) for w in m.writes[before_worker:]]
            modes.append(bytes(m.uc.mem_read(CORE+1, 1))[0])
            m.report_frames()
            assert m.run('syna_dev_isr', 0, CTX) == 1
        expected = {
            'probe-write-error': (-110, '0000'), 'probe-read-error': (-110, '0000'),
            'invalid-probe-header': (-245, '0000'), 'size-command-error': (-245, '0001'),
            'detect-bootloader': (11, '020b'), 'mode-app': (0, '0201'),
            'mode-app-stays-bootloader': (-242, '020b'), 'mode-app-write-error': (-110, '020b'),
            'mode-bootloader': (0, '020b'), 'mode-bootloader-stays-app': (-242, '0201'),
            'mode-invalid': (-241, '0201'), 'connect-irq-error': (-5, '0201'),
        }
        expected_rc, expected_mode = expected.get(label, (0 if connected else 1,
            '020b' if label in ['connect-config-timeout', 'connect-app-timeout-exhausted'] else '0201'))
        assert rc == expected_rc and bytes(m.uc.mem_read(CORE, 2)).hex() == expected_mode, label
        working = label in ['connect-background-ISR', 'connect-app-timeout-recovered', 'background-config-recovered']
        expected_config = 13 if working or label == 'connect-irq-error' else 0
        assert m.u32(CORE+0x18c) == expected_config, label
        if working:
            assert bytes(m.uc.mem_read(m.u64(CORE+0x180), 13)) == CONFIG
            assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
            assert [INPUT, 1, 330, 1] in m.events and m.events[-1] == [INPUT, 0, 0, 0]
            assert m.u32(CORE+0x10) == 10 and m.u32(CORE+8) == 1440 and m.u32(CORE+12) == 3200
        else:
            assert not m.events and not m.slots, label
        if connected:
            assert len(m.irq_requests) == 1 and m.irq_requests[0][1] == 76
            if rc == 0:
                assert m.panel_calls == 1 and len(m.inputs) == 1 and m.u64(CTX+0x3b8) == INPUT
                assert len(m.queued) == 1 and m.queued[0][2:] == [CTX+0x3d0, 50]
                assert m.requests == ['synaptics_spi_dijun.img']
                assert worker_writes == ([0x20, 0x25] if label == 'background-config-recovered' else []), label
                assert len(m.updates) == (1 if label == 'background-config-recovered' else 3 if label == 'background-update-exhausted' else 0)
            else:
                assert m.power == [1, 0] and not m.panel_calls and not m.inputs and not m.queued
            if label == 'connect-app-timeout-recovered':
                assert connect_writes == [10, 9, 32, 10, 10, 10, 32, 37]
            if label == 'connect-app-timeout-exhausted':
                assert connect_writes == [10, 9]+[32, 10, 10, 10]*3+[31]
        else:
            assert not m.inputs and not m.queued and not m.irq_requests and not m.panel_calls
            if label.startswith('mode-'):
                suffix = [10, 20] if label.startswith('mode-app') else [] if label == 'mode-invalid' else [31]
                assert [int(w['packet'][:2], 16) for w in m.writes] == [10, 9]+suffix
            if label == 'identify-fallback':
                assert connect_writes == [10, 2, 9]
            if label == 'reset-fallback':
                assert connect_writes == [10, 2, 4, 9]
        assert len(m.responses) == (3 if label in ['probe-write-error', 'probe-read-error', 'invalid-probe-header'] else 0), label
        assert m.probe_io[0] == dict(operation='write', packet='02', result=-110 if label == 'probe-write-error' else 1)
        assert len(m.probe_io) == (1 if label == 'probe-write-error' else 2), label
        if label not in ['probe-write-error', 'probe-read-error', 'invalid-probe-header', 'size-command-error']:
            assert m.u32(CORE+0x2c) == m.u32(CORE+0x30) == 256, label
        print(label, rc, bytes(m.uc.mem_read(CORE, 2)).hex(), 'config', m.u32(CORE+0x18c),
              'inputs', len(m.inputs), 'events', len(m.events), 'remaining', len(m.responses), flush=True)
        cases.append(dict(case=label, status='PASS', result=rc, mode=bytes(m.uc.mem_read(CORE, 2)).hex(),
            config_length=m.u32(CORE+0x18c), max_write=m.u32(CORE+0x2c), max_read=m.u32(CORE+0x30),
            reads=m.reads, writes=m.writes, probe_io=m.probe_io, inputs=m.inputs,
            panel_calls=m.panel_calls, queued=m.queued, irq_requests=m.irq_requests,
            events=m.events, modes=modes, remaining=len(m.responses),
            connect_commands=connect_writes, worker_commands=worker_writes,
            firmware_requests=m.requests, firmware_updates=len(m.updates),
            prints=m.prints))
    return cases


def main():
    cases = []; drivers = {}; sources = {}
    tool = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    symbols = ['syna_tcm_detect_device', 'syna_tcm_v2_detect', 'syna_dev_connect', 'syna_dev_set_up_app_fw',
               'syna_tcm_switch_fw_mode', 'syna_tcm_run_application_fw', 'syna_dev_reflash_startup_work',
               'syna_dev_reflash_startup', 'syna_tcm_get_app_info']
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        assert sha(path) in LAYOUTS
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        disasm = ROOT/'logs'/f'{sample}-touch-v2-startup.disasm'
        disasm.write_bytes(subprocess.check_output([tool, '-dr', '--disassemble-symbols='+','.join(symbols), str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        results = exercise(path)
        assert len(results) == 22 and len({c['case'] for c in results}) == 22
        cases.extend(dict(sample=sample, **c) for c in results)
    tests = [Path(__file__).resolve()] + [ROOT/'tests'/name for name in ['touch_v2_command_emulation.py',
        'touch_message_emulation.py', 'touch_configuration_emulation.py', 'touch_startup_emulation.py',
        'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-v2-startup-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, drivers=drivers, sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in dependencies}), indent=2)+'\n')


if __name__ == '__main__':
    main()
