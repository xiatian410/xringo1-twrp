// Real production FlashImage/IsSparseImage/FlashSparseImage and AOSP libsparse.
// Only this process's private target file is described as a block device.
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <android-base/unique_fd.h>
#include <android-base/scopeguard.h>
#include <sparse/sparse.h>
#include "sparse_format.h"

#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
namespace gui2_console {
template<class...T> void info(T&&...) {}
template<class...T> void log_error(T&&...) {}
}
namespace TWFunc {
uint64_t GetFileSize(const std::string& s) {
  std::error_code ec; auto n=std::filesystem::file_size(s,ec); return ec?0:n;
}
}
enum class BackupMethod {kFiles,kDd};
struct PartitionSettings {std::string backup_folder=".";};
static std::string scenario;
static unsigned writes=0, syncs=0, closes=0, discards=0, capacities=0;
static dev_t target_dev; static ino_t target_ino;
static uint64_t capacity=32768;
static bool is_target(int fd) {
  struct stat st{}; return ::fstat(fd,&st)==0 && st.st_dev==target_dev && st.st_ino==target_ino;
}
extern "C" int __real_fstat(int,struct stat*);
extern "C" int __wrap_fstat(int fd,struct stat* st) {
  int rc=__real_fstat(fd,st);
  if(rc==0 && st->st_dev==target_dev && st->st_ino==target_ino && scenario!="regular-target")
    st->st_mode=(st->st_mode&07777)|S_IFBLK;
  return rc;
}
extern "C" int __wrap_ioctl(int fd,unsigned long op,...) {
  assert(is_target(fd) && op==BLKGETSIZE64);
  va_list ap; va_start(ap,op); auto* n=va_arg(ap,uint64_t*); va_end(ap);
  ++capacities;
  if(scenario=="capacity-error") {errno=EIO; return -1;}
  if(scenario=="capacity-eintr" && capacities==1) {errno=EINTR; return -1;}
  *n=capacity; return 0;
}
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" ssize_t __wrap_write(int fd,const void* p,size_t n) {
  if(is_target(fd)) {
    ++writes;
    if(scenario=="write-error") {errno=ENOSPC; return -1;}
    if(scenario=="write-late-error" && writes==2) {errno=EIO; return -1;}
    if(scenario=="write-eintr" && writes==1) {errno=EINTR; return -1;}
    if(scenario=="write-short" && n>1) n/=2;
  }
  return __real_write(fd,p,n);
}
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd) {
  assert(is_target(fd)); ++syncs;
  if(scenario=="sync-error") {errno=EIO; return -1;}
  if(scenario=="sync-eintr" && syncs==1) {errno=EINTR; return -1;}
  return __real_fsync(fd);
}
extern "C" int __real_close(int);
extern "C" int __wrap_close(int fd) {
  bool target=is_target(fd); int rc=__real_close(fd);
  if(target) {++closes; if(scenario=="close-error") {errno=EIO;return -1;}}
  return rc;
}
// libsparse's final truncate is unsupported on real block devices. Reproduce
// that behavior on the single designated file, preserving its capacity/tail.
extern "C" int __real_ftruncate64(int,off64_t);
extern "C" int __wrap_ftruncate64(int fd,off64_t n) {
  if(is_target(fd)) {errno=EINVAL;return -1;}
  return __real_ftruncate64(fd,n);
}
struct TWPartition {
  std::string backup_file_name_="input.sparse",actual_block_device_="target.bin";
  std::string display_name_="private fixture", mount_point_="/fixture";
  BackupMethod backup_method_=BackupMethod::kDd;
  bool can_flash_img_=true;
  uint64_t size_=32768;
  bool FindPartitionSize(){return true;} // actual capacity separately at ioctl
  bool RawReadWrite(const PartitionSettings*) const {assert(false);return false;}
  bool BlkDiscard() const {++discards;return true;} // no actual discard ioctl
  bool FlashImage(const PartitionSettings*);
  bool IsSparseImage(const std::string&);
  bool FlashSparseImage(const std::string&) const;
};
// PRODUCTION_METHODS
int main(int argc,char** argv) {
  assert(argc==3); scenario=argv[1]; bool expected=std::string(argv[2])=="1";
  struct stat st{}; assert(::stat("target.bin",&st)==0);
  target_dev=st.st_dev; target_ino=st.st_ino;
  if(scenario=="actual-small") capacity=8192;
  if(scenario=="zero-capacity") capacity=0;
  TWPartition p;
  if(scenario=="cached-small") p.size_=8192;
  if(scenario=="files-target") p.backup_method_=BackupMethod::kFiles;
  if(scenario=="disabled-target") p.can_flash_img_=false;
  PartitionSettings settings;
  // Missing source bypasses IsSparseImage's ambiguous false (raw) result here;
  // the caller's missing-file/RawReadWrite path is outside this suite.
  bool result=scenario=="missing-source"?p.FlashSparseImage("absent"):p.FlashImage(&settings);
  printf("result=%d writes=%u syncs=%u closes=%u discards=%u capacity_calls=%u\n",
         result,writes,syncs,closes,discards,capacities);
  fflush(stdout);
  assert(result==expected);
  if(expected) assert(syncs==(scenario=="sync-eintr"?2u:1u) && closes==1);
  if(scenario=="expanded-oversize" || scenario=="cached-small" || scenario=="actual-small" ||
     scenario=="capacity-error" || scenario=="zero-capacity" || scenario=="regular-target" ||
     scenario=="bad-chunk" || scenario=="zero-blocks" || scenario=="files-target" ||
     scenario=="disabled-target" || scenario=="missing-source") assert(writes==0 && discards==0);
  return 0;
}
