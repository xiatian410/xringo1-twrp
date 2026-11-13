// Private chroot: original repair routing and process capture, real delivered checker.
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <memory>
#include <mutex>
#include <string>
#include <vector>
#include <sys/wait.h>
#include <unistd.h>
#include "mount_backend.h"
using gui2_backend::is_restricted_mount_path;
namespace fs = std::filesystem;
#define LOGINFO(...) std::printf(__VA_ARGS__)
#define LOGERR(...) std::fprintf(stderr,__VA_ARGS__)
static unsigned done=0,errors=0,unmounts=0,starts=0,ends=0;
static int ended=-1;
namespace gui2_console {
template<class... A> void info(const char* key,A...) { if(std::string(key)=="done") ++done; }
template<class... A> void log_error(const char* key,A...) { ++errors; std::printf("ERROR %s\n",key); }
}
namespace TWFunc {
bool IsPathExists(const std::string&);
std::string GetRootPath(const std::string&);
int ExecCmd(const std::string&,std::string&,bool);
int ExecCmd(const std::string&,bool=true) { assert(false && "non-ext checker is outside this fixture"); return -1; }
}
namespace twrp_operation_executor {
struct executor { std::recursive_mutex lock; std::recursive_mutex& mutex(){ return lock; } };
executor& instance(){ static executor e; return e; }
struct guard { std::lock_guard<std::recursive_mutex> lock; guard(std::recursive_mutex& m):lock(m){} };
}
struct TWPartition {
  std::string GetMountPoint(){return mount_point_;}
  std::string mount_point_,symlink_mount_point_,sub_partition_of_;
  bool is_sub_partition_=false,unmount_ok=true;
  std::string current_file_system_="ext4",display_name_="private image",actual_block_device_;
  bool Unmount(bool) { ++unmounts; return unmount_ok; }
  bool IsMounted() const { return false; } // Explicit unmounted fixture after successful Unmount.
  void FindActualBlockDevice() {} // Explicit device-resolution boundary: only a private regular file.
  bool Repair();
};
struct TWPartitionManager {
  std::vector<TWPartition*> partitions_;
  static bool MatchesPath(const TWPartition*,const std::string&);
  TWPartition* FindPartitionByPath(const std::string&)const;
  int RepairByPath(const std::string&,bool)const;
  std::string GetAndroidRootPath()const { return "/system_root"; }
} PartitionManager;
static void operation_start(const char* name) { assert(std::string(name)=="Repair Partition"); ++starts; }
static void operation_end(int status) { ended=status; ++ends; }
#include "methods.inc"
int main(int argc,char**argv) {
  assert(argc==3); const std::string scenario=argv[1]; const bool success=std::stoi(argv[2])!=0;
  TWPartition owner; owner.mount_point_="/mnt/vendor/persist";
  owner.actual_block_device_="/fixtures/target.img";
  TWPartition other; other.mount_point_="/mnt/vendor/persist-other";
  other.actual_block_device_="/fixtures/never-open.img";
  PartitionManager.partitions_={&other,&owner};
  std::string target="/mnt/vendor/persist/TWRP";
  if(scenario=="unmount-denied") owner.unmount_ok=false;
  if(scenario=="unknown-target") target="/mnt/vendor/unknown";
  TWPartition child;
  if(scenario=="child-invalid") {
    child.mount_point_="/mnt/vendor/persist/child"; child.is_sub_partition_=true;
    child.sub_partition_of_=owner.mount_point_; child.actual_block_device_="/fixtures/invalid.img";
    PartitionManager.partitions_.push_back(&child);
  }
  const int status=repair(target);
  assert(status==(success?0:1)); assert(ended==status && starts==1 && ends==1);
  if(scenario=="clean" || scenario=="corrected") { assert(done==1 && errors==0 && unmounts==1); }
  if(scenario=="invalid") { assert(done==0 && errors==1 && unmounts==1); }
  if(scenario=="missing-checker" || scenario=="unknown-target") { assert(done==0 && errors==1 && unmounts==0); }
  if(scenario=="unmount-denied") { assert(done==0 && unmounts==1); }
  if(scenario=="child-invalid") { assert(done==1 && errors==1 && unmounts==2); }
  std::printf("RESULT scenario=%s status=%d done=%u errors=%u unmounts=%u\n",scenario.c_str(),status,done,errors,unmounts);
}
