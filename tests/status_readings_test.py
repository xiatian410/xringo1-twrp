#!/usr/bin/env python3
"""Execute production battery, temperature, clock policy and status parsing.

Sysfs is redirected to disposable files. Wall/monotonic clocks and DataManager
are substitutes. No real clock is readjusted, no Health HAL or hardware is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('/root/AAA/twrp/bootable/recovery')


def method(text, signature):
    start = text.index(signature)
    pos = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    return text[start:pos]


parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, default=SRC)
parser.add_argument('--data-source', type=Path)
parser.add_argument('--report', type=Path, default=ROOT / 'logs/status-readings.json')
args = parser.parse_args()
cases = ['battery-valid', 'battery-missing', 'battery-malformed', 'battery-overflow',
         'battery-range', 'battery-zero', 'battery-status', 'battery-hotplug',
         'UI-valid', 'UI-zero', 'UI-malformed', 'UI-hidden',
         'temperature-positive', 'temperature-negative', 'temperature-small',
         'temperature-malformed', 'temperature-overflow', 'temperature-cache',
         'temperature-unavailable', 'temperature-disabled', 'clock-format',
         'clock-jump', 'rtc-policy', 'temperature-concurrent', 'clock-read-error',
         'clock-conversion-error', 'clock-error-recovery', 'clock-forward-backward']
source_names = ['twrp.cpp', 'data.cpp', 'twrp_functions.cpp', 'gui2/backend/status_backend.cpp']
contents = {n:(args.source/n).read_text() for n in source_names}
if args.data_source:
    contents['data.cpp'] = args.data_source.read_text()
functions = method(contents['twrp.cpp'], 'static BatteryInfo ReadLegacyBattery()')
functions += '\n' + method(contents['data.cpp'], 'int DataManager::GetMagicValue(')
# Only the system-call/clock boundaries are redirected, not parser logic.
functions = functions.replace('std::chrono::steady_clock', 'FixtureClock')
functions = functions.replace('time(nullptr)', 'fixture_time(nullptr)')
functions = functions.replace('localtime_r(&now, &local)', 'fixture_localtime_r(&now, &local)')
functions += '\n' + method(contents['twrp_functions.cpp'], 'void TWFunc::FixupTimeOnBoot(')
with tempfile.TemporaryDirectory(prefix='dijun-status-') as temp:
    temp = Path(temp)
    (temp/'fixture').mkdir()
    harness = (ROOT/'tests/status_readings_test.cpp').read_text().replace('// PRODUCTION_METHODS', functions)
    (temp/'test.cpp').write_text(harness)
    (temp/'status_backend.cpp').write_text(contents['gui2/backend/status_backend.cpp'])
    subprocess.run(['g++','-std=c++23','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                    '-fsanitize=undefined','-fno-sanitize-recover=all','-g','-pthread',
                    '-I'+str(SRC/'gui2/backend'),
                    '-DTW_CUSTOM_BATTERY_PATH="'+str(temp/'fixture')+'"',
                    str(temp/'test.cpp'), str(temp/'status_backend.cpp'), '-o',str(temp/'test')],check=True)
    results=[]
    for case in cases:
        run=subprocess.run([str(temp/'test'),case],capture_output=True,text=True,timeout=5)
        results.append(dict(case=case,returncode=run.returncode,status='PASS' if run.returncode==0 else 'FAIL',
                            output=(run.stdout+run.stderr).strip()))
        print(results[-1]['status'],case,results[-1]['output'],flush=True)
    report=dict(status='PASS' if all(r['returncode']==0 for r in results) else 'FAIL',
                scope=__doc__.strip(),cases=results,
                sources={str(args.data_source if n=='data.cpp' and args.data_source else args.source/n):hashlib.sha256(contents[n].encode()).hexdigest() for n in source_names},
                test_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'tests/status_readings_test.cpp']})
    args.report.write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
