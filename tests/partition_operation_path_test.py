#!/usr/bin/env python3
"""Exercise real wipe/format/repair/resize routing with private partition doubles.

Only target selection and call order execute. No mount, wipe, filesystem tool,
device or block I/O executes. The doubles record targets and propagate errors.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from nested_partition_path_test import HARNESS, SRC, ROOT, method


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SRC/'partitionmanager.cpp')
    ap.add_argument('--report', type=Path, default=ROOT/'logs/partition-operation-path.json')
    args = ap.parse_args()
    harness = HARNESS[:HARNESS.index('int main(){')]
    harness = harness.replace('bool Unmount(bool,int)const', 'bool Unmount(bool,int=0)const')
    harness = harness.replace('bool Mount(bool)', '''
 std::string actual_block_device_,last_fs;
 mutable unsigned wipes=0,repairs=0,resizes=0,cache_wipes=0,secure_wipes=0;
 bool operation_result=true;
 void FindActualBlockDevice(){}
 bool Wipe(){++wipes;return operation_result;}
 bool Wipe(const std::string& fs){last_fs=fs;++wipes;return operation_result;}
 bool WipeAndSec(){++secure_wipes;return operation_result;}
 bool WipeDataCache(){++cache_wipes;return operation_result;}
 bool Repair(){++repairs;return operation_result;}
 bool Resize(){++resizes;return operation_result;}
 bool Mount(bool)''')
    harness = harness.replace('std::string GetAndroidRootPath()', '''
 int WipeByPath(const std::string&)const;
 int WipeByPath(const std::string&,const std::string&)const;
 int RepairByPath(const std::string&,bool)const;
 int ResizeByPath(const std::string&,bool)const;
 std::string GetAndroidRootPath()''')
    signatures = ['bool TWPartitionManager::MatchesPath(',
                  'TWPartition* TWPartitionManager::FindPartitionByPath(',
                  'int TWPartitionManager::MountByPath(',
                  'bool TWPartitionManager::UnmountByPath(',
                  'int TWPartitionManager::IsMountedByPath(',
                  'int TWPartitionManager::WipeByPath(const std::string& Path) const',
                  'int TWPartitionManager::WipeByPath(const std::string& Path,',
                  'int TWPartitionManager::RepairByPath(',
                  'int TWPartitionManager::ResizeByPath(']
    text = args.source.read_text()
    methods = [method(text, sig) for sig in signatures]
    methods += [method((SRC/'twrp_functions.cpp').read_text(), 'std::string TWFunc::GetRootPath('),
                method((SRC/'infomanager.cpp').read_text(), 'static bool twPersistMount(')]
    harness = harness.replace('// METHODS', '\n'.join(methods))
    harness += r'''
int main(){
 TWPartition protect{ "/mnt/vendor/protect_f" },persist{ "/mnt/vendor/persist" },
 data{ "/data", "/sdcard" },system{ "/system_root" },vendor{ "/vendor" },
 child{ "/vendor/child" },alias{ "/other-vendor" };
 child.is_sub_partition_=true;child.sub_partition_of_="/vendor";
 PartitionManager.partitions_={&protect,&persist,&data,&system,&vendor,&child,&alias};
 for(auto p:PartitionManager.partitions_) p->actual_block_device_="/fixture"+p->mount_point_;
 alias.actual_block_device_=vendor.actual_block_device_;
 CHECK(PartitionManager.WipeByPath("/mnt/vendor/protect_f"));
 CHECK(protect.wipes==1 && persist.wipes==0 && data.wipes==0);
 CHECK(PartitionManager.WipeByPath("/mnt/vendor/protect_f", "ext4"));
 CHECK(protect.wipes==2 && protect.last_fs=="ext4" && persist.last_fs.empty());
 CHECK(PartitionManager.RepairByPath("/mnt/vendor/protect_f",false));
 CHECK(protect.repairs==1 && persist.repairs==0);
 CHECK(PartitionManager.ResizeByPath("/mnt/vendor/protect_f",false));
 CHECK(protect.resizes==1 && persist.resizes==0);
 // Owner boundaries and ordinary paths still use the intended partition.
 CHECK(!PartitionManager.WipeByPath("/mnt/vendor/protect_f-other"));
 CHECK(!PartitionManager.WipeByPath("/mnt/vendor/protect_f-other","f2fs"));
 CHECK(!PartitionManager.RepairByPath("/mnt/vendor/protect_f-other",false));
 CHECK(!PartitionManager.ResizeByPath("/mnt/vendor/protect_f-other",false));
 CHECK(protect.wipes==2 && protect.repairs==1 && protect.resizes==1);
 protect.operation_result=false;
 CHECK(!PartitionManager.WipeByPath("/mnt/vendor/protect_f"));
 CHECK(!PartitionManager.WipeByPath("/mnt/vendor/protect_f","ext4"));
 CHECK(!PartitionManager.RepairByPath("/mnt/vendor/protect_f",false));
 CHECK(!PartitionManager.ResizeByPath("/mnt/vendor/protect_f",false));
 CHECK(PartitionManager.WipeByPath("/system/bin"));
 CHECK(PartitionManager.WipeByPath("/system", "ext4"));
 CHECK(system.wipes==2 && system.last_fs=="ext4");
 CHECK(PartitionManager.RepairByPath("/system",false));
 CHECK(PartitionManager.ResizeByPath("/system",false));
 CHECK(system.repairs==1 && system.resizes==1);
 CHECK(PartitionManager.WipeByPath("/sdcard/test"));
 CHECK(data.wipes==1);
 CHECK(PartitionManager.WipeByPath("/vendor"));
 CHECK(vendor.wipes==1 && child.wipes==1 && alias.unmounts==1);
 CHECK(PartitionManager.RepairByPath("/vendor",false));
 CHECK(PartitionManager.ResizeByPath("/vendor",false));
 CHECK(vendor.repairs==1 && child.repairs==1 && vendor.resizes==1 && child.resizes==1);
 child.operation_result=false;
 CHECK(!PartitionManager.WipeByPath("/vendor"));
 CHECK(!PartitionManager.WipeByPath("/vendor","ext4"));
 CHECK(!PartitionManager.RepairByPath("/vendor",false));
 CHECK(!PartitionManager.ResizeByPath("/vendor",false));
 CHECK(vendor.wipes==3 && child.wipes==3 && vendor.last_fs=="ext4" && child.last_fs=="ext4");
 CHECK(vendor.repairs==2 && child.repairs==2 && vendor.resizes==2 && child.resizes==2);
 CHECK(PartitionManager.WipeByPath("/cache"));
 CHECK(data.cache_wipes==1 && data.wipes==1);
 data.operation_result=false;
 CHECK(!PartitionManager.WipeByPath("/cache"));
 CHECK(data.cache_wipes==2 && data.wipes==1);
 TWPartition secure{ "/and-sec" };secure.actual_block_device_="/fixture-sec";
 PartitionManager.partitions_.push_back(&secure);
 CHECK(PartitionManager.WipeByPath("/and-sec"));
 CHECK(PartitionManager.WipeByPath("/and-sec","ext4"));
 CHECK(secure.secure_wipes==2 && secure.wipes==0);
 CHECK(PartitionManager.RepairByPath("/tmp/file",false));
 CHECK(PartitionManager.ResizeByPath("/tmp/file",false));
 CHECK(protect.wipes==4 && protect.repairs==2 && protect.resizes==2 && persist.wipes==0);
 std::printf("assertions=%u failures=%u\n",assertions,failures);
 return failures?1:0;
}
'''
    with tempfile.TemporaryDirectory(prefix='partition-operation-path-') as temp:
        p = Path(temp); (p/'test.cpp').write_text(harness)
        subprocess.run(['g++', '-std=c++23', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        str(p/'test.cpp'), '-o', str(p/'test')], check=True)
        result = subprocess.run([str(p/'test')], capture_output=True, text=True, timeout=10)
    paths = [args.source, SRC/'twrp_functions.cpp', SRC/'infomanager.cpp',
             Path(__file__).resolve(), ROOT/'tests/nested_partition_path_test.py']
    report = dict(status='PASS' if result.returncode==0 else 'FAIL', scope=__doc__,
                  returncode=result.returncode, output=result.stdout+result.stderr,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(report['output'], end='')
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
