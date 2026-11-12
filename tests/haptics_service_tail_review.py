#!/usr/bin/env python3
"""Join original OS4 PCM/data setup to thread construction and XML consumption.

Uses prior partial constructor: alternate-device/map initialization and
calibration body are still skipped. Original hash-container static init runs.
Original service-thread constructor and XML consumers execute; libxml nodes,
content and libc/Android Thread/refcount/ALSA calls are explicit fixtures.
The service worker is entered separately by an explicit scheduler boundary and
stops at its first timed wait. AAC worker is never scheduled. No full Android
service lifecycle, real ALSA/driver/DSP or motor is executed.
Ordinary on then uses the XML-derived global without pre-filling its long-id;
only the restore-complete flag and null callback remain explicit boundaries.
"""
import json
import io
import re
import struct
from pathlib import Path
import xml.etree.ElementTree as ET

from haptics_pcm_init_review import PCM
from haptics_driver_emulation import ROOT, DEPS, sha
from elftools.elf.elffile import ELFFile
from haptics_service_route_review import Service, OBJ, RETURN
from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X8, UC_ARM64_REG_X19, UC_ARM64_REG_X20, UC_ARM64_REG_X30, UC_ARM64_REG_PC, UC_ARM64_REG_SP

ARENA = 0x7000000
RUN = RETURN + 0x300
XMLFREE = RETURN + 0x400
ALSA = 0x2000000


