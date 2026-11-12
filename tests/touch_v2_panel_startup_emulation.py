#!/usr/bin/env python3
"""Join stock OS4 DT parsing/panel/report commands with v2 startup and ISR.

Original ARM64 parses hash-bound DT properties and synthetic lockdown bytes,
selects panel parameters, switches reports using original v2 frames and runs
connect/background/parser/ISR. Flash-area read is a fixture in the first 13 cases;
the last three execute original identify/mode/boot-info/flash-read/return paths
with synthetic bytes. Physical transport, panel/input registration, firmware
request/update and kernel services are fixtures. Background runs sequentially.
No kernel or phone is booted.
Supplied status4/no-event responses do not model controller enable state.
"""
import json
from pathlib import Path
import struct
import subprocess

from touch_v2_startup_emulation import Startup, frames, identity, appinfo, CONFIG
from touch_spi_emulation import Spi, SPI, NODE
from touch_startup_emulation import CORE, CTX, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

FLASH = 0x40f8000
LOCKDOWN = bytes([0x53, 0x42, 0x32, 0x30, 0x4f, 2, 0x72, 0])
OF_APIS = ['of_find_property', 'of_property_read_variable_u32_array',
           'of_property_read_string', 'of_get_named_gpio', 'of_get_next_child']


class PanelStartup(Startup):
    def __init__(self, path, properties, children):
        super().__init__(path)
        self.properties = properties
        self.children = {0x40e8000+i*0x100: p for i, p in enumerate(children.values())}
        self.gpios = {'synaptics,irq-gpio': 76, 'synaptics,reset-gpio': 74}
        self.strings = {}; self.failures = {}
        self.bss = next(self.bases[i] for i, s in enumerate(self.sections) if s.name == '.bss')
        self.put64(SPI+0x2f8, NODE)
        for offset in [0x1874, 0x1878, 0x18ac]:
            self.put32(self.bss+offset, 0)
        # Reuse only the explicit OF service fixtures, not SPI probe/transport.
        assert self.run('xiaomi_parse_dt', SPI) == 0
        assert [self.u32(self.bss+o) for o in [0x1874, 0x1878, 0x18ac]] == [1440, 3200, 100]
        self.dt_reads = self.reads; self.reads = []
        for name in ['syna_xiaomi_touch_probe', 'syna_tcm_enable_report']:
            del self.hooks[self.symbols[name]]
        self.intercept('syna_tcm_read_flash_area')
        self.flash_error = self.flash_reads = self.valid_after = 0
        self.panel_error = self.notifier_error = 0
        self.panels = []; self.notifiers = []; self.sleeps = []; self.formatting = []
        self.firmware_wait = 0
        self.flash_area_calls = 0
        self.report_write_errors = []
        self.uc.mem_write(FLASH, b'\0'*128)
        self.uc.mem_write(FLASH+120, LOCKDOWN)

    def on_code(self, uc, address, size, data):
        if address == self.symbols['syna_tcm_read_flash_area']:
            self.flash_area_calls += 1
        name = self.hooks.get(address)
        if name in OF_APIS:
            return Spi.on_code(self, uc, address, size, data)
        args = [self.arg(i) for i in range(7)]
        if name == 'fixture_transport_write' and args[2] > 1:
            command = bytes(uc.mem_read(args[1], 1))[0]
            if command in [5, 6] and self.report_write_errors:
                error = self.report_write_errors.pop(0)
                if error: self.write_errors = [error]
        if name == 'syna_tcm_read_flash_area':
            assert args[:2] == [CORE, 2]
            self.flash_reads += 1
            if self.valid_after and self.flash_reads >= self.valid_after:
                uc.mem_write(FLASH+120, LOCKDOWN)
            if not self.flash_error:
                self.put64(args[2], FLASH)
            result = self.flash_error
        elif name == 'strlen':
            result = len(self.string(args[0]).encode())
        elif name == 'snprintf':
            fmt = self.string(args[2])
            assert fmt == 'Firmware: %d Cfg: %02x %02x', fmt
            rendered = (fmt % tuple(args[3:6])).encode()
            assert 0 < args[1] <= 128
            uc.mem_write(args[0], rendered[:args[1]-1]+b'\0')
            self.formatting.append(dict(format=fmt, value=rendered.decode()))
            result = len(rendered)
        elif name == 'register_touch_panel':
            assert args[1] == 0
            p = args[2]
            self.panels.append(dict(width=int.from_bytes(uc.mem_read(p, 2), 'little'),
                height=int.from_bytes(uc.mem_read(p+2, 2), 'little'),
                config=self.string(p+0x15), driver=self.string(p+0x55)))
            result = self.panel_error
        elif name == 'xiaomi_register_panel_notifier':
            self.notifiers.append(args[:4]); result = self.notifier_error
        elif name in ['register_tpd_tui_request', '__init_swait_queue_head', 'debugfs_create_dir']:
            result = 0
        elif name == 'wait_for_completion_timeout':
            result = self.firmware_wait
        elif name == 'msleep':
            self.sleeps.append(args[0]); result = 0
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        self.boundaries.append(dict(name=name, args=args, result=result))
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def exercise(path, properties, children):
    results = []
    labels = ['normal', 'disable-write-error', 'enable-write-error', 'both-report-write-errors',
              'enable-error-no-report', 'panel-register-error', 'notifier-register-error',
              'flash-error', 'lockdown-empty', 'lockdown-then-valid', 'firmware-wait-timeout',
              'raw-mode-ISR', 'config-timeout', 'original-flash', 'original-flash-read-error-recovered',
              'original-flash-identify-error']
    for label in labels:
        m = PanelStartup(path, properties, children)
        m.responses = frames(0x10, identity())+frames(1)+frames(1, appinfo())
        m.responses += [-110]+frames(0x10, identity(11)) if label == 'config-timeout' else frames(1, CONFIG)
        if label.startswith('original-flash'):
            del m.hooks[m.symbols['syna_tcm_read_flash_area']]
            boot = bytearray(32)
            boot[4] = 8
            struct.pack_into('<HH', boot, 5, 64, 256)
            struct.pack_into('<H', boot, 12, 2)
            flash = b'\0'*120+LOCKDOWN
            if label == 'original-flash-identify-error':
                m.responses += [-110]*5
            else:
                setup = frames(1, identity())+frames(0x10, identity(11))+frames(1, boot)
                if label.endswith('read-error-recovered'):
                    m.responses += setup+[-110]+frames(0x10, identity())
                m.responses += setup+frames(1, flash)+frames(0x10, identity())
        errors = {
            'disable-write-error': [-110, 0], 'enable-write-error': [0, -110],
            'both-report-write-errors': [-110, -110], 'enable-error-no-report': [0, -110],
        }.get(label, [0, 0])
        m.report_write_errors = [] if label == 'config-timeout' else errors.copy()
        for value in ([] if label == 'config-timeout' else errors):
            if value == 0: m.responses += frames(1)
        if label == 'panel-register-error': m.panel_error = -12
        if label == 'notifier-register-error': m.notifier_error = -517
        if label == 'flash-error': m.flash_error = -110
        if label.startswith('lockdown-'):
            m.uc.mem_write(FLASH+120, b'\0'*8)
            if label == 'lockdown-then-valid': m.valid_after = 3
        if label == 'firmware-wait-timeout': m.put32(CORE+0x328, 1)
        budget = False
        try:
            rc = m.run('syna_dev_connect', CTX)
        except AssertionError as e:
            if label != 'lockdown-empty' or e.args != (('emulation budget', 'syna_dev_connect'),): raise
            budget = True; rc = None
        print(label, rc, 'flash', m.flash_reads, 'writes', [w['packet'][:2] for w in m.writes], flush=True)
        if budget:
            assert m.flash_reads > 100 and not m.panels and not m.notifiers and not m.queued and not m.inputs
            assert m.flash_area_calls == m.flash_reads
            assert len(m.irq_requests) == 1 and not m.sleeps
            assert len(m.responses) == 2 and len(m.report_write_errors) == 2
        else:
            assert rc == 0 and not m.responses and not m.write_errors and not m.report_write_errors, (label, rc, m.responses)
            assert len(m.panels) == len(m.notifiers) == len(m.queued) == len(m.irq_requests) == 1
            assert m.panels[0]['width'] == 1440 and m.panels[0]['height'] == 3200
            assert m.panels[0]['config'] == 'dijun_syna_thp_config.ini'
            assert m.panels[0]['driver'].startswith('synaptics:')
            commands = [int(w['packet'][:2], 16) for w in m.writes]
            middle = [2]*5 if label == 'original-flash-identify-error' else [2, 31, 16, 19, 20]*(2 if label.endswith('read-error-recovered') else 1) if label.startswith('original-flash') else []
            assert commands == [10, 9, 32, 37]+middle+([31] if label == 'config-timeout' else [6, 5]), (label, commands)
            if label != 'config-timeout':
                packets = [bytes.fromhex(w['packet']) for w in m.writes[-2:]]
                assert [p[4:-2].hex() for p in packets] == ['c0', '11']
                assert [w['result'] < 0 for w in m.writes[-2:]] == [e < 0 for e in errors]
            assert not m.inputs and m.u64(CTX+0x3b8) == 0
            expected_flash = 0 if label == 'firmware-wait-timeout' or label.startswith('original-flash') else 5 if label == 'flash-error' else 3 if label == 'lockdown-then-valid' else 1
            assert m.flash_reads == expected_flash
            expected_calls = (5 if label == 'original-flash-identify-error' else
                              2 if label.endswith('read-error-recovered') else 1) if label.startswith('original-flash') else expected_flash
            assert m.flash_area_calls == expected_calls
            assert m.u32(CORE+0x18c) == (0 if label == 'config-timeout' else 13)
            if label != 'config-timeout':
                assert bytes(m.uc.mem_read(m.u64(CORE+0x180), 13)) == CONFIG
            assert bytes(m.uc.mem_read(CORE, 2)).hex() == ('020b' if label == 'config-timeout' else '0201')
            if label.startswith('original-flash') and label != 'original-flash-identify-error':
                reads = [bytes.fromhex(w['packet']) for w in m.writes if w['packet'].startswith('13')]
                assert all(p[4:-2] == bytes.fromhex('100000004000') for p in reads)
                assert len(reads) == (2 if label.endswith('read-error-recovered') else 1)
            if label in ['flash-error', 'firmware-wait-timeout', 'original-flash-identify-error']: assert m.sleeps == [1000]*5
            m.request_error = -2
            before_worker = len(m.writes)
            m.run('syna_dev_reflash_startup_work', CTX+0x3d0)
            assert len(m.writes) == before_worker and len(m.inputs) == 1
            assert m.u64(CTX+0x3b8) == INPUT
            assert m.requests == ['synaptics_spi_dijun.img'] and not m.updates
            if label == 'raw-mode-ISR':
                m.responses = frames(1)*2
                assert m.run('syna_tcm_enable_touch_raw', 1) == 0
                assert not m.responses
                assert [bytes.fromhex(w['packet'])[4:-2].hex() for w in m.writes[-2:]] == ['11', 'c0']
                m.report_frames(code=0xc0)
            elif label == 'enable-error-no-report':
                m.responses = frames(4)
            else:
                m.report_frames()
            assert m.run('syna_dev_isr', 0, CTX) == 1 and not m.responses
            if label in ['config-timeout', 'raw-mode-ISR', 'enable-error-no-report']:
                assert not m.events
                assert bool(m.raw_frames) == (label == 'raw-mode-ISR')
            else:
                assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
                assert m.events[-1] == [INPUT, 0, 0, 0]
        results.append(dict(case=label, status='PASS', result=rc, instruction_budget=budget,
            flash_reads=m.flash_reads, flash_area_calls=m.flash_area_calls,
            panels=m.panels, notifiers=m.notifiers, sleeps=m.sleeps,
            writes=m.writes, reads=m.reads, dt_reads=m.dt_reads, queued=m.queued,
            inputs=m.inputs, irq_requests=m.irq_requests, events=m.events, raw_frames=m.raw_frames,
            config_length=m.u32(CORE+0x18c), mode=bytes(m.uc.mem_read(CORE, 2)).hex(),
            formatting=m.formatting, remaining=len(m.responses), prints=m.prints))
    return results


