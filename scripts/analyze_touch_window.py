#!/usr/bin/env python3
"""Compare action-window logs without treating cumulative IRQs as touch proof.

Accept the device-side collector directory, or a parent containing it. Does
not run adb, touch input devices, or infer a hardware root cause.
"""
import argparse
import json
import re
from pathlib import Path


def text(path):
    data = path.read_bytes()
    return data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff'))
                       else 'utf-8-sig')


def irqs(value):
    lines = value.splitlines()
    header = next((line.split() for line in lines if re.fullmatch(
        r'\s*CPU\d+(?:\s+CPU\d+)*\s*', line)), None)
    if not header:
        raise ValueError('missing CPU header in interrupts')
    result = {}
    for name in ('xiaomi_tpsynaptics_tcm', 'spi_dma_irq'):
        rows = [line for line in lines if line.split() and line.split()[-1] == name]
        if len(rows) != 1:
            raise ValueError(f'expected one IRQ row for {name}, found {len(rows)}')
        fields = rows[0].split()
        counts = fields[1:1 + len(header)]
        if len(counts) != len(header) or not all(c.isdecimal() for c in counts):
            raise ValueError(f'invalid CPU counters for {name}')
        result[name] = {'irq': fields[0].rstrip(':'),
                        'counts': [int(c) for c in counts]}
    return result


def window(root, phase):
    start = float(text(root / f'{phase}-start-uptime.txt').split()[0])
    end = float(text(root / f'{phase}-end-uptime.txt').split()[0])
    if not 0 < end - start <= 120:
        raise ValueError(f'{phase}: invalid duration or reboot')
    before = irqs(text(root / f'{phase}-start-interrupts.txt'))
    after = irqs(text(root / f'{phase}-end-interrupts.txt'))
    deltas = {}
    for name, row in before.items():
        other = after[name]
        if row['irq'] != other['irq'] or len(row['counts']) != len(other['counts']):
            raise ValueError(f'{phase}: IRQ identity/CPU layout changed for {name}')
        changes = [b - a for a, b in zip(row['counts'], other['counts'])]
        if any(change < 0 for change in changes):
            raise ValueError(f'{phase}: counters decreased for {name}')
        deltas[name] = {'delta': sum(changes), 'per_second': sum(changes) / (end - start)}
    events = text(root / f'{phase}-events.txt')
    # Require a timed getevent line with a device and actual coordinate type,
    # rather than capability listings or an unrelated input device's ABS axes.
    coords = []
    for line in events.splitlines():
        match = re.match(r'^\[\s*[0-9.]+\]\s+(/dev/input/event\d+):\s+'
                         r'EV_ABS\s+(ABS_MT_POSITION_[XY])\s+([0-9a-fA-F]+)\s*$', line)
        if match:
            coords.append({'device': match[1], 'axis': match[2], 'value_hex': match[3]})
    code = text(root / f'{phase}-getevent-exit.txt').strip()
    # timeout -s KILL can report 124 or 137 depending on the installed utility.
    # Other exits may indicate getevent failed before observing the window.
    if code not in ('124', '137'):
        raise ValueError(f'{phase}: unexpected getevent exit {code!r}')
    return {'start_uptime': start, 'end_uptime': end, 'seconds': end - start,
            'irqs': deltas, 'coordinate_event_count': len(coords),
            'coordinate_devices': sorted({c['device'] for c in coords}),
            'getevent_exit': int(code)}


def analyze(root):
    if (root / 'dijun-touch-no-events').is_dir():
        root = root / 'dijun-touch-no-events'
    report = {'status': 'insufficient', 'scope': 'Action-window observations only; '
              'requires the instructed idle/swipe actions. No hardware root cause inferred.',
              'directory': str(root)}
    try:
        idle, touch = window(root, 'idle'), window(root, 'touch')
        if touch['start_uptime'] < idle['end_uptime']:
            raise ValueError('overlapping windows or uptime reset between windows')
        if touch['end_uptime'] - idle['start_uptime'] > 180:
            raise ValueError('windows too far apart to compare')
        report.update(status='observed', idle=idle, touch=touch)
        if touch['coordinate_event_count']:
            report['next_focus'] = 'Identify coordinate devices, then inspect Recovery consumption if they belong to the touchscreen.'
        elif touch['irqs']['xiaomi_tpsynaptics_tcm']['delta'] == 0:
            report['next_focus'] = 'No touch IRQ increment in this window; inspect controller, IRQ enable and power/pin state.'
        else:
            report['next_focus'] = 'IRQ increased without coordinates; inspect ISR gates, SPI responses, report mode/configuration and parser. IRQ increments alone do not prove valid touch packets.'
    except (OSError, UnicodeError, ValueError, IndexError) as error:
        report['reason'] = str(error)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    rendered = json.dumps(analyze(args.directory), ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end='')