class Tail(PCM):
    def __init__(self, path, disasm, label, props, plugin, plugin_disasm, xml, relocations, tinyalsa):
        super().__init__(path, disasm, 'normal', props, plugin, plugin_disasm)
        self.scenario = label
        self.u.mem_map(ARENA, 0x100000)
        self.arena = ARENA
        self.allocations, self.content_allocations, self.nodes = {}, set(), {}
        self.thread = None
        self.run_requests, self.timed_waits = [], []
        self.pcm_config, self.peer_messages = None, []
        self.tokens = []
        self.xml_root = ET.fromstring(xml.read_bytes())
        if label == 'xml-long42':
            self.xml_root.find('long_vib_id/data').text = '42'
        if label == 'xml-no-long':
            self.xml_root.remove(self.xml_root.find('long_vib_id'))
        # These two external identities are decoded from the original Android
        # packed relocation section by llvm-readelf, not guessed from zeros.
        for offset, symbol, kind in [
            (0x30728, '_ZN7android6Thread3runEPKcim', 'R_AARCH64_ABS64'),
            (0x30db0, 'xmlFree', 'R_AARCH64_GLOB_DAT')]:
            assert re.search(r'^0*' + format(offset, 'x') + r'\s+\S+\s+' + kind +
                             r'\s+0+\s+' + re.escape(symbol) + r' \+ 0$', relocations, re.M)
        self.put64(0x30728, RUN)
        self.put64(0x30db0, OBJ + 0x10000)
        self.put64(OBJ + 0x10000, XMLFREE)
        self.document = self.allocate(64)
        self.root_node = self.xml_node(self.xml_root)
        assert sha(tinyalsa) == 'c5008f3a3e1257e0f4042331ebc6279ca04347d2027ac5be4d8b0ddee2350c7b'
        elf = ELFFile(io.BytesIO(tinyalsa.read_bytes()))
        for segment in elf.iter_segments():
            if segment['p_type'] == 'PT_LOAD':
                start = segment['p_vaddr'] & ~4095
                length = (segment['p_vaddr'] - start + segment['p_memsz'] + 4095) & ~4095
                self.u.mem_map(ALSA + start, length)
                self.u.mem_write(ALSA + segment['p_vaddr'], segment.data())
        # Only the original leaf conversion runs; no loader or PCM open body.
        assert next(s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()
                    if s.name == 'pcm_frames_to_bytes') == 0x62f4

    def allocate(self, count):
        assert 0 < count <= 0x10000
        result = self.arena
        self.arena += (count + 15) & ~15
        assert self.arena < ARENA + 0x100000
        self.allocations[result] = count
        return result

    def string(self, text):
        value = text.encode() + b'\0'
        result = self.allocate(len(value))
        self.u.mem_write(result, value)
        return result

    def xml_node(self, element):
        pointer = self.allocate(128)
        is_text = isinstance(element, str)
        self.put64(pointer + 16, self.string('text' if is_text else element.tag))
        self.nodes[pointer] = element if is_text else ''.join(element.itertext())
        children = []
        if not is_text:
            if element.text:
                children.append(self.xml_node(element.text))
            for child in element:
                children.append(self.xml_node(child))
                if child.tail:
                    children.append(self.xml_node(child.tail))
        if children:
            self.put64(pointer + 24, children[0])
            for a, b in zip(children, children[1:]):
                self.put64(a + 48, b)
        return pointer

    def hook(self, u, address, size, data):
        a = [self.arg(i) for i in range(8)]
        record = dict(phase=self.phase)
        if address == 0x264d0:
            assert self.phase == 'worker' and a[0] == 4096
            self.calls.append(dict(call='original-pcm-frames-return', phase=self.phase, bytes=a[0]))
            return
        if address == RUN:
            assert a[0] == self.thread and self.text(a[1]) == 'DynamicEffectThread'
            assert a[2:4] == [0, 0]
            result = -11 if self.scenario == 'thread-run-error' else 0
            record.update(call='Android-Thread-run', result=result, callback_executed=False)
            self.run_requests.append(record.copy())
        elif address == XMLFREE:
            assert a[0] in self.content_allocations
            self.content_allocations.remove(a[0])
            record.update(call='xmlFree', pointer=a[0])
            result = 0
        elif address not in self.plt:
            return super().hook(u, address, size, data)
        else:
            name = self.plt[address]
            record['call'] = name
            if name == '__cxa_atexit':
                assert a[0] == 0x118c0 and a[1] in [0x34268, 0x34290, 0x342b8]
                result = 0
            elif name in ['_ZN7android7RefBaseC2Ev', '_ZN7android6ThreadC2Eb',
                          '_ZNK7android7RefBase9incStrongEPKv']:
                record['object'] = a[0]
                if name == '_ZN7android6ThreadC2Eb':
                    self.thread = a[0]
                    assert a[1:3] == [0x30a50, 1]
                result = 0
            elif name in ['_Znwm', '_Znam'] and self.phase in ['startup-tail', 'worker']:
                record['size'] = a[0]
                result = self.allocate(a[0])
            elif name == '_ZdlPv' and self.phase in ['startup-tail', 'worker']:
                assert a[0] in self.allocations
                record['pointer'] = a[0]
                result = 0
            elif name == 'fopen' and self.phase == 'startup-tail':
                assert self.text(a[0]) == '/data/local/log/hapticDump.bin' and self.text(a[1]) == 'wb+'
                record.update(path=self.text(a[0]), mode=self.text(a[1]))
                result = 0  # Missing dump directory is explicit; no host file.
            elif name in ['pthread_mutex_init', 'pthread_condattr_init', 'pthread_condattr_setclock',
                          'pthread_cond_init', 'pthread_condattr_destroy', 'pthread_mutex_lock',
                          'pthread_mutex_unlock']:
                record['args'] = a[:2]
                if name == 'pthread_condattr_setclock':
                    assert a[1] == 1
                result = 0
            elif name == 'xmlInitParser' or name == 'xmlCleanupParser':
                result = 0
            elif name == 'xmlReadFile':
                assert self.text(a[0]) == '/odm/etc/waveform_conf.xml' and a[1:3] == [0, 0]
                record['path'] = self.text(a[0])
                result = 0 if self.scenario == 'xml-absent' else self.document
            elif name == 'xmlDocGetRootElement':
                assert a[0] == self.document
                result = self.root_node
            elif name == 'xmlStrcmp':
                left, right = self.text(a[0]), self.text(a[1])
                record.update(left=left, right=right)
                result = (left > right) - (left < right)
            elif name == 'xmlNodeGetContent':
                assert a[0] in self.nodes
                value = self.nodes[a[0]]
                result = self.string(value)
                self.content_allocations.add(result)
                record['value'] = value
            elif name == 'strtol':
                assert a[1:3] == [0, 10]
                value = self.text(a[0])
                match = re.match(r'\s*([+-]?\d+)', value)
                assert match, value
                result = int(match.group(1))
                record['value'] = value
            elif name == 'strtok':
                assert self.text(a[1]) == ','
                if a[0]:
                    value = self.text(a[0])
                    self.tokens = []
                    for match in re.finditer('[^,]+', value):
                        pointer = a[0] + match.start()
                        u.mem_write(a[0] + match.end(), b'\0')
                        self.tokens.append(pointer)
                result = self.tokens.pop(0) if self.tokens else 0
            elif name == '_ZNSt3__112__next_primeEm':
                value = max(2, a[0])
                while any(value % divisor == 0 for divisor in range(2, int(value ** .5) + 1)):
                    value += 1
                record['requested'] = a[0]
                result = value
            elif name == 'xmlFreeDoc':
                assert a[0] == self.document and not self.content_allocations
                result = 0
            elif name == 'property_get_bool' and self.phase == 'startup-tail':
                key = self.text(a[0])
                assert key == 'ro.odm.mm.vibrator.lowPowerMode'
                record['key'] = key
                result = int(self.props[key] == 'true')
            elif name == 'property_get_int32':
                key = self.text(a[0])
                assert key == 'ro.odm.mm.vibrator.slide_effect_protect_time'
                result = int(self.props[key])
                record['key'] = key
            elif name == '_ZNK7android6Thread11exitPendingEv':
                assert a[0] == self.thread
                result = 0
            elif name == 'socket':
                assert self.phase == 'worker' and a[:3] == [1, 5, 0]
                result = 55
            elif name == '__strlcpy_chk':
                assert self.text(a[1]) == '/dev/socket/vibrator_audio_socket_0'
                assert a[2:4] == [36, 108]
                value = self.text(a[1]).encode() + b'\0'
                u.mem_write(a[0], value)
                result = len(value) - 1
            elif name == 'connect':
                assert a[0] == 55 and a[2] == 110
                assert bytes(u.mem_read(a[1], 2)) == b'\1\0'
                assert self.text(a[1] + 2) == '/dev/socket/vibrator_audio_socket_0'
                result = 0
            elif name == 'setsockopt':
                assert a[:3] == [55, 1, 21] and a[4] == 16
                record['timeout'] = list(struct.unpack('<qq', bytes(u.mem_read(a[3], 16))))
                result = 0
            elif name == 'write' and self.phase == 'worker':
                assert a[0] == 55 and a[2] == 72
                record['data'] = bytes(u.mem_read(a[1], 72)).hex()
                self.peer_messages.append(record['data'])
                result = 72
            elif name == 'poll':
                assert a[1:3] == [1, 500]
                assert struct.unpack('<iH', bytes(u.mem_read(a[0], 6))) == (55, 1)
                u.mem_write(a[0] + 6, struct.pack('<H', 0 if self.scenario == 'audio-socket-timeout' else 1))
                result = 0 if self.scenario == 'audio-socket-timeout' else 1
            elif name == 'read' and self.phase == 'worker':
                assert a[0] == 55 and a[2] == 2
                u.mem_write(a[1], b'\1\0')
                result = 2
            elif name == 'mixer_get_ctl_by_name' and self.phase == 'worker':
                assert a[0] == OBJ + 0x9000
                control = self.text(a[1])
                result = self.allocate(16)
                self.controls[result] = control
                record['control'] = control
            elif name == 'mixer_ctl_set_array':
                assert a[0] in self.controls and self.controls[a[0]] == 'XR_TDM7_RX' and a[2] == 3
                record.update(control=self.controls[a[0]], values=list(struct.unpack('<QQQ', bytes(u.mem_read(a[1], 24)))))
                assert record['values'] == [48000, 24, 4]
                result = -5 if self.scenario == 'pcm-array-error' else 0
            elif name == 'mixer_ctl_set_value' and self.phase == 'worker':
                assert a[0] in self.controls and a[1] == 0
                record.update(control=self.controls[a[0]], value=a[2])
                result = 0
            elif name == 'pcm_open':
                assert a[:3] == [0, 9, 0]
                self.pcm_config = list(struct.unpack('<IIIIIIII', bytes(u.mem_read(a[3], 32))))
                record.update(card=a[0], device=a[1], flags=a[2], config=self.pcm_config)
                result = ARENA + 0xf0000
                u.mem_write(result + 0xa0, struct.pack('<IIIIIIII', *self.pcm_config))
            elif name == 'pcm_is_ready':
                assert a[0] == ARENA + 0xf0000
                result = 1
            elif name == 'pcm_get_buffer_size':
                assert a[0] == ARENA + 0xf0000
                result = 1024  # Explicit synthetic ALSA frame count.
            elif name == 'pcm_frames_to_bytes':
                assert a[:2] == [ARENA + 0xf0000, 1024]
                self.calls.append(dict(call=name, phase=self.phase, frames=1024,
                                       original_entry=ALSA + 0x62f4))
                u.reg_write(UC_ARM64_REG_PC, ALSA + 0x62f4)
                return
            elif name in ['_ZN7android7MiEventC1Ej', '_ZN7android7MiEventD1Ev']:
                result = 0
            elif name == 'clock_gettime' and self.phase == 'worker':
                assert a[0] == 1
                u.mem_write(a[1], struct.pack('<qq', 100, 0))
                result = 0
            elif name == 'pthread_cond_timedwait':
                assert a[:2] == [self.thread + 0xb0, self.thread + 0x88]
                record['deadline'] = list(struct.unpack('<qq', bytes(u.mem_read(a[2], 16))))
                record['call'] = name
                self.timed_waits.append(record)
                self.calls.append(record)
                u.emu_stop()
                return
            elif self.phase in ['route', 'ordinary-on']:
                return Service.hook(self, u, address, size, data)
            else:
                return super().hook(u, address, size, data)
        record['result'] = result
        self.calls.append(record)
        self.reply(result)

    def containers(self):
        result = {}
        for name, address in [('mapping', 0x34290), ('no_dvl', 0x342b8), ('no_svc', 0x342e0)]:
            count = self.u64(address + 24)
            pointer = self.u64(address + 16)
            values = {}
            for _ in range(count):
                assert pointer in self.allocations
                key, value = struct.unpack('<ii', bytes(self.u.mem_read(pointer + 16, 8)))
                assert key not in values
                values[key] = value if name == 'mapping' else None
                pointer = self.u64(pointer)
            assert pointer == 0
            result[name] = values
        return result

    def tail(self):
        self.phase = 'hash-init'
        self.interval(0x11820, 0x118b0)
        state = self.construct()
        self.phase = 'startup-tail'
        self.u.reg_write(UC_ARM64_REG_X19, OBJ)
        self.u.reg_write(UC_ARM64_REG_X20, OBJ + 0x78)
        # Outer prologue was skipped; reserve its above-SP scratch area.
        self.u.reg_write(UC_ARM64_REG_SP, 0x501e000)
        try:
            self.interval(0x1349c, 0x13bb8)
        except Exception:
            print('Tail failure PC=', hex(self.u.reg_read(UC_ARM64_REG_PC)), 'args=', [hex(self.arg(i)) for i in range(8)])
            raise
        state.update(thread=self.thread, data=self.u64(OBJ + 0x68),
                     long_id=int.from_bytes(self.u.mem_read(0x3402c, 4), 'little'),
                     low_power=self.u.mem_read(0x34258, 1)[0],
                     protect_ms=int.from_bytes(self.u.mem_read(0x34320, 4), 'little'),
                     buffer_samples=int.from_bytes(self.u.mem_read(self.thread + 0xf0, 4), 'little'),
                     buffer=self.u64(self.thread + 0xf8), containers=self.containers())
        return state

    def worker(self):
        assert self.run_requests[0]['result'] == 0
        self.phase = 'worker'
        boundary = len(self.calls)
        self.u.reg_write(UC_ARM64_REG_X0, self.thread)
        self.u.reg_write(UC_ARM64_REG_SP, 0x501e000)
        self.u.reg_write(UC_ARM64_REG_X30, RETURN)
        self.u.emu_start(0x272f0, RETURN, count=100000, timeout=2000000)
        waits = [a for a, name in self.plt.items() if name == 'pthread_cond_timedwait']
        assert len(waits) == 1 and self.u.reg_read(UC_ARM64_REG_PC) == waits[0]
        assert len(self.timed_waits) == 1
        return self.calls[boundary:]


