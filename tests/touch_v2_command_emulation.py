#!/usr/bin/env python3
"""Execute stock OS4 v2 command/read/write/framing through parser and ISR.

Original ARM64 builds and checks CRC6/CRC16, sequence bits, retries and buffer
assembly. The physical transport callback supplies explicitly synthetic frames
and records generated command bytes; no SPI controller or kernel is booted.
Report configuration, allocation, locks, time, GPIO and input remain fixtures.
"""
import json
from pathlib import Path
import struct
import subprocess

from touch_message_emulation import Message, EVENT_ID, OUTPUT
from touch_configuration_emulation import CONFIG
from touch_startup_emulation import CORE, CTX, HW, INPUT, LAYOUTS
from haptics_driver_emulation import ROOT, DEPS, MASK, sha
from haptics_driver_emulation import UC_ARM64_REG_X0, UC_ARM64_REG_PC, UC_ARM64_REG_X30

WRITE_CALLBACK = 0x300b000


def crc6(data):
    crc = 0xfc
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ (0xc if crc & 0x80 else 0)) & 255
    return crc & 0xfc


def crc16(data):
    crc = 0xffff
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 65535
    return crc


def header(code, length, seq):
    first = bytes([code]) + struct.pack('<H', length)
    for tail in range(64):
        candidate = first + bytes([(seq & 1) << 6 | tail])
        if crc6(candidate) == 0:
            return candidate
    raise AssertionError('no synthetic header')


class Command(Message):
    def __init__(self, path):
        super().__init__(path, 2)
        del self.hooks[self.symbols['syna_tcm_v2_execute_cmd_request']]
        self.hooks[WRITE_CALLBACK] = 'fixture_transport_write'
        self.put32(WRITE_CALLBACK-4, 0xcc41658f)
        self.put64(HW+0x120, WRITE_CALLBACK)
        self.responses = []
        self.writes = []
        self.write_errors = []
        self.put32(CORE+0x2c, 256)
        self.put32(CORE+0x30, 256)

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(7)]
        if name == 'fixture_transport_write':
            packet = bytes(uc.mem_read(args[1], args[2]))
            assert crc6(packet[:4]) == 0
            if len(packet) > 4:
                assert crc16(packet) == 0
            result = self.write_errors.pop(0) if self.write_errors else len(packet)
            self.writes.append(dict(packet=packet.hex(), result=result))
        elif name == 'fixture_transport_read':
            assert self.responses, ('unexpected frame request', args, self.reads, self.writes)
            response = self.responses.pop(0)
            if isinstance(response, int):
                result = response
                packet = None
            else:
                code, length, payload, fault = response
                seq = bytes(uc.mem_read(CORE+0x1de, 1))[0]
                packet = header(code, length, seq ^ int(fault == 'sequence'))
                if fault == 'header-crc':
                    packet = packet[:3] + bytes([packet[3] ^ 1])
                if args[2] > 4:
                    assert args[2] == len(payload)+6, (args, response)
                    packet += payload
                    packet += struct.pack('>H', crc16(packet))
                    if fault == 'payload-crc':
                        packet = packet[:-1]+bytes([packet[-1] ^ 1])
                else:
                    assert not payload
                assert len(packet) == args[2]
                uc.mem_write(args[1], packet)
                result = len(packet)
            self.reads.append(dict(length=args[2], payload=packet.hex() if packet else None, result=result))
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        self.boundaries.append(dict(name=name, args=args, result=result))
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    def report_frames(self, payload=None, code=0x11, predictive=False):
        self.payload = payload if payload is not None else struct.pack('<BBHHBB', 0, 1, 644, 1589, 7, 6)
        if predictive:
            self.uc.mem_write(CORE+0x319, b'\1')
            self.put32(CORE+0x1d8, len(self.payload))
            self.responses = [(code, len(self.payload), self.payload, '')]
        else:
            self.responses = [(code, len(self.payload), b'', '')]
            if self.payload:
                self.responses.append((code, len(self.payload), self.payload, ''))


