// The actual backend thread and manager route reach the actual sparse writer.
// Only private file targets exist; capacity/discovery/hardware remain fixtures.
#include <algorithm>
#include <cassert>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <thread>
#include <vector>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <android-base/unique_fd.h>
#include <android-base/scopeguard.h>
#include <sparse/sparse.h>
#include "sparse_format.h"
#include "twrp_install_backend.h"
#include "twrp_operation_executor.h"
twrp_operation_executor& twrp_operation_executor::instance() {
  static twrp_operation_executor executor;return executor;
}
namespace fs=std::filesystem;
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
static std::string scenario;
static std::vector<std::string> events;
static std::mutex gate_mutex;
static std::condition_variable gate;
static bool entered=false,released=false;
static bool block_io=false;
static std::map<std::string,std::pair<dev_t,ino_t>> targets;
static std::string target_for(int fd) {
  struct stat st{}; if(::fstat(fd,&st)!=0)return {};
  for(const auto& [name,id]:targets) if(id==std::pair(st.st_dev,st.st_ino)) return name;
  return {};
}
extern "C" int __real_fstat(int,struct stat*);
extern "C" int __wrap_fstat(int fd,struct stat* st) {
  int rc=__real_fstat(fd,st);
  if(rc==0) for(const auto& [name,id]:targets) if(id==std::pair(st->st_dev,st->st_ino)) st->st_mode=(st->st_mode&07777)|S_IFBLK;
  return rc;
}
extern "C" int __wrap_ioctl(int fd,unsigned long op,...) {
  auto name=target_for(fd);assert(!name.empty() && op==BLKGETSIZE64);
  va_list ap;va_start(ap,op);auto* size=va_arg(ap,uint64_t*);va_end(ap);
  events.push_back("capacity:"+name);*size=scenario=="second-small" && name=="boot_b"?4096:32768;
  return 0;
}
extern "C" ssize_t __real_write(int,const void*,size_t);
extern "C" ssize_t __wrap_write(int fd,const void* p,size_t n) {
  auto name=target_for(fd);
  if(!name.empty()) {
    if(block_io) {
      std::unique_lock lock(gate_mutex);entered=true;gate.notify_all();gate.wait(lock,[]{return released;});
    }
    events.push_back("write:"+name);
    if((scenario=="first-write-error" && name=="boot_a") ||
       (scenario=="second-write-error" && name=="boot_b")) {errno=EIO;return -1;}
  }
  return __real_write(fd,p,n);
}
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd) {
  auto name=target_for(fd);assert(!name.empty());events.push_back("sync:"+name);
  if(scenario=="second-sync-error" && name=="boot_b") {errno=EIO;return -1;}
  return __real_fsync(fd);
}
extern "C" int __real_close(int);
extern "C" int __wrap_close(int fd) {
  auto name=target_for(fd);int rc=__real_close(fd);
  if(!name.empty()) {
    events.push_back("close:"+name);
    if(scenario=="second-close-error" && name=="boot_b") {errno=EIO;return -1;}
  }
  return rc;
}
extern "C" int __real_ftruncate64(int,off64_t);
extern "C" int __wrap_ftruncate64(int fd,off64_t n) {
  if(!target_for(fd).empty()) {errno=EINVAL;return -1;}
  return __real_ftruncate64(fd,n);
}
struct DataManager {
  static inline std::mutex mutex;
  static inline std::map<std::string,std::string> values;
  static void SetValue(const std::string& k,const std::string& v) {std::lock_guard l(mutex);values[k]=v;}
  static void SetValue(const std::string& k,int v) {SetValue(k,std::to_string(v));}
  static std::string GetStrValue(const std::string& k) {std::lock_guard l(mutex);return values[k];}
  static int GetIntValue(const std::string& k) {return std::atoi(GetStrValue(k).c_str());}
  static void GetValue(const std::string& k,std::string& out) {out=GetStrValue(k);}
  static void SetProgress(double) {}
};
namespace gui2_console {
template<class...T> void info(T&&...) {}
template<class...T> void log_error(T&&...) {}
template<class...T> void highlight(T&&...) {}
}
namespace TWFunc {
uint64_t GetFileSize(const std::string& p) {std::error_code ec;auto n=fs::file_size(p,ec);return ec?0:n;}
bool IsPathExists(const std::string& p) {return fs::exists(p);}
std::string GetRootPath(const std::string&);
}
enum class BackupMethod {kFiles,kDd};
enum class PartitionManagerOp {kRestore};
enum Repack_Type {REPLACE_NONE,REPLACE_RAMDISK,REPLACE_KERNEL};
struct RepackOptionsStruct {Repack_Type Type;bool Backup_First,Disable_Verity,Disable_Force_Encrypt;};
struct twrpRepacker {bool Repack_Image_And_Flash(const std::string&,const RepackOptionsStruct&){assert(false);return false;}};
struct ProgressTracking {explicit ProgressTracking(uint64_t) {}};
struct PartitionSettings {std::string backup_folder;ProgressTracking* progress;PartitionManagerOp pm_method;};
struct PartitionList {std::string display_name,mount_point;bool slot_select=false;};
struct TWPartition {
  std::string mount_point_,actual_block_device_,backup_file_name_,display_name_;
  std::string storage_path_,symlink_mount_point_;
  bool slot_select_=true,is_storage_=false;
  uint64_t size_=32768;
  BackupMethod backup_method_=BackupMethod::kDd;
  bool can_flash_img_=true;
  bool FindPartitionSize();
  bool RawReadWrite(const PartitionSettings*) const {assert(false);return false;}
  bool IsSlotSelect() const;
  bool FlashImage(const PartitionSettings*);
  bool IsSparseImage(const std::string&);
  bool FlashSparseImage(const std::string&) const;
};
struct TWPartitionManager {
  std::vector<TWPartition*> partitions_;
  std::string active_slot_display_="A";
  bool FlashImage(const std::string&,const std::string&) const;
  static bool MatchesPath(const TWPartition*,const std::string&);
  TWPartition* FindPartitionByPath(const std::string&) const;
  std::string GetAndroidRootPath() const {return "/system_root";}
  void OverrideActiveSlot(const std::string&);
  std::string GetActiveSlotDisplay();
  std::string GetActiveSlotSuffix() const;
  void UpdateSystemDetails() {events.push_back("override:"+active_slot_display_);}
  bool MountByPath(const std::string&,bool) const {events.push_back("source-mount-denied");return false;}
  bool TryGetPartitionList(const std::string&,std::vector<PartitionList>* out) {
    if(scenario=="list-unavailable")return false;
    for(auto* p:partitions_) if(p->can_flash_img_)out->push_back({p->display_name_,p->mount_point_,p->slot_select_});return true;
  }
} PartitionManager;
bool TWPartition::FindPartitionSize() {
  auto suffix=slot_select_?PartitionManager.GetActiveSlotSuffix():"";
  actual_block_device_=mount_point_.substr(1)+suffix+".bin";
  events.push_back("resolve:"+actual_block_device_);
  return scenario!="size-unknown";
}
static unsigned starts=0,ends=0;
static int completion=-1;
namespace gui2_backend {
void operation_start(const std::string&) {++starts;}
void operation_end(int result) {++ends;completion=result;}
// ZIP installation is not linked or run in this sparse route suite.
bool twrp_install_backend::start_zip(const std::vector<std::string>&){assert(false);return false;}
}
// PRODUCTION_METHODS
static void init_target(const std::string& name) {
  struct stat st{};assert(::stat((name+".bin").c_str(),&st)==0);targets[name]={st.st_dev,st.st_ino};
}
int main(int argc,char** argv) {
  assert(argc==2);scenario=argv[1];
  for(auto name:{"boot_a","boot_b","recovery"})init_target(name);
  TWPartition boot;boot.mount_point_="/boot";boot.display_name_="Boot";
  TWPartition recovery;recovery.mount_point_="/recovery";recovery.display_name_="Recovery";recovery.slot_select_=false;
  PartitionManager.partitions_={&boot,&recovery};
  if(scenario=="initial-B")PartitionManager.active_slot_display_="B";
  if(scenario=="disabled")boot.can_flash_img_=false;
  if(scenario=="files-target")boot.backup_method_=BackupMethod::kFiles;
  const auto initial=PartitionManager.active_slot_display_;
  gui2_backend::twrp_install_backend backend;
  bool dual=scenario.starts_with("second-") || scenario=="dual" || scenario=="initial-B" || scenario=="first-write-error";
  if(scenario=="route-names" || scenario=="list-unavailable") {
    assert(backend.image_target_for("BoOt_B.ImG")=="/boot");
    assert(backend.image_target_for("vendor_boot_a.img")=="/vendor_boot");
    assert(backend.image_target_for("init_boot.img")=="/init_boot");
    assert(backend.image_target_for("recovery-custom.img")=="/recovery");
    assert(backend.image_target_for("dtbo_b.img")=="/dtbo");
    assert(backend.image_target_for("unrecognized.img").empty());
    if(scenario=="list-unavailable")assert(backend.image_target_for("kernelsu_patched_test.img").empty());
    else {
      assert(backend.image_targets().size()==2);
      assert(backend.image_target_for("kernelsu_patched_test.img")=="/boot");
      TWPartition init;init.mount_point_="/init_boot";PartitionManager.partitions_.push_back(&init);
      assert(backend.image_target_for("kernelsu_patched_test.img")=="/init_boot");
    }
    return 0;
  }
  std::string target=scenario=="nonslot"?"/recovery":"/boot";
  if(scenario=="nonslot")dual=true;
  if(scenario=="unknown-target")target="/boot-extra";
  if(scenario=="multiple-targets")target="/boot;/recovery";
  if(scenario=="empty-target")target="";
  block_io=scenario=="busy";
  const auto input=fs::absolute("input.sparse").string();
  assert(!backend.start_image("",target,dual));
  assert(backend.start_image(scenario=="missing-source"?input+".absent":input,target,dual));
  if(block_io) {
    std::unique_lock lock(gate_mutex);
    assert(gate.wait_for(lock,std::chrono::seconds(5),[]{return entered;}));
    auto state=backend.status();assert(state.state==gui2_backend::install_state::RUNNING);
    assert(!backend.start_image(input,"/recovery",false));
    assert(DataManager::GetStrValue("tw_flash_partition")=="/boot;");
    backend.acknowledge();assert(backend.status().state==gui2_backend::install_state::RUNNING);
    released=true;gate.notify_all();
  }
  auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
  while(backend.status().state==gui2_backend::install_state::RUNNING) {
    assert(std::chrono::steady_clock::now()<deadline);std::this_thread::yield();
  }
  auto status=backend.status();backend.acknowledge(); // joins, then observations are race-free
  bool expected=scenario=="normal" || scenario=="dual" || scenario=="initial-B" || scenario=="nonslot" || scenario=="busy";
#ifndef AB_OTA_UPDATER
  if(scenario.starts_with("second-"))expected=true;
#endif
  assert(status.state==(expected?gui2_backend::install_state::DONE:gui2_backend::install_state::FAILED));
  assert(status.done==int(expected) && status.items.size()==1);
  assert(starts==1 && ends==1 && completion==!expected);
  assert(PartitionManager.GetActiveSlotDisplay()==initial);
  assert(backend.status().state==gui2_backend::install_state::IDLE);
  if(scenario=="unknown-target" || scenario=="multiple-targets" || scenario=="empty-target" || scenario=="missing-source")
    assert(std::none_of(events.begin(),events.end(),[](auto& s){return s.starts_with("write:");}));
  for(const auto& e:events)printf("EVENT %s\n",e.c_str());
  printf("done=%d completion=%d restored_slot=%s\n",status.done,completion,initial.c_str());
}
