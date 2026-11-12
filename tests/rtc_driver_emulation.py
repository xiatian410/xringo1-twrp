#!/usr/bin/env python3
"""Execute original six-profile ARM64 RTC read/set callbacks and OS4 refresh.

MMIO reads/writes, spinlocks, PMIC, reset, delays and calendar conversion are
explicit fixtures. No kernel boot, hctosys, hardware clock or host time change.
Original instructions/relocations use the shared bounded module emulator;
unknown imports and instruction-budget exhaustion fail closed.
"""
import json
import struct
import sys
from pathlib import Path
from haptics_driver_emulation import Module, ROOT, MASK, UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_PC, sha
sys.path.insert(0, str(ROOT/'scripts'))
from acquire_firmware import parse_manifest
from firmware_facts import boot_parts, ramdisk_entries

DEV, CTX, MMIO, CRG, TM = 0x4000000, 0x4010000, 0x4020000, 0x4030000, 0x4040000
SAMPLES = ['os2-initial', 'os2-final', 'os3-initial', 'os3-final', 'os4-current', 'os4-stable']


class Rtc(Module):
    def __init__(self, path):
        super().__init__(path)
        self.intercept('readl')
        self.intercept('writel')
        self.put64(DEV+0x98, CTX)
        self.put64(CTX+0x10, DEV)
        self.put64(CTX+0x18, MMIO)
        self.put64(CTX+0x38, 0x1234)
        self.put64(CTX+0x40, CRG)
        self.put32(CTX+0x34, 1)
        self.put32(self.symbols['g_rtc_saved'], 0)
        self.reads = []
        self.writes = []
        self.converted = []
        self.pmic = []
        self.pmic_error = 0
        self.reset_error = None
        self.seconds = 1794326400
        self.values = {MMIO: [123], MMIO+4: [100]}
        self.locked = False

    def on_code(self, uc, address, size, data):
        if address not in self.hooks:
            return
        name = self.hooks[address]
        a = [self.arg(i) for i in range(5)]
        self.calls.append(name)
        result = 0
        if name == 'readl':
            assert a[0] in self.values, hex(a[0])
            values = self.values[a[0]]
            result = values.pop(0) if len(values) > 1 else values[0]
            self.reads.append(dict(address=a[0], value=result))
        elif name == 'writel':
            assert a[1] in [MMIO+4, MMIO+8, MMIO+0x20, CRG, CRG+4]
            self.writes.append(dict(address=a[1], value=a[0] & 0xffffffff))
        elif name == '_raw_spin_lock_irqsave':
            assert not self.locked and a[0] == CTX+0x30
            self.locked = True
            result = 0x2468
        elif name == '_raw_spin_unlock_irqrestore':
            assert self.locked and a[:2] == [CTX+0x30, 0x2468]
            self.locked = False
        elif name == 'rtc_time64_to_tm':
            self.converted.append(a[0])
            assert a[1] == TM
            # Calendar algorithm is outside this callback test. Sentinel output
            # proves the actual driver passes through the supplied tm pointer.
            self.put32(TM, 0x12345678)
        elif name == 'rtc_tm_to_time64':
            result = self.seconds
        elif name in ['pmic_rtc_gettime', 'pmic_rtc_settime']:
            self.pmic.append(name)
            result = self.pmic_error
        elif name in ['reset_control_assert', 'reset_control_deassert']:
            assert a[0] == 0x1234
            result = -5 if self.reset_error == name else 0
        elif name == '__const_udelay':
            assert a[0] > 0
        elif name == '_dev_err':
            self.messages.append(self.string(a[1]))
        else:
            raise AssertionError(('unhandled RTC boundary', name, a))
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def main():
    cases, modules = [], {}
    origins, origin_sources = [], []
    for sample in SAMPLES:
        paths = list((ROOT/'firmware/samples'/sample/'analysis/vendor_boot').rglob('dw_apb_rtc.ko'))
        assert len(paths) == 1
        path = paths[0]
        modules[str(path)] = sha(path)
        folder = ROOT/'firmware/samples'/sample
        manifest_path, image_path = folder/'payload-manifest.pb', folder/'vendor_boot.img'
        expected_image = parse_manifest(manifest_path.read_bytes())['partitions']['vendor_boot']
        assert image_path.stat().st_size == expected_image['size']
        assert sha(image_path) == expected_image['sha256']
        _, parts = boot_parts(image_path.read_bytes())
        entry_name = str(path.relative_to(folder/'analysis/vendor_boot/fragment-0'))
        original = [entry[-1] for entry in ramdisk_entries(parts['fragment-0']) if entry[0] == entry_name]
        assert len(original) == 1 and original[0] == path.read_bytes()
        origins.append(dict(profile=sample, image_sha256=expected_image['sha256'],
                            entry=entry_name, module_sha256=sha(path), byte_match=True))
        origin_sources.extend([manifest_path, image_path])
        del parts, original
        for label, count, saved, frequency in [
                ('zero', 0, 0, 1), ('utc', 1794326400, 0, 1),
                ('divider', 987654, 123, 1000), ('wrap', 0xfffffff0, 0x30, 1),
                ('zero-frequency', 123, 0, 0)]:
            m = Rtc(path)
            m.values[MMIO] = [count]
            m.put32(CTX+0x34, frequency)
            m.put32(m.symbols['g_rtc_saved'], saved)
            rc = m.run('dw_rtc_read_time', DEV, TM)
            expected = ((count+saved) & 0xffffffff)//frequency if frequency else 0
            assert rc == 0 and m.converted == [expected] and not m.locked
            assert m.u32(TM) == 0x12345678 and not m.pmic and not m.writes
            cases.append(dict(profile=sample, case='read-'+label, status='PASS', seconds=expected,
                              rc=rc, calls=m.calls, reads=m.reads))
        for label, alarm, current, failure in [
                ('success', 100, 123, 0), ('pmic-failure', 100, 123, -5),
                ('alarm-adjust', 1000, 123, 0)]:
            m = Rtc(path)
            m.values[MMIO] = [current]
            m.values[MMIO+4] = [alarm]
            m.pmic_error = failure
            m.put32(m.symbols['g_rtc_saved'], 50)
            rc = m.run('dw_rtc_set_time', DEV, TM)
            assert rc == failure and not m.locked and m.pmic == ['pmic_rtc_settime']
            assert m.u32(m.symbols['g_rtc_saved']) == (m.seconds-current) & 0xffffffff
            expected = [dict(address=MMIO+4, value=(alarm-m.seconds+current+50) & 0xffffffff)] if alarm > current else []
            assert m.writes == expected, (sample, label, m.writes, expected)
            cases.append(dict(profile=sample, case='set-'+label, status='PASS', rc=rc,
                              saved=m.u32(m.symbols['g_rtc_saved']), calls=m.calls, writes=m.writes,
                              observation='PMIC failure does not roll back the software saved counter offset.'))
        if sample.startswith('os4-'):
            for label, pmic, reset in [('success', 0, None), ('pmic-failure', -5, None),
                                       ('assert-failure', 0, 'reset_control_assert'),
                                       ('deassert-failure', 0, 'reset_control_deassert')]:
                m = Rtc(path)
                m.values[MMIO], m.values[MMIO+4] = [123], [100]
                m.put32(m.symbols['g_rtc_saved'], 50)
                m.pmic_error, m.reset_error = pmic, reset
                rc = m.run('dw_rtc_cnt_refresh', CTX)
                assert rc == (-5 if reset else 0)
                assert m.pmic == ['pmic_rtc_gettime']
                writes = [dict(address=CRG+4, value=1)]
                if reset != 'reset_control_assert':
                    value = 173 if pmic else m.seconds
                    writes += [dict(address=MMIO+0x20, value=1024), dict(address=MMIO+8, value=value)]
                    if not reset:
                        writes += [dict(address=CRG, value=1)]
                    assert m.u32(m.symbols['g_rtc_saved']) == 0
                else:
                    assert m.u32(m.symbols['g_rtc_saved']) == 50
                assert m.writes == writes, (label, m.writes)
                cases.append(dict(profile=sample, case='refresh-'+label, status='PASS', rc=rc,
                                  calls=m.calls, writes=m.writes,
                                  observation='PMIC failure uses current counter+saved; reset failures propagate.'))
        print('PASS', sample, flush=True)
    index = json.loads((ROOT/'simulation-report.json').read_text())
    provenance = json.loads(Path(index['image']).with_name(Path(index['image']).stem+'-sources.json').read_text())
    assert all(sha(Path(p)) == digest for p, digest in provenance['files'].items())
    sources = [Path(__file__).resolve(), ROOT/'tests/haptics_driver_emulation.py', ROOT/'scripts/firmware_facts.py',
               ROOT/'scripts/acquire_firmware.py', *origin_sources]
    report = dict(status='PASS', scope=__doc__, cases=cases, modules=modules, origins=origins,
                  sources={str(p): sha(p) for p in sources}, image_sha256=index['image_sha256'],
                  production_sources=len(provenance['files']), production_changes=False,
                  limits=['No full probe/hctosys/calendar algorithms/real MMIO/PMIC, physical drift or battery-loss test.',
                          'Zero divisor and 32bit wrap are observed original callback behavior, not accepted hardware configuration.',
                          'No reason established to enable QCOM_RTC_FIX or to modify stock modules.'])
    (ROOT/'logs/rtc-driver-emulation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('PASS', len(cases), 'original RTC callback cases')


if __name__ == '__main__':
    main()