def exercise(path):
    cases = []
    for label in ['event', 'ISR-press-release', 'ISR-payload-crc-exhausted', 'raw', 'empty', 'predictive', 'fragmented-response',
                  'write-error', 'header-read-error', 'payload-read-error', 'header-crc-retry',
                  'sequence-retry', 'payload-crc-retry', 'header-crc-exhausted', 'sequence-exhausted',
                  'payload-crc-exhausted', 'status8-retry', 'status8-exhausted', 'status0', 'status4', 'no-write-callback',
                  'no-read-callback', 'allocation-write', 'allocation-read', 'allocation-input',
                  'allocation-grow', 'allocation-read-grow', 'allocation-payload', 'allocation-report', 'allocation-output',
                  'size-command-9', 'fragmented-command', 'normal-mode', 'raw-mode', 'mode-first-write-error',
                  'mode-second-write-error']:
        m = Command(path)
        assert m.acquire() == 0
        m.allocation_count = 0
        m.allocations = []
        m.report_frames(payload=b'' if label == 'empty' else None, code=0xc0 if label == 'raw' else 0x11,
                        predictive=label == 'predictive')
        if label == 'fragmented-response':
            m.put32(CORE+0x30, 10)
            m.responses = [(0x11, 8, b'', ''), (0x11, 4, m.payload[:4], ''), (0x11, 4, m.payload[4:], '')]
        if label == 'write-error':
            m.write_errors = [-110]
        if label == 'header-read-error':
            m.responses = [-110]
        if label == 'payload-read-error':
            m.responses[1] = -110
        fault = next((f for f in ['header-crc', 'sequence', 'payload-crc'] if label.startswith(f)), None)
        if fault:
            if fault == 'payload-crc':
                bad = (0x11, 8, m.payload, fault)
                m.responses = [m.responses[0]] + [bad]*(7 if label.endswith('exhausted') else 1) + ([] if label.endswith('exhausted') else [m.responses[1]])
            else:
                bad = (0x11, 8, b'', fault)
                m.responses = [bad]*(6 if label.endswith('exhausted') else 1) + ([] if label.endswith('exhausted') else m.responses)
        if label in ['payload-crc-exhausted', 'ISR-payload-crc-exhausted']:
            m.responses = [m.responses[0]] + [(0x11, 8, m.payload, 'payload-crc')]*7
        if label == 'status8-retry':
            m.responses.insert(0, (8, 0, b'', ''))
        if label == 'status8-exhausted':
            m.responses = [(8, 0, b'', '')]*6
        if label == 'status0':
            m.responses = [(0, 0, b'', '')]
        if label == 'status4':
            m.responses = [(4, 0, b'', '')]
        if label == 'no-write-callback':
            m.put64(HW+0x120, 0)
        if label == 'no-read-callback':
            m.put64(HW+0x118, 0)
        if label.startswith('allocation-'):
            m.allocation_error = ['write', 'read', 'input', 'grow', 'read-grow', 'payload', 'report', 'output'].index(label[11:])+1
        if label in ['size-command-9', 'fragmented-command']:
            payload = b'\0\1' if label == 'size-command-9' else b'12345678'
            m.uc.mem_write(0x4079000, payload)
            if label == 'fragmented-command':
                m.put32(CORE+0x2c, 10)
            m.responses = [(1, 0, b'', '')]*(1 if label == 'size-command-9' else 2)
            rc = m.run('syna_tcm_v2_execute_cmd_request', CORE, 9, 0x4079000, len(payload), len(payload))
            assert rc == 0 and not m.responses
            assert [bytes.fromhex(w['packet'])[0] for w in m.writes] == ([9] if label == 'size-command-9' else [9, 1])
            assert b''.join(bytes.fromhex(w['packet'])[4:-2] for w in m.writes) == payload
        elif label in ['normal-mode', 'raw-mode', 'mode-first-write-error', 'mode-second-write-error']:
            del m.hooks[m.symbols['syna_tcm_enable_report']]
            m.put64(CORE+0x340, m.symbols['syna_tcm_v2_write_message'])
            m.responses = [(1, 0, b'', '')]*(1 if label.startswith('mode-') else 2)
            if label == 'mode-first-write-error':
                m.write_errors = [-110]
            if label == 'mode-second-write-error':
                m.write_errors = [7, -110]
            rc = m.run('syna_tcm_enable_touch_raw', int(label == 'raw-mode'))
            assert rc == (-110 if label == 'mode-second-write-error' else 0)
            assert [bytes.fromhex(w['packet'])[0] for w in m.writes] == [6, 5]
            assert [bytes.fromhex(w['packet'])[4] for w in m.writes] == ([0x11, 0xc0] if label == 'raw-mode' else [0xc0, 0x11])
            assert bytes(m.uc.mem_read(CTX+0x6ac, 1)) == bytes([int(label == 'raw-mode')])
            assert not m.responses
        else:
            rc = m.run('syna_dev_isr', 0, CTX) if label.startswith('ISR-') else m.event()
        expected_success = label in ['event', 'ISR-press-release', 'raw', 'empty', 'predictive', 'fragmented-response',
                                     'header-crc-retry', 'sequence-retry', 'payload-crc-retry', 'status8-retry']
        if expected_success:
            assert rc == (1 if label == 'ISR-press-release' else 0), (label, rc)
        if label == 'ISR-press-release':
            assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
            m.events = []; m.slots = []
            m.report_frames(payload=struct.pack('<BBHHBB', 0, 0, 644, 1589, 0, 0))
            assert m.run('syna_dev_isr', 0, CTX) == 1
            assert m.slots == [[INPUT, 0, 0]]
        elif expected_success and label != 'empty':
            assert m.u32(OUTPUT+12) == 8, (label, rc, m.calls, m.reads)
            assert bytes(m.uc.mem_read(m.u64(OUTPUT), 8)) == m.payload
        elif label == 'empty':
            assert m.u32(OUTPUT+12) == 0
        elif label in ['write-error', 'header-read-error', 'payload-read-error']:
            assert rc == -110 and m.u32(OUTPUT+12) == 0
        elif label in ['no-write-callback', 'no-read-callback']:
            assert rc == -245 and m.u32(OUTPUT+12) == 0
        elif label.startswith('allocation-'):
            assert m.allocation_count == m.allocation_error
            assert rc == (0 if label == 'allocation-report' else -243)
            assert m.u32(OUTPUT+12) == 0
        elif label in ['header-crc-exhausted', 'sequence-exhausted']:
            assert rc == 0 and m.u32(OUTPUT+12) == 0 and len(m.reads) == len(m.writes) == 6
            assert bytes(m.uc.mem_read(EVENT_ID, 1)) == b'\xfe'
        elif label == 'payload-crc-exhausted':
            assert rc == 0 and len(m.reads) == 8 and len(m.writes) == 7
            assert m.u32(OUTPUT+12) == 8 and bytes(m.uc.mem_read(m.u64(OUTPUT), 8)) == b'\0'*8
            assert bytes(m.uc.mem_read(EVENT_ID, 1)) == b'\x11'
        elif label == 'ISR-payload-crc-exhausted':
            assert rc == 1 and m.events == [[INPUT, 1, 330, 0], [INPUT, 1, 325, 0], [INPUT, 0, 0, 0]]
            assert not m.slots and m.u32(CTX+0x2cc) == 8
            assert bytes(m.uc.mem_read(m.u64(CTX+0x2c0), 8)) == b'\0'*8
        elif label == 'status8-exhausted':
            # acquire() left an actual synthetic config command response in the
            # original response buffer. Status 8 returns it via get_event_data.
            assert rc == 0 and m.u32(OUTPUT+12) == len(CONFIG)
            assert bytes(m.uc.mem_read(m.u64(OUTPUT), len(CONFIG))) == CONFIG
            assert bytes(m.uc.mem_read(EVENT_ID, 1)) == b'\x08'
        elif label in ['status0', 'status4']:
            assert rc == 0 and m.u32(OUTPUT+12) == 0
            assert bytes(m.uc.mem_read(EVENT_ID, 1)) == (b'\xff' if label == 'status4' else b'\0')
        if label in ['header-crc-retry', 'sequence-retry', 'status8-retry']:
            assert m.writes[0]['packet'] == m.writes[1]['packet']
        if label == 'payload-crc-retry':
            assert bytes.fromhex(m.writes[1]['packet'])[0] == 7
        if expected_success or label in ['header-crc-exhausted', 'sequence-exhausted', 'payload-crc-exhausted',
                                         'ISR-payload-crc-exhausted', 'status8-exhausted', 'status0', 'status4']:
            assert not m.responses, (label, m.responses)
        assert all(m.uc.mem_read(CORE+i, 1) == b'\0' for i in [0xf8, 0x138, 0x178, 0x240, 0x280, 0x2c0])
        cases.append(dict(case=label, status='PASS', result=rc, reads=m.reads, writes=m.writes,
                          allocations=m.allocations, waits=m.waits, events=m.events, slots=m.slots,
                          report_id=bytes(m.uc.mem_read(EVENT_ID, 1)).hex(), report_length=m.u32(CORE+0xcc),
                          output_length=m.u32(OUTPUT+12), isr_output_length=m.u32(CTX+0x2cc),
                          output=bytes(m.uc.mem_read(m.u64(OUTPUT), m.u32(OUTPUT+12))).hex() if m.u64(OUTPUT) else '',
                          response_status=bytes(m.uc.mem_read(CORE+0x1dc, 1)).hex()))
    for label in ['config-app-ISR', 'config-timeout-ISR', 'config-crc-exhausted-ISR']:
        m = Command(path)
        # Replace the earlier whole-command fixture with the original v2
        # write_message -> execute -> framing/CRC -> physical-byte boundary.
        m.put64(CORE+0x340, m.symbols['syna_tcm_v2_write_message'])
        m.responses = [(1, len(CONFIG), b'', ''), (1, len(CONFIG), CONFIG, '')]
        if label == 'config-timeout-ISR':
            m.responses = [-110]
        if label == 'config-crc-exhausted-ISR':
            m.responses = [m.responses[0]]+[(1, len(CONFIG), CONFIG, 'payload-crc')]*7
        rc = m.acquire()
        assert rc == (-110 if label == 'config-timeout-ISR' else 0)
        config_length = m.u32(CORE+0x18c)
        assert config_length == (0 if label == 'config-timeout-ISR' else len(CONFIG))
        config = bytes(m.uc.mem_read(m.u64(CORE+0x180), config_length)) if config_length else b''
        assert config == (CONFIG if label == 'config-app-ISR' else b'\0'*config_length)
        if label == 'config-app-ISR':
            app = bytearray(48)
            struct.pack_into('<HHH', app, 32, 1440, 3200, 10)
            struct.pack_into('<HH', app, 40, 17, 38)
            m.responses = [(1, 48, b'', ''), (1, 48, bytes(app), '')]
            assert m.run('syna_tcm_get_app_info', CORE, CORE+0x70) == 0
            assert [m.u32(CORE+i) for i in [8, 12, 16, 20, 24]] == [1440, 3200, 10, 17, 38]
        m.report_frames()
        assert m.run('syna_dev_isr', 0, CTX) == 1 and not m.responses
        if label == 'config-app-ISR':
            assert [INPUT, 3, 53, 64400] in m.events and [INPUT, 3, 54, 158900] in m.events
        elif label == 'config-timeout-ISR':
            assert not m.events and not m.slots
        else:
            assert m.events == [[INPUT, 1, 330, 0], [INPUT, 1, 325, 0], [INPUT, 0, 0, 0]] and not m.slots
        cases.append(dict(case=label, status='PASS', result=rc, config=config.hex(), config_length=config_length,
                          events=m.events, reads=m.reads, writes=m.writes))
    return cases