def main():
    evidence = ROOT/'logs/touch-devicetree-audit.json'
    dt = json.loads(evidence.read_text()); sources = {str(evidence.relative_to(ROOT)): sha(evidence)}
    for field in ['sources', 'tests', 'libfdt_sources']:
        for name, expected in dt[field].items():
            p = Path(name) if Path(name).is_absolute() else ROOT/name
            assert sha(p) == expected
            sources[str(p)] = expected
    cases = []; drivers = {}
    for record in dt['cases']:
        sample = record['sample']
        path = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        assert sha(path) in LAYOUTS
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        properties = {k:bytes.fromhex(v) if isinstance(v, str) else v for k, v in record['canonical_touch_properties'].items()}
        children = {n:{k:bytes.fromhex(v) for k, v in p.items()} for n, p in record['touch_child_properties'].items()}
        disasm = ROOT/'logs'/f'{sample}-touch-v2-panel-startup.disasm'
        disasm.write_bytes(subprocess.check_output([
            '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump', '-dr',
            '--disassemble-symbols=xiaomi_parse_dt,syna_xiaomi_touch_probe,syna_tcm_enable_touch_raw,syna_tcm_enable_report,syna_tcm_read_flash_area,syna_tcm_set_up_flash_access,syna_tcm_read_flash_boot_config,syna_tcm_read_flash,syna_tcm_identify,syna_tcm_get_boot_info', str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        results = exercise(path, properties, children)
        assert len(results) == 16
        cases.extend(dict(sample=sample, **c) for c in results)
    tests = [Path(__file__).resolve()]+[ROOT/'tests'/n for n in [
        'touch_v2_startup_emulation.py', 'touch_v2_command_emulation.py', 'touch_message_emulation.py',
        'touch_spi_emulation.py', 'touch_configuration_emulation.py', 'touch_startup_emulation.py',
        'haptics_driver_emulation.py', 'haptics-emulator-dependencies.json']]
    deps = sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-v2-panel-startup-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, drivers=drivers, sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in deps}), indent=2)+'\n')


if __name__ == '__main__': main()