def main():
    cases, sources = [], {}
    for sample in ['os4-current', 'os4-stable']:
        base = ROOT / 'firmware/samples' / sample / 'analysis/odm'
        path = base / 'bin/hw/vendor.xring.hardware.vibratorfeature.service'
        disasm = ROOT / 'logs' / (sample + '-vibrator-service.disasm')
        properties = base / 'etc/build.prop'
        plugin = base / 'lib64/libaachaptics.so'
        plugin_disasm = ROOT / 'logs' / (sample + '-haptics-aac-init.disasm')
        relocations = ROOT / 'logs' / (sample + '-vibrator-service-relocations.txt')
        xml = base / 'etc/waveform_conf.xml'
        tinyalsa = base.parent / 'vendor/lib64/libtinyalsa.so'
        props = dict(line.split('=', 1) for line in properties.read_text().splitlines() if '=' in line and not line.startswith('#'))
        for p in [path, disasm, properties, plugin, plugin_disasm, xml, relocations, tinyalsa]:
            sources[str(p.relative_to(ROOT))] = sha(p)
        for label in ['normal', 'xml-absent', 'xml-no-long', 'xml-long42', 'thread-run-error',
                      'pcm-array-error', 'audio-socket-timeout']:
            m = Tail(path, disasm.read_text(), label, props, plugin, plugin_disasm.read_text(), xml, relocations.read_text(), tinyalsa)
            state = m.tail()
            expected_long = 42 if label == 'xml-long42' else (35 if label in ['xml-absent', 'xml-no-long'] else 31)
            assert state['long_id'] == expected_long, (sample, label, state)
            assert state['low_power'] == 1 and state['protect_ms'] == 20
            assert len(m.run_requests) == 1 and m.run_requests[0]['result'] == (-11 if label == 'thread-run-error' else 0)
            assert state['buffer_samples'] > 0
            if label != 'xml-absent':
                root = m.xml_root
                mapping = root.find('waveform_id_mapping')
                keys = [int(e.text) for e in mapping.findall('key')]
                values = [int(e.text) for e in mapping.findall('value')]
                assert state['containers']['mapping'] == dict(zip(keys, values))
                for name in ['no_dvl', 'no_svc']:
                    assert set(map(int, root.findtext(name + '/data').split(','))) == set(state['containers'][name])
            else:
                assert state['containers'] == dict(mapping={}, no_dvl={}, no_svc={})
            assert not m.content_allocations
            worker = [] if label == 'thread-run-error' else m.worker()
            if worker:
                controls = [(c['control'], c['value']) for c in worker if c['call'] == 'mixer_ctl_set_value']
                expected_controls = [] if label == 'pcm-array-error' else [
                    ('Haptics Source', 1), ('ASP Mode', 1), ('ASP PCM Slot', 1),
                    ('audio_tdm_fmtchs', 8), ('XR_TDM7_RX Mixer XR_media7', 1)]
                assert controls == expected_controls, (label, controls)
                assert m.pcm_config == [1, 48000, 480, 4, 3, 120, 2147483647, 120]
                assert len(m.peer_messages) == (2 if label == 'audio-socket-timeout' else 1)
                assert all(bytes.fromhex(message) == struct.pack('<III', 42, 1, 1) + bytes(60) for message in m.peer_messages)
                assert m.timed_waits[0]['deadline'] == [102, 0]
                assert m.u.mem_read(state['backend'] + 8, 1)[0] == 1
            boundary = len(m.calls)
            m.phase = 'ordinary-on'
            m.u.mem_write(0x34308, b'\1')  # Calibration body is still a boundary.
            m.run(0x13e04, OBJ, 80, OBJ + 0x4000)
            ordinary = m.calls[boundary:]
            assert [c['call'] for c in ordinary] == ['_ZN7android7MiEventC1Ej', 'write', 'upload', 'write',
                                                    '_ZN7android7MiEventD1Ev', 'AStatus_newOk']
            assert bytes.fromhex(ordinary[2]['custom']) == struct.pack('<HH', 0, expected_long)
            assert bytes.fromhex(ordinary[1]['data'])[16:] == struct.pack('<HHi', 21, 96, 100)
            assert bytes.fromhex(ordinary[3]['data'])[16:] == struct.pack('<HHi', 21, 7, 1)
            cases.append(dict(sample=sample, case=label, status='PASS', state=state,
                              calls=m.calls, plugin_calls=m.plugin_calls, logs=m.logs,
                              run_requests=m.run_requests, worker=worker, pcm_config=m.pcm_config,
                              peer_messages=m.peer_messages, ordinary_on=ordinary))
    files = [Path(__file__).resolve()] + [ROOT / 'tests' / (n + '.py') for n in
             ['haptics_pcm_init_review', 'haptics_service_init_review', 'haptics_service_route_review',
              'haptics_service_request_emulation', 'haptics_driver_emulation',
              'haptics_playback_emulation', 'haptics_lifecycle_emulation']]
    files += [ROOT / 'tests/haptics-emulator-dependencies.json', ROOT / 'scripts/firmware_facts.py']
    report = dict(status='PASS', scope=__doc__, cases=cases, sources=sources,
                  tests={str(p.relative_to(ROOT)): sha(p) for p in files},
                  emulator_files={str(p.relative_to(ROOT)): sha(p) for p in DEPS.rglob('*')
                                  if p.is_file() and (p.suffix in ['.py', '.so'] or '.so.' in p.name)})
    (ROOT / 'logs/haptics-service-tail-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS:', len(cases), 'original service thread-constructor/XML cases; worker/hardware boundary explicit')


if __name__ == '__main__':
    main()
