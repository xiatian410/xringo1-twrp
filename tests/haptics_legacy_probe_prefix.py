#!/usr/bin/env python3
"""Execute the original OS2/OS3 probe prefix through DT, power/reset and PLL.

The final PLL result is deliberately failed so the run never reaches DSP upload,
input registration, self-test, IRQ delivery or motor hardware. Kernel services,
merged-DT property reads, regulator/GPIO/pinctrl state and sleeps are fixtures.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools/haptics-emulator-python'))
from haptics_driver_emulation import Module, MASK, sha, UC_ARM64_REG_X0, UC_ARM64_REG_X30, UC_ARM64_REG_SP, UC_ARM64_REG_PC

CTX = 0x4000000
DEV = 0x4060000
REG = 0x4070000


def signed(value):
    value &= 0xffffffff
    return value - 0x100000000 if value & 0x80000000 else value


class Prefix(Module):
    def __init__(self, path, properties):
        super().__init__(path)
        assert 'cs40l26_probe' in self.symbols and 'cs40l26_set_pll_loop' in self.symbols
        self.intercept('cs40l26_set_pll_loop')
        self.properties = properties
        self.boundaries = []
        self.calls_probe = []
        self.service_results = dict(alloc_workqueue=0x4080000, devm_regulator_bulk_get=0,
                                    regulator_bulk_enable=0, devm_gpiod_get_optional=0x4088000,
                                    devm_pinctrl_get=0x4098000, pinctrl_lookup_state=0x40a0000,
                                    pinctrl_select_state=0, gpiod_set_value_cansleep=0, usleep_range_state=0,
                                    cs40l26_set_pll_loop=-5, cs40l26_remove=0,
                                    regmap_update_bits_base=0)
        self.ctx_initialized = False
        self.allocations = []
        self.regmap_reads = []
        self.remove_entries = 0

    def prepare(self):
        self.uc.mem_write(CTX, b'\0' * 0x2000)
        self.put64(CTX, DEV)
        self.put64(CTX + 8, REG)
        self.ctx_initialized = True

    def run_probe(self):
        self.prepare()
        self.uc.reg_write(UC_ARM64_REG_X0, CTX)
        self.uc.reg_write(UC_ARM64_REG_SP, 0x5020000 - 16)
        self.uc.reg_write(UC_ARM64_REG_X30, self.return_address)
        self.uc.emu_start(self.symbols['cs40l26_probe'], self.return_address,
                          timeout=10000000, count=1000000)
        assert self.uc.reg_read(UC_ARM64_REG_PC) == self.return_address, 'legacy probe instruction budget exhausted'
        return signed(self.arg(0))

    def on_code(self, uc, address, size, data):
        if address == self.symbols['cs40l26_remove']:
            self.remove_entries += 1
        name = self.hooks.get(address)
        if name is None:
            return
        args = [self.arg(i) for i in range(6)]
        result = None
        if name in self.service_results:
            result = self.service_results[name]
            if name == 'cs40l26_set_pll_loop':
                self.calls_probe.append(name)
                self.boundaries.append(dict(name=name, args=args[:2], result=result, injected=True))
            elif name == 'cs40l26_remove':
                self.calls_probe.append(name)
                self.boundaries.append(dict(name=name, args=args[:1], result=result, fixture='remove-not-executed'))
        elif name == 'regmap_read':
            result = -5
            self.regmap_reads.append(dict(address=args[1], result=result))
            self.boundaries.append(dict(name=name, address=args[1], result=result,
                                        fixture='injected-read-error'))
        elif name in ['device_property_present', 'device_property_read_u32_array']:
            key = self.string(args[1])
            value = self.properties.get(key)
            if name == 'device_property_present':
                result = int(key in self.properties)
            elif value is None:
                result = -22
            else:
                assert isinstance(value, list) and all(isinstance(x, int) for x in value), (key, value)
                if args[2] == 0:
                    result = len(value)
                elif args[3] < len(value):
                    result = -75
                else:
                    for i, element in enumerate(value):
                        self.put32(args[2] + 4 * i, element)
                    result = 0
            self.boundaries.append(dict(name=name, property=key, supplied=value, result=result))
        elif name in ['__mutex_init', 'init_timer_key', 'device_get_child_node_count',
                      'device_get_next_child_node', 'disable_irq', '__pm_runtime_use_autosuspend',
                      '__pm_runtime_set_autosuspend_delay', 'pm_runtime_enable', '__pm_runtime_disable',
                      'cancel_work_sync', 'destroy_workqueue', 'timer_delete_sync', 'debugfs_remove']:
            result = 0
            if name == 'device_get_child_node_count':
                self.boundaries.append(dict(name=name, result=0, fixture='no-children'))
            elif name == 'disable_irq':
                self.boundaries.append(dict(name=name, args=args[:2], result=0, fixture='IRQ service'))
        elif name in ['devm_kmalloc', '__kmalloc', '__kmalloc_noprof']:
            length = args[1] if name == 'devm_kmalloc' else args[0]
            assert 0 < length <= 0x20000
            result = self.alloc_cursor
            self.alloc_cursor += (length + 15) & ~15
            assert self.alloc_cursor < 0x4200000
            self.allocations.append(dict(address=result, length=length, api=name))
        elif name in ['_printk', '_dev_err', '_dev_info', '_dev_warn', '_dev_printk']:
            result = 0
        if result is None:
            raise AssertionError(('unhandled legacy probe boundary', name, [hex(x) for x in args]))
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def run_sample(sample):
    path = ROOT / 'firmware/samples' / sample / 'analysis/vendor_dlkm/lib/modules/xring_smartpa.ko'
    dt = json.loads((ROOT / 'logs/haptics-devicetree-audit.json').read_text())
    case = next(c for c in dt['cases'] if c['sample'] == sample and c['case'] == 'overlay-5')
    props = case['haptics']['/soc/i2c@EC100000/cs40l26@43']['properties']
    results = []
    scenarios = [
        ('pinctrl-select-error', dict(pinctrl_select_state=-5, cs40l26_set_pll_loop=0)),
        ('pll-error-after-init', dict(cs40l26_set_pll_loop=-5)),
        ('id-read-error-after-pll', dict(cs40l26_set_pll_loop=0)),
    ]
    for failure, overrides in scenarios:
        m = Prefix(path, props)
        m.service_results.update(overrides)
        result = m.run_probe()
        expected = -5
        assert result == expected, (sample, failure, result, m.calls)
        assert m.remove_entries == 1
        assert m.symbols['cs40l26_remove'] not in m.hooks
        assert 'cs40l26_input_init' not in m.calls and 'cs40l26_fw_upload' not in m.calls
        if failure == 'pinctrl-select-error':
            assert 'pinctrl_select_state' in m.calls
            assert 'cs40l26_set_pll_loop' not in m.calls
            assert not m.regmap_reads
            assert m.calls[-1] == 'debugfs_remove'
        elif failure == 'pll-error-after-init':
            assert 'cs40l26_set_pll_loop' in m.calls
            assert m.calls.index('cs40l26_set_pll_loop') < m.calls.index('disable_irq')
            assert m.calls[-1] == 'debugfs_remove'
            assert not m.regmap_reads
        else:
            assert 'regmap_read' in m.calls
            assert m.calls.index('regmap_read') < m.calls.index('disable_irq')
            assert m.calls[-1] == 'debugfs_remove'
            assert m.regmap_reads == [dict(address=0, result=-5)]
        assert any(x['name'] == 'device_property_read_u32_array' and
                   x.get('property') == 'cirrus,f0-default' and x['result'] == 0 for x in m.boundaries)
        if failure != 'pinctrl-select-error':
            assert 'regulator_bulk_enable' in m.calls and 'devm_gpiod_get_optional' in m.calls
            assert 'pinctrl_select_state' in m.calls
        results.append(dict(case=failure, result=result, calls=m.calls, boundaries=m.boundaries,
                            allocations=m.allocations, no_dsp_upload=True, no_input_registration=True,
                            pll_or_pinctrl_failure_fixture=True,
                            remove_body='original instructions; kernel teardown services are fixtures'))

    m = LegacyRunthrough(path, props)
    result = m.run_probe()
    assert result == -2, (sample, 'firmware-request-missing', result, m.calls)
    assert m.remove_entries == 1
    assert m.symbols['cs40l26_remove'] not in m.hooks
    assert m.firmware_requests == ['cs40l26.wmfw']
    assert m.regmap_reads == [dict(address=0, value=0x40a270),
                              dict(address=4, value=0xb2)]
    assert m.regmap_writes == [dict(address=0x2806fb0, mask=0x1ff, value=0x40a270),
                               dict(address=0x2806fb4, mask=0x1ff, value=0x40a270)]
    assert m.regmap_updates == [dict(address=0x2c04, mask=0x800, value=0x800),
                                dict(address=0x7404, mask=0x10000000, value=0x10000000)]
    assert m.calls.count('__init_swait_queue_head') == 6
    assert 'cdev_tevent_alloc' in m.calls and 'cs40l26_input_init' not in m.calls
    assert m.calls[-1] == 'debugfs_remove'
    results.append(dict(case='firmware-request-missing-after-stock-PLL-and-ID', result=result,
                        calls=m.calls, firmware_requests=m.firmware_requests,
                        regmap_reads=m.regmap_reads, regmap_writes=m.regmap_writes,
                        regmap_updates=m.regmap_updates,
                        synthetic_chip_identity=dict(device=0x40a270, revision=0xb2),
                        missing_firmware_fixture='cs40l26.wmfw', no_input_registration=True,
                        no_dsp_execution=True,
                        remove_body='original instructions; kernel teardown services are fixtures'))
    return dict(sample=sample, module=str(path.relative_to(ROOT)), module_sha256=sha(path), cases=results)


class LegacyRunthrough(Prefix):
    """Run original PLL and probe code to its first stock firmware request."""
    def __init__(self, path, properties):
        super().__init__(path, properties)
        del self.hooks[self.symbols['cs40l26_set_pll_loop']]
        self.service_results.pop('cs40l26_set_pll_loop')
        self.firmware_requests = []
        self.regmap_reads = []
        self.regmap_writes = []
        self.regmap_updates = []

    def on_code(self, uc, address, size, data):
        name = self.hooks.get(address)
        args = [self.arg(i) for i in range(7)]
        result = None
        if name == 'regmap_read':
            value = {0: 0x40a270, 4: 0xb2}.get(args[1])
            assert value is not None, ('unknown legacy ID register', args)
            self.put32(args[2], value)
            self.regmap_reads.append(dict(address=args[1], value=value))
            result = 0
        elif name == 'regmap_write':
            self.regmap_writes.append(dict(address=args[1], mask=args[2], value=args[3]))
            result = 0
        elif name == 'regmap_update_bits_base':
            self.regmap_updates.append(dict(address=args[1], mask=args[2], value=args[3]))
            result = 0
        elif name == '__init_swait_queue_head':
            result = 0
        elif name in ('strlen', 'strnlen'):
            limit = 128 if name == 'strlen' else min(args[1], 128)
            result = len(bytes(uc.mem_read(args[0], limit)).split(b'\0')[0])
        elif name in ('strscpy', 'strlcpy'):
            limit = min(args[2], 128)
            raw = bytes(uc.mem_read(args[1], limit)).split(b'\0')[0]
            assert len(raw) < limit
            uc.mem_write(args[0], raw + b'\0')
            result = len(raw)
        elif name == 'request_firmware':
            filename = self.string(args[1])
            self.firmware_requests.append(filename)
            assert filename == 'cs40l26.wmfw'
            result = -2
        elif name == 'release_firmware':
            result = 0
        elif name in ('cdev_tevent_alloc', 'cdev_tevent_add_str',
                      'cdev_tevent_write', 'cdev_tevent_destroy'):
            result = -12 if name == 'cdev_tevent_alloc' else 0
        else:
            return super().on_code(uc, address, size, data)
        self.calls.append(name)
        uc.reg_write(UC_ARM64_REG_X0, result & MASK)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))


def main():
    samples = ['os2-initial', 'os2-final', 'os3-initial', 'os3-final']
    profiles = [run_sample(sample) for sample in samples]
    assert len(profiles) == 4
    sources = {p['module']: p['module_sha256'] for p in profiles}
    sources['logs/haptics-devicetree-audit.json'] = sha(ROOT / 'logs/haptics-devicetree-audit.json')
    script = Path(__file__)
    auditor = ROOT / 'scripts/audit_haptics_legacy_probe_prefix.py'
    report = dict(status='PASS', scope=__doc__.strip(), profiles=profiles, sources=sources,
                  tests={str(script.relative_to(ROOT)): sha(script),
                         str(auditor.relative_to(ROOT)): sha(auditor)}, runtime_services='fixtures',
                  execution_boundary='original legacy PLL and probe through the first firmware request; additional original failure paths',
                  hardware_result='unverified')
    out = ROOT / 'logs/haptics-legacy-probe-prefix.json'
    out.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: four legacy probe ELFs x four cases; original PLL/ID reaches missing stock firmware; no DSP/input/motor')


if __name__ == '__main__':
    main()
