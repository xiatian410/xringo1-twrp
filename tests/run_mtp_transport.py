#!/usr/bin/env python3
"""Compile the actual MTP sources with property/logging substitutes, no USB."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
AOSP = Path('/root/AAA/twrp')
RECOVERY = AOSP / 'bootable/recovery'

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--report', type=Path, default=ROOT/'logs/mtp-transport-regression.json')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='dijun-mtp-') as directory:
    temp = Path(directory)
    shim = temp / 'include'
    (shim / 'android-base').mkdir(parents=True)
    (shim / 'sys').mkdir()
    (shim / 'sys/endian.h').write_text('#include <endian.h>\n')
    (shim / 'android-base/properties.h').write_text('''#pragma once
#include <map>
#include <string>
namespace android::base {
inline std::map<std::string, std::string> test_properties;
inline bool GetBoolProperty(const std::string&, bool value) { return value; }
template<class T> T GetIntProperty(const std::string&, T value) { return value; }
inline bool SetProperty(const std::string& key, const std::string& value) {
    test_properties[key] = value; return true;
}
}
''')
    (shim / 'android-base/logging.h').write_text('''#pragma once
#include <cassert>
#include <iostream>
#define LOG(x) std::cerr
#define PLOG(x) std::cerr
#define CHECK(x) assert(x)
''')
    source = RECOVERY / 'mtp'
    if args.baseline:
        source = temp / 'baseline'
        source.mkdir()
        for p in (RECOVERY / 'mtp').iterdir():
            if p.is_file() and p.suffix in ['.cpp', '.h']:
                data = subprocess.check_output(['git', '-C', str(RECOVERY), 'show', 'HEAD:mtp/' + p.name])
                (source / p.name).write_bytes(data)
    files = [source / n for n in ['MtpFfsHandle.cpp', 'MtpFfsCompatHandle.cpp', 'MtpDescriptors.cpp', 'PosixAsyncIO.cpp']]
    files += [AOSP / 'system/core/libasyncio/AsyncIO.cpp', ROOT / 'tests/mtp_transport_test.cpp']
    includes = [shim, source, AOSP / 'system/libbase/include', AOSP / 'system/core/libasyncio/include']
    cmd = ['g++', '-std=gnu++17', '-O1', '-g', '-pthread', '-Wall', '-Wextra',
           '-Wno-sign-compare', '-Wno-unused-parameter', '-Wno-attributes',
           '-include', 'unistd.h', '-Wl,--wrap=write', '-Wl,--wrap=pwrite64']
    cmd += ['-I' + str(p) for p in includes]
    binary = temp / 'mtp-test'
    subprocess.run(cmd + [str(p) for p in files] + ['-o', str(binary)], check=True)
    result = subprocess.run([str(binary), str(temp)], capture_output=True, text=True, timeout=30)
    print(result.stdout + result.stderr)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = dict(status='PASS' if result.returncode == 0 else 'FAIL', scope=__doc__,
                  returncode=result.returncode, output=result.stdout+result.stderr,
                  sources={str(p):sha(p) for p in source.glob('*') if p.suffix in ['.cpp','.h']},
                  shared_sources={str(p):sha(p) for base in [AOSP/'system/libbase/include',AOSP/'system/core/libasyncio'] for p in base.rglob('*') if p.suffix in ['.cpp','.h']},
                  test_sources={str(p):sha(p) for p in [Path(__file__).resolve(),ROOT/'tests/mtp_transport_test.cpp']},
                  compile_command=cmd+[str(p) for p in files],
                  boundaries=['Real host Linux AIO/pipes/files, substituted Android properties/logging.',
                              'No physical FunctionFS/UDC or Windows enumeration.'])
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(result.returncode)
