#!/usr/bin/env python3
"""Record user-supplied raw-off intervention and subsequent real input events.

This is transcript evidence, not an agent-run device test or new-image test.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    transcript = ROOT/'logs/touch-raw-off-user-transcript.txt'
    dmesg = ROOT/'imgs/built/1/touch-after-raw-off.txt'
    text = transcript.read_text()
    assert 'echo 0 > /sys/class/touch/touch_dev/enable_touch_raw' in text
    assert re.search(r'enable_touch_raw\s*\n0\s*\n', text)
    events = re.findall(r'\[\s*([\d.]+)\]\s+(EV_\w+)\s+(\w+)\s+(\S+)', text)
    assert len(events) == 215
    assert all(float(a[0]) <= float(b[0]) for a,b in zip(events, events[1:]))
    down = sum(e[2:] == ('BTN_TOUCH', 'DOWN') for e in events)
    up = sum(e[2:] == ('BTN_TOUCH', 'UP') for e in events)
    tracking = [e[3] for e in events if e[2] == 'ABS_MT_TRACKING_ID']
    assert down == up == 7
    assert tracking == [v for i in range(7) for v in (f'{i:08x}', 'ffffffff')]
    axes = {axis:[int(e[3],16) for e in events if e[2] == axis]
            for axis in ['ABS_MT_POSITION_X','ABS_MT_POSITION_Y']}
    assert all(len(set(v)) > 1 for v in axes.values())
    assert all(0 <= x <= 143999 for x in axes['ABS_MT_POSITION_X'])
    assert all(0 <= y <= 319999 for y in axes['ABS_MT_POSITION_Y'])
    raw = dmesg.read_bytes()
    kernel = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    touch_lines = [line for line in kernel.splitlines() if re.search(r'syna|tcm|\btouch\b',line,re.I)]
    files = [transcript,dmesg,Path(__file__).resolve()]
    report = dict(status='OBSERVED', scope=__doc__, saved_input_events=len(events),
                  presses=down, releases=up, time_range=[float(events[0][0]),float(events[-1][0])],
                  axes={k:dict(count=len(v),min=min(v),max=max(v)) for k,v in axes.items()},
                  dmesg_touch_lines=len(touch_lines),
                  conclusion='User raw=0 intervention was followed by real event3 coordinate, press and release events. With preceding c0/no-events capture, this supports ordinary-report mode as an effective recovery action for this boot.',
                  remaining='GUI response, cold startup policy, resume persistence, and who enabled c0 remain unproven. Post-intervention dmesg contains no touch protocol lines and cannot establish report IDs or command acknowledgements.',
                  files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (ROOT/'logs/touch-raw-off-observation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('OBSERVED: raw=0 followed by 215 event3 events, 7 presses/releases and changing X/Y')


if __name__ == '__main__':
    main()
