// Actual libsnapshot state publication. All storage/boot hardware is denied.
#include <libsnapshot/snapshot.h>
#include <liblp/partition_opener.h>
#include <aidl/android/hardware/boot/MergeStatus.h>
#include <android-base/file.h>
#include <cassert>
#ifdef NDEBUG
#error Fixture assertions must be enabled
#endif
#include <cerrno>
#include <cstdio>
#include <filesystem>
#include <sys/stat.h>
#include <unistd.h>

namespace fs = std::filesystem;
using namespace android::snapshot;
using android::dm::DmTable;
using android::dm::DmDeviceState;
using MergeStatus = aidl::android::hardware::boot::MergeStatus;
static std::string sync_failure;
static unsigned sync_injections = 0, sync_completions = 0, merge_calls = 0;
static bool merge_ok = true, sync_interrupt = false;
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd) {
    struct stat actual{}, selected{};
    if (!sync_failure.empty() && fstat(fd, &actual) == 0 &&
        stat(sync_failure.c_str(), &selected) == 0 &&
        actual.st_dev == selected.st_dev && actual.st_ino == selected.st_ino) {
        if (!sync_interrupt || sync_injections == 0) {
            ++sync_injections; errno = sync_interrupt ? EINTR : EIO; return -1;
        }
        int result = __real_fsync(fd);
        if (result == 0) ++sync_completions;
        return result;
    }
    return __real_fsync(fd);
}
[[noreturn]] static void denied() { assert(false && "unexpected device operation"); abort(); }
class DenyMapper final : public android::dm::IDeviceMapper {
 public:
 bool CreateDevice(const std::string&, const DmTable&, std::string*, const std::chrono::milliseconds&) override { denied(); }
 DmDeviceState GetState(const std::string&) const override { denied(); }
 bool LoadTableAndActivate(const std::string&, const DmTable&) override { denied(); }
 bool LoadTable(const std::string&, const DmTable&) override { denied(); }
 bool GetTableInfo(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetTableStatus(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetTableStatusIma(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetDmDevicePathByName(const std::string&, std::string*) override { denied(); }
 bool GetDeviceString(const std::string&, std::string*) override { denied(); }
 bool DeleteDeviceIfExists(const std::string&) override { denied(); }
};
class DenyOpener final : public android::fs_mgr::IPartitionOpener {
 public:
 android::base::unique_fd Open(const std::string&, int) const override { denied(); }
 bool GetInfo(const std::string&, android::fs_mgr::BlockDeviceInfo*) const override { denied(); }
 std::string GetDeviceString(const std::string&) const override { denied(); }
};
class Info final : public ISnapshotManager::IDeviceInfo {
 DenyMapper dm; DenyOpener opener;
 public:
 std::string GetMetadataDir() const override { return "/work/meta"; }
 std::string GetSlotSuffix() const override { return "_a"; }
 std::string GetOtherSlotSuffix() const override { return "_b"; }
 std::string GetSuperDevice(uint32_t) const override { denied(); }
 const android::fs_mgr::IPartitionOpener& GetPartitionOpener() const override { denied(); }
 bool IsOverlayfsSetup() const override { denied(); }
 bool SetBootControlMergeStatus(MergeStatus status) override {
   assert(status == MergeStatus::NONE); ++merge_calls; return merge_ok;
 }
 bool SetActiveBootSlot(unsigned int) override { denied(); }
 bool SetSlotAsUnbootable(unsigned int) override { denied(); }
 bool IsSlotMarkedSuccessful(unsigned int) override { denied(); }
 bool IsRecovery() const override { return true; }
 bool IsFirstStageInit() const override { return false; }
 std::unique_ptr<IImageManager> OpenImageManager() const override { denied(); }
 android::dm::IDeviceMapper& GetDeviceMapper() override { return dm; }
 bool IsTempMetadata() const override { return false; }
};
#include "update_engine/aosp/dynamic_partition_control_android.h"
#include "update_engine/common/prefs.h"
using namespace chromeos_update_engine;
struct MetadataToken final : AutoDevice {MetadataToken():AutoDevice("fixture-mounted") {}};
namespace chromeos_update_engine {
class DynamicPartitionControlAndroidTest {
 public:
 static void Inject(DynamicPartitionControlAndroid& c){c.snapshot_=SnapshotManager::New(new Info);c.metadata_device_=std::make_unique<MetadataToken>();}
};
}
class Control final : public DynamicPartitionControlAndroid {
 public:
 Control():DynamicPartitionControlAndroid(0){DynamicPartitionControlAndroidTest::Inject(*this);}
 FeatureFlag GetVirtualAbFeatureFlag() override{return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 protected:
 bool IsRecovery() override{return true;}
};
static std::string read(const std::string& path) {
 std::string data; assert(android::base::ReadFileToString(path, &data)); return data;
}
static void write(const std::string& path, const std::string& data) {
 assert(android::base::WriteStringToFile(data, path));
}
int main(int argc, char** argv) {
 assert(argc==2); const std::string name=argv[1];
 fs::create_directories("/work/meta/snapshots");
 SnapshotUpdateStatus initial;
 initial.set_state(name=="missing-snapshots" ? UpdateState::Initiated : UpdateState::None);
 write("/work/meta/state",initial.SerializeAsString());
 if(name=="missing-snapshots")fs::remove_all("/work/meta/snapshots");
 if(name=="missing-metadata")fs::remove_all("/work/meta");
 if((name=="state-open-error"||name=="reset-open-error"))fs::create_directory("/work/meta/state.tmp");
 if((name=="state-sync-error"||name=="reset-sync-error"))sync_failure="/work/meta/state.tmp";
 if(name=="state-sync-interrupted"){sync_failure="/work/meta/state.tmp";sync_interrupt=true;}
 if(name=="merge-status-error")merge_ok=false;
 auto manager=SnapshotManager::New(new Info);
 const bool expected=name=="normal"||name=="reset-normal"||name=="state-sync-interrupted";
 fs::create_directory("/work/prefs");
 Prefs prefs; assert(prefs.Init(base::FilePath("/work/prefs")));
 const bool reset=name.starts_with("reset-");
 const bool result=reset ? Control().ResetUpdate(&prefs) : manager->CancelUpdate();
 printf("RESULT name=%s cancelled=%d expected=%d merges=%u sync_errors=%u\n",name.c_str(),result,expected,merge_calls,sync_injections);fflush(stdout);
 assert(result==expected);
 if(name=="missing-metadata")return 0;
 SnapshotUpdateStatus after;assert(after.ParseFromString(read("/work/meta/state")));
 assert(after.state()==initial.state());
 if(name=="state-sync-interrupted")assert(sync_injections==1&&sync_completions==1);
 if((name=="state-sync-error"||name=="reset-sync-error"))assert(sync_injections==1&&sync_completions==0);
 if(!expected){
  manager.reset();sync_failure.clear();merge_ok=true;
  if((name=="state-open-error"||name=="reset-open-error"))fs::remove("/work/meta/state.tmp");
  if(name=="missing-snapshots")return 0; // image cleanup remains a denied boundary
  manager=SnapshotManager::New(new Info);assert(reset ? Control().ResetUpdate(&prefs) : manager->CancelUpdate());
  assert(after.ParseFromString(read("/work/meta/state"))&&after.state()==UpdateState::None);
 }
 puts("PASS actual cancellation and persisted-state retry; hardware denied");
}