def main():
    cases = []; drivers = {}; sources = {}
    tool = '/root/AAA/twrp/prebuilts/clang/host/linux-x86/clang-r547379/bin/llvm-objdump'
    symbols = ['syna_tcm_v2_execute_cmd_request', 'syna_tcm_v2_write', 'syna_tcm_v2_read',
               'syna_tcm_v2_write_message', 'syna_tcm_v2_read_message', 'syna_tcm_enable_report',
               'syna_tcm_enable_touch_raw', 'syna_tcm_preserve_touch_report_config', 'syna_tcm_get_app_info']
    for sample in ['os4-current', 'os4-stable']:
        path = ROOT/'firmware/samples'/sample/'analysis/vendor_dlkm/lib/modules/synaptics_tcm2.ko'
        assert sha(path) in LAYOUTS
        drivers[sample] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
        disasm = ROOT/'logs'/f'{sample}-touch-v2-command.disasm'
        disasm.write_bytes(subprocess.check_output([tool, '-dr', '--disassemble-symbols='+','.join(symbols), str(path)]))
        sources[str(disasm.relative_to(ROOT))] = sha(disasm)
        results = exercise(path)
        cases.extend(dict(sample=sample, **c) for c in results)
        print('PASS', sample, len(results), 'cases', flush=True)
    tests = [Path(__file__).resolve()] + [ROOT/'tests'/name for name in ['touch_message_emulation.py',
        'touch_configuration_emulation.py', 'touch_startup_emulation.py', 'haptics_driver_emulation.py',
        'haptics-emulator-dependencies.json']]
    dependencies = sorted(p for p in DEPS.rglob('*') if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name))
    (ROOT/'logs/touch-v2-command-emulation.json').write_text(json.dumps(dict(status='PASS', scope=__doc__.strip(),
        cases=cases, drivers=drivers, sources=sources, tests={str(p.relative_to(ROOT)):sha(p) for p in tests},
        emulator_files={str(p.relative_to(ROOT)):sha(p) for p in dependencies}), indent=2)+'\n')


if __name__ == '__main__':
    main()
