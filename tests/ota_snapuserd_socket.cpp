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
#include <snapuserd/snapuserd_client.h>
#include <sys/socket.h>
#include <thread>
#include <cstring>

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
 bool GetTableStatus(const std::string& name, std::vector<TargetInfo>* targets) override {
 assert(name=="system_b");events.push_back("table-status");
 TargetInfo target;memset(&target.spec,0,sizeof(target.spec));strcpy(target.spec.target_type,"user");
 targets->push_back(target);return true;
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


namespace android::snapshot {
// Existing upstream test-friend seam. No production header or method replaced.
class SnapshotTest {
 public:
 static void Client(SnapshotManager& manager,int fd) {
  manager.snapuserd_client_=std::make_unique<SnapuserdClient>(android::base::unique_fd(fd));
 }
};
}
static void store(const std::string& path,const std::string& data) {
 assert(android::base::WriteStringToFile(data,path));
}
int main(int argc,char** argv) {
 assert(argc==2);std::string mode=argv[1];
 fs::create_directories("/work/meta/snapshots");
 SnapshotUpdateStatus status;status.set_state(UpdateState::Initiated);
 status.set_userspace_snapshots(true);status.set_using_snapuserd(true);
 store("/work/meta/state",status.SerializeAsString());store("/work/meta/snapshot-boot","_a");
 SnapshotStatus snap;snap.set_name("system_b");snap.set_state(SnapshotState::CREATED);
 store("/work/meta/snapshots/system_b",snap.SerializeAsString());
 devices={"system_b","system_b-cow","system_b-base","system_b-src"};
 int fd[2];assert(socketpair(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0,fd)==0);
 auto manager=SnapshotManager::New(new Info);SnapshotTest::Client(*manager,fd[0]);
 bool received=false;
 if(mode=="closed-peer") {close(fd[1]);fd[1]=-1;}
 std::thread peer;
 if(fd[1]>=0)peer=std::thread([&](){
  const std::string expected="delete,system_b";std::string request;
  while(request.size()<expected.size()) {
   char bytes[32];auto n=recv(fd[1],bytes,sizeof(bytes),0);assert(n>0);request.append(bytes,n);
  }
  assert(request==expected);received=true;
  if(mode!="eof") {
   const std::string response=mode=="success"?"success":mode=="failure"?"fail":"succ";
   assert(send(fd[1],response.data(),response.size(),MSG_NOSIGNAL)==ssize_t(response.size()));
  }
  shutdown(fd[1],SHUT_RDWR);close(fd[1]);
 });
 bool result=manager->UnmapUpdateSnapshot("system_b");
 if(peer.joinable())peer.join();
 bool expected=mode=="success";
 printf("mode=%s result=%d expected=%d peer_request=%d remaining=%zu image=%d\n",mode.c_str(),result,expected,received,devices.size(),image_mapped);fflush(stdout);
 assert(result==expected);assert(received==(mode!="closed-peer"));
 assert(!devices.contains("system_b"));
 if(expected)assert(devices.empty()&&!image_mapped);
 else {
  assert(devices==std::set<std::string>({"system_b-cow","system_b-base","system_b-src"}));
  assert(image_mapped);
 }
 std::vector<std::string> first={"state:system_b","state:system_b","table-status","delete:system_b"};
 if(expected)first.insert(first.end(),{"image-open","delete:system_b-cow","image-state","image-unmap","delete:system_b-base","delete:system_b-src"});
 assert(events==first);
 // Once device deletion succeeded but notification failed, existing implementation
 // skips notification for the now-absent device on retry. Record, don't hide it.
 if(!expected) {
  events.clear();assert(manager->UnmapUpdateSnapshot("system_b"));
  assert(devices.empty()&&!image_mapped);
  assert(events.front()=="state:system_b");
  for(const auto& event:events)assert(event!="table-status");
 }
 puts("PASS actual manager/client socket request/response; daemon peer and mapper modeled");
}
