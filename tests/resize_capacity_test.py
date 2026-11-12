#!/usr/bin/env python3
"""Original ext Resize command bounds; repair/device/command/size are explicit doubles.

No tool or block device is accessed. Rejects signed-minimum negation, negative
reservation underflow, sub-KiB results and positive sizes beyond the device.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
from nested_partition_path_test import ROOT,SRC,method
from haptics_ui_test import sha

HARNESS=r'''
#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <string>
#define LOGINFO(...) ((void)0)
namespace gui2_console {template<class... A>void info(A...){} template<class... A>void log_error(A...){}}
static unsigned execs=0;static std::string command;static bool available=true;static int result=0;
namespace TWFunc {bool IsPathExists(const std::string&){return available;}int ExecCmd(const std::string&s){++execs;command=s;return result;}}
struct TWPartition {
 std::string current_file_system_="ext4",display_name_="fixture",actual_block_device_="/fixture/never-open";
 int length_=0;uint64_t capacity=10485760;bool repair=true;unsigned repairs=0,updates=0;
 bool CanRepair(){return repair;}bool Repair(){++repairs;return repair;}void FindActualBlockDevice(){}
 uint64_t IoctlGetBlockSize(){return capacity;}void UpdateSize(bool){++updates;}bool Resize();
};
// METHOD
int main(int argc,char**argv){
 assert(argc==2);std::string label=argv[1];TWPartition p;bool expected=true;std::string suffix;
 if(label=="whole-device"){}
 else if(label=="positive"){p.length_=2097152;suffix=" 2048K";}
 else if(label=="reserved"){p.length_=-16384;suffix=" 10224K";}
 else if(label=="unaligned-reserved"){p.length_=-1025;suffix=" 10238K";}
 else if(label=="minimum"){p.length_=1024;suffix=" 1K";}
 else if(label=="equal-device"){p.length_=p.capacity;suffix=" 10240K";}
 else if(label=="reserved-equal"){p.length_=-static_cast<int64_t>(p.capacity);expected=false;}
 else if(label=="reserved-larger"){p.length_=-static_cast<int64_t>(p.capacity)-1024;expected=false;}
 else if(label=="signed-min"){p.length_=INT_MIN;expected=false;}
 else if(label=="sub-KiB"){p.length_=1023;expected=false;}
 else if(label=="positive-larger"){p.length_=p.capacity+1024;expected=false;}
 else if(label=="reserved-sub-KiB"){p.length_=-static_cast<int64_t>(p.capacity)+1023;expected=false;}
 else if(label=="capacity-missing"){p.length_=-16384;p.capacity=0;expected=false;}
 else if(label=="repair-failed"){p.repair=false;expected=false;}
 else if(label=="tool-missing"){available=false;expected=false;}
 else if(label=="tool-failed"){result=-1;expected=false;}
 else assert(false);
 assert(p.Resize()==expected);
 bool runs=expected||label=="tool-failed";assert(execs==(runs?1u:0u));assert(p.updates==(runs?1u:0u));
 if(runs)assert(command=="/system/bin/resize2fs /fixture/never-open"+suffix);
 printf("PASS %s execs=%u command=%s\n",argv[1],execs,command.c_str());
}
'''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=SRC/'partition.cpp');ap.add_argument('--report',type=Path,default=ROOT/'logs/resize-capacity.json');args=ap.parse_args()
 labels=['whole-device','positive','reserved','unaligned-reserved','minimum','equal-device','reserved-equal','reserved-larger','signed-min','sub-KiB','positive-larger','reserved-sub-KiB','capacity-missing','repair-failed','tool-missing','tool-failed']
 with tempfile.TemporaryDirectory(prefix='resize-bounds-') as tmp:
  p=Path(tmp);(p/'test.cpp').write_text(HARNESS.replace('// METHOD',method(args.source.read_text(),'bool TWPartition::Resize()')))
  subprocess.run(['g++','-std=c++23','-fsanitize=undefined','-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True);cases=[]
  for label in labels:
   r=subprocess.run([str(p/'test'),label],capture_output=True,text=True,timeout=5);cases.append(dict(case=label,status='PASS' if r.returncode==0 else 'FAIL',output=r.stdout+r.stderr));print(cases[-1],flush=True)
 assert 'int length_;' in (SRC/'partitions.hpp').read_text()
 paths=[args.source,SRC/'partitions.hpp',Path(__file__),ROOT/'tests/nested_partition_path_test.py',ROOT/'tests/haptics_ui_test.py'];report=dict(status='PASS' if all(c['status']=='PASS' for c in cases) else 'FAIL',scope=__doc__,cases=cases,sources={str(p):sha(p) for p in paths});args.report.write_text(json.dumps(report,indent=2)+'\n');return report['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
