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
#include <set>
#include <vector>
#include <string>
#include <libfiemap/image_manager.h>

namespace fs = std::filesystem;
using namespace android::snapshot;
using android::dm::DmTable;
using android::dm::DmDeviceState;
using MergeStatus = aidl::android::hardware::boot::MergeStatus;
static std::string failure;
static std::vector<std::string> events;
static std::set<std::string> devices;
static bool image_mapped=true;
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd) {return __real_fsync(fd);}
[[noreturn]] static void denied() { assert(false && "unexpected device operation"); abort(); }
class DenyMapper final : public android::dm::IDeviceMapper {
 public:
 bool CreateDevice(const std::string&, const DmTable&, std::string*, const std::chrono::milliseconds&) override { denied(); }
 DmDeviceState GetState(const std::string& name) const override {
 events.push_back("state:"+name);
 return devices.contains(name)?DmDeviceState::ACTIVE:DmDeviceState::INVALID;
 }
 bool LoadTableAndActivate(const std::string&, const DmTable&) override { denied(); }
 bool LoadTable(const std::string&, const DmTable&) override { denied(); }
 bool GetTableInfo(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetTableStatus(const std::string& name, std::vector<TargetInfo>*) override {
 assert(name=="system_b");events.push_back("table-status");return false;
 }
 bool GetTableStatusIma(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetDmDevicePathByName(const std::string&, std::string*) override { return false; }
 bool GetDeviceString(const std::string&, std::string*) override { denied(); }
 bool DeleteDeviceIfExists(const std::string& name) override {
 events.push_back("delete:"+name);
 if(failure==name)return false;
 devices.erase(name);return true;
 }
};
class DenyOpener final : public android::fs_mgr::IPartitionOpener {
 public:
 android::base::unique_fd Open(const std::string&, int) const override { denied(); }
 bool GetInfo(const std::string&, android::fs_mgr::BlockDeviceInfo*) const override { denied(); }
 std::string GetDeviceString(const std::string&) const override { denied(); }
};
class Images final : public android::fiemap::IImageManager {
 public:
 android::fiemap::FiemapStatus CreateBackingImage(const std::string&,uint64_t,int,std::function<bool(uint64_t,uint64_t)>&&) override {denied();}
 bool DeleteBackingImage(const std::string&) override {denied();}
 bool MapImageDevice(const std::string&,const std::chrono::milliseconds&,std::string*) override {denied();}
 bool UnmapImageDevice(const std::string& name) override {
  assert(name=="system_b-cow-img");events.push_back("image-unmap");
  if(failure=="image")return false;image_mapped=false;return true;
 }
 bool BackingImageExists(const std::string&) override {denied();}
 bool IsImageMapped(const std::string& name) override {
  assert(name=="system_b-cow-img");events.push_back("image-state");return image_mapped;
 }
 bool MapImageWithDeviceMapper(const IPartitionOpener&,const std::string&,std::string*) override {denied();}
 bool GetMappedImageDevice(const std::string&,std::string*) override {denied();}
 bool MapAllImages(const std::function<bool(std::set<std::string>)>&) override {denied();}
 bool DisableImage(const std::string&) override {denied();}
 bool RemoveDisabledImages() override {denied();}
 std::vector<std::string> GetAllBackingImages() override {denied();}
 android::fiemap::FiemapStatus ZeroFillNewImage(const std::string&,uint64_t) override {denied();}
 bool RemoveAllImages() override {denied();}
 bool DisableAllImages() override {denied();}
 bool IsImageDisabled(const std::string&) override {denied();}
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
   (void)status;denied();
 }
 bool SetActiveBootSlot(unsigned int) override { denied(); }
 bool SetSlotAsUnbootable(unsigned int) override { denied(); }
 bool IsSlotMarkedSuccessful(unsigned int) override { denied(); }
 bool IsRecovery() const override { return true; }
 bool IsFirstStageInit() const override { return false; }
 std::unique_ptr<IImageManager> OpenImageManager() const override {
 events.push_back("image-open");if(failure=="open-image")return nullptr;
 return std::make_unique<Images>();
 }
 android::dm::IDeviceMapper& GetDeviceMapper() override { return dm; }
 bool IsTempMetadata() const override { return false; }
};

#include "update_engine/aosp/dynamic_partition_control_android.h"
using namespace chromeos_update_engine;
struct Token final : AutoDevice {Token():AutoDevice("fixture-mounted") {}};
namespace chromeos_update_engine {
class DynamicPartitionControlAndroidTest {
 public:
 static void Inject(DynamicPartitionControlAndroid& c) {
  c.snapshot_=SnapshotManager::New(new Info);c.metadata_device_=std::make_unique<Token>();
 }
};
}
class Control final : public DynamicPartitionControlAndroid {
 public:
 Control():DynamicPartitionControlAndroid(0){DynamicPartitionControlAndroidTest::Inject(*this);}
 FeatureFlag GetVirtualAbFeatureFlag() override{return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 protected:
 bool IsRecovery() override{return true;}
};
static void store(const std::string& path,const std::string& data) {
 assert(android::base::WriteStringToFile(data,path));
}
static std::vector<std::string> collapsed() {
 std::vector<std::string> result;
 for(const auto& e:events)if(result.empty()||result.back()!=e)result.push_back(e);
 return result;
}
int main(int argc,char** argv) {
 assert(argc==2);std::string mode=argv[1];
 fs::create_directories("/work/meta/snapshots");
 SnapshotUpdateStatus status;status.set_state(UpdateState::Initiated);
 status.set_userspace_snapshots(mode.starts_with("userspace-"));
 store("/work/meta/state",status.SerializeAsString());
 store("/work/meta/snapshot-boot","_a");
 SnapshotStatus snap;snap.set_name("system_b");snap.set_state(SnapshotState::CREATED);
 store("/work/meta/snapshots/system_b",snap.SerializeAsString());
 devices={"system_b","system_b-cow","system_b-base","system_b-src"};
 if(mode=="userspace-unmapped")devices.erase("system_b");
 if(mode=="snapshot-fail"||mode=="userspace-delete-fail")failure="system_b";
 if(mode=="cow-fail"||mode=="control-cow-fail")failure="system_b-cow";
 if(mode=="base-fail")failure="system_b-base";
 if(mode=="source-fail")failure="system_b-src";
 if(mode=="image-fail")failure="image";
 if(mode=="open-image")failure=mode;
 if(mode=="missing-metadata")fs::remove_all("/work/meta");
 if(mode=="all-missing-directory")fs::remove_all("/work/meta/snapshots");
 auto manager=SnapshotManager::New(new Info);
 const bool controller=mode.starts_with("control-");
 const bool all=mode.starts_with("all-");
 auto run=[&](){return controller ? Control().UnmapAllPartitions() :
  all ? manager->UnmapAllSnapshots() : manager->UnmapUpdateSnapshot("system_b");};
 bool result=run();
 bool expected=failure.empty()&&mode!="missing-metadata"&&mode!="all-missing-directory";
 printf("mode=%s result=%d expected=%d attempts=%zu remaining=%zu image=%d\n",mode.c_str(),result,expected,events.size(),devices.size(),image_mapped);fflush(stdout);
 assert(result==expected);
 auto actual=collapsed();
 std::vector<std::string> order={"delete:system_b","image-open","delete:system_b-cow","image-state","image-unmap","delete:system_b-base","delete:system_b-src"};
 if(mode.starts_with("userspace-")) {
  order[0]="state:system_b";
  if(mode!="userspace-unmapped")order.insert(order.begin()+1,{"table-status","delete:system_b"});
 }
 size_t stop=order.size();
 if(mode=="snapshot-fail")stop=1;
 if(mode=="userspace-delete-fail")stop=3;
 if(mode=="open-image")stop=2;
 if(mode=="cow-fail"||mode=="control-cow-fail")stop=3;
 if(mode=="image-fail")stop=5;
 if(mode=="base-fail")stop=6;
 if(mode=="source-fail")stop=7;
 if(mode=="missing-metadata"||mode=="all-missing-directory")stop=0;
 order.resize(stop);assert(actual==order);
 std::set<std::string> expected_devices={"system_b","system_b-cow","system_b-base","system_b-src"};
 if(mode=="userspace-unmapped")expected_devices.erase("system_b");
 bool expected_image=true;
 for(const auto& e:order) {
  if(e.starts_with("delete:")&&e.substr(7)!=failure)expected_devices.erase(e.substr(7));
  if(e=="image-unmap"&&failure!="image")expected_image=false;
 }
 assert(devices==expected_devices&&image_mapped==expected_image);
 printf("ORDER");for(const auto& e:actual)printf(" %s",e.c_str());puts("");
 if(expected)assert(devices.empty()&&!image_mapped);
 // Clear injected fault and retry the same manager (controller creates a new one).
 if(!failure.empty()) {
  auto prior=devices;failure.clear();events.clear();assert(run());
  assert(devices.empty()&&!image_mapped);
  assert(!prior.empty());
 }
 if(expected) {
  events.clear();assert(run());assert(devices.empty()&&!image_mapped);
  for(const auto& e:events)assert(e!="image-unmap");
 }
 assert(!fs::exists("/dev/mapper"));
 fflush(stdout);
 puts("PASS original SnapshotManager unmap ordering/retry; modeled devices only");
}
