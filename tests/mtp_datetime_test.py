#!/usr/bin/env python3
"""Compile actual MTP utils and compare dates with independent Python datetime.

Real host libc/filesystem utility implementation; no transport, device RTC,
Android libc, phone or GUI. Invalid input must retain the caller's output.
"""
import argparse,ctypes,datetime as dt,hashlib,json,os,subprocess,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REC=Path('/root/AAA/twrp/bootable/recovery')
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source',type=Path,default=REC/'mtp/MtpUtils.cpp')
ap.add_argument('--report',type=Path,required=True)
ap.add_argument('--skip-null',action='store_true',help='Old sscanf implementation dereferences null; omit only for baseline comparison')
args=ap.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
valid=[('20261111T020953+0800','2026-11-10T18:09:53+00:00'),
 ('20260101T003000+0130','2025-12-31T23:00:00+00:00'),
 ('20261231T233000-0230','2027-01-01T02:00:00+00:00'),
 ('20240229T120000Z','2024-02-29T12:00:00+00:00'),
 ('20000229T000000Z','2000-02-29T00:00:00+00:00'),
 ('19691231T235959Z','1969-12-31T23:59:59+00:00'),
 ('19700101T000000Z','1970-01-01T00:00:00+00:00'),
 ('20261111T020953.7+0800','2026-11-10T18:09:53+00:00'),
 ('20261110T180953.0Z','2026-11-10T18:09:53+00:00'),
 ('20261110T180953+0000','2026-11-10T18:09:53+00:00'),
 ('20261110T180953-0000','2026-11-10T18:09:53+00:00'),
 ('20260101T235959+2359','2026-01-01T00:00:59+00:00'),
 ('20260101T000000-2359','2026-01-01T23:59:00+00:00')]
bad=['','2026','20261111T02095','202611110020953Z','2026a111T020953Z',
 '20261111t020953Z','20261111T020953z','20261111T020953Zjunk',
 '20261111T020953junk','20261111T020953+08','20261111T020953+08000',
 '20261111T020953+08:00','20261111T020953+2400','20261111T020953-0060',
 '20261111T020953+0x00','20261111T020953.','20261111T020953.xZ',
 '20261111T020953.12Z','20261111T020953.Z','20261111T020953 Z',
 '20261301T000000Z','20260001T000000Z','20261100T000000Z',
 '20261131T000000Z','20260229T000000Z','19000229T000000Z',
 '20260101T240000Z','20260101T006000Z','20260101T000060Z',
 '00000101T000000Z',' 0260101T000000Z','20260101T-10000Z']
cases=[]
with tempfile.TemporaryDirectory(prefix='mtp-date-') as temp:
 temp=Path(temp);(temp/'log').mkdir();(temp/'android-base').mkdir()
 (temp/'android-base/logging.h').write_text('#pragma once\n#include <iostream>\n#define PLOG(x) std::cerr\n#define LOG(x) std::cerr\n')
 (temp/'shim.cpp').write_text('''#include <cstdint>
#include <ctime>
#include "MtpUtils.h"
extern "C" bool parse(const char* text,int64_t* value) {
 time_t result=*value;bool ok=android::parseDateTime(text,result);*value=result;return ok;
}
''')
 command=['g++','-std=c++23','-O1','-g','-shared','-fPIC','-fsanitize=undefined',
  '-fno-sanitize-recover=all','-I'+str(temp),'-I'+str(REC/'mtp'),
  '-I/root/AAA/twrp/system/libbase/include','-I/root/AAA/twrp/system/core/libcutils/include',
  str(args.source),str(temp/'shim.cpp'),'-o',str(temp/'libdate.so')]
 subprocess.run(command,check=True)
 lib=ctypes.CDLL(str(temp/'libdate.so'));lib.parse.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.c_int64)];lib.parse.restype=ctypes.c_bool
 saved=os.environ.get('TZ')
 def check(text,zone,expected,label):
  os.environ['TZ']=zone;time.tzset();out=ctypes.c_int64(123456789)
  ok=lib.parse(text.encode() if text is not None else None,ctypes.byref(out))
  passed=(ok and out.value==expected) if expected is not None else (not ok and out.value==123456789)
  cases.append(dict(case=label,input=text,timezone=zone,expected=expected,accepted=ok,value=out.value,status='PASS' if passed else 'FAIL'))
 try:
  for text,iso in valid:
   expected=int(dt.datetime.fromisoformat(iso).timestamp())
   for zone in ['UTC0','CST-8','EST5EDT,M3.2.0,M11.1.0']:check(text,zone,expected,'explicit-zone')
  for text in bad:check(text,'UTC0',None,'invalid')
  if not args.skip_null:check(None,'UTC0',None,'null')
  for zone,offset in [('UTC0',0),('CST-8',8),('EST5EDT,M3.2.0,M11.1.0',-5)]:
   expected=int(dt.datetime(2026,11,11,2,9,53,tzinfo=dt.timezone(dt.timedelta(hours=offset))).timestamp())
   for text in ['20261111T020953','20261111T020953.5']:check(text,zone,expected,'local-zone')
  check('20260701T120000','EST5EDT,M3.2.0,M11.1.0',int(dt.datetime(2026,7,1,16,tzinfo=dt.timezone.utc).timestamp()),'local-DST')
  check('20260308T023000','EST5EDT,M3.2.0,M11.1.0',None,'nonexistent-local-time')
 finally:
  if saved is None:os.environ.pop('TZ',None)
  else:os.environ['TZ']=saved
  time.tzset()
 report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,count=len(cases),cases=cases,sources={str(args.source):sha(args.source),str(REC/'mtp/MtpUtils.h'):sha(REC/'mtp/MtpUtils.h')},tests={str(Path(__file__).resolve()):sha(Path(__file__))},compile_command=command)
 args.report.write_text(json.dumps(report,indent=2)+'\n')
 for c in cases:
  if c['status']=='FAIL':print('FAIL',c)
 print(report['status'],len(cases),'date checks')
raise SystemExit(report['status']!='PASS')
