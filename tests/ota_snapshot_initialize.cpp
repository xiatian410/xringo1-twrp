// Real SnapshotManager creates/initializes COWs; only DM/file views are modeled.
#define OTA_ALLOCATION_LIBRARY
#include "ota_snapshot_allocate.cpp"
#include <libsnapshot/cow_reader.h>
static std::map<std::string,std::string> file_views;
static std::set<std::string> active_views;
static unsigned created=0,paths=0,hal_completed=0;
class FileMapper final:public android::dm::IDeviceMapper {
 public:
 bool CreateDevice(const std::string& name,const DmTable& table,std::string* path,const std::chrono::milliseconds&)override {
  assert(name.ends_with("_b-cow")&&table.valid()&&!table.readonly());
  const auto part=name.substr(0,name.size()-4);assert(expected.contains(part));
  assert(table.num_sectors()*512==expected.at(part).second);
  ++created;assert(!active_views.contains(name));
  auto target="/work/cows/"+name;
  android::base::unique_fd fd(open(target.c_str(),O_CREAT|O_RDWR|O_TRUNC,0600));
  assert(fd>=0&&ftruncate(fd.get(),expected.at(part).second)==0);
  // This is a separate file view, not a kernel mapping or alias into super.
  file_views[name]=target;active_views.insert(name);*path=target;
  if(scenario=="header-sync-error"&&created==2)sync_failure=target;
  return true;
 }
 DmDeviceState GetState(const std::string& n)const override{return active_views.contains(n)?DmDeviceState::ACTIVE:DmDeviceState::INVALID;}
 bool LoadTableAndActivate(const std::string&,const DmTable&)override{denied();}
 bool LoadTable(const std::string&,const DmTable&)override{denied();}
 bool GetTableInfo(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetTableStatus(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetTableStatusIma(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetDmDevicePathByName(const std::string& n,std::string* p)override{if(!active_views.contains(n))return false;*p=file_views.at(n);return true;}
 bool GetDeviceString(const std::string&,std::string*)override{denied();}
 bool DeleteDeviceIfExists(const std::string& n)override{active_views.erase(n);return true;}
};
class FileImages final:public android::fiemap::IImageManager {
 public:
 android::fiemap::FiemapStatus CreateBackingImage(const std::string&,uint64_t,int,std::function<bool(uint64_t,uint64_t)>&&)override{denied();}
 bool DeleteBackingImage(const std::string&)override{denied();}
 bool MapImageDevice(const std::string&,const std::chrono::milliseconds&,std::string*)override{denied();}
 bool UnmapImageDevice(const std::string&)override{denied();}
 bool BackingImageExists(const std::string&)override{return false;}
 bool IsImageMapped(const std::string&)override{return false;}
 bool MapImageWithDeviceMapper(const IPartitionOpener&,const std::string&,std::string*)override{denied();}
 bool GetMappedImageDevice(const std::string& n,std::string* p)override {
  assert(active_views.contains(n));++paths;*p=file_views.at(n);
  if(scenario=="path-error"&&paths==2)return false;
  return true;
 }
 bool MapAllImages(const std::function<bool(std::set<std::string>)>&)override{denied();}
 bool DisableImage(const std::string&)override{denied();}
 bool RemoveDisabledImages()override{denied();}
 std::vector<std::string> GetAllBackingImages()override{return {};}
 android::fiemap::FiemapStatus ZeroFillNewImage(const std::string&,uint64_t)override{denied();}
 bool RemoveAllImages()override{return true;}
 bool DisableAllImages()override{return true;}
 bool IsImageDisabled(const std::string&)override{denied();}
};
class InitInfo final:public ISnapshotManager::IDeviceInfo {
 FileMapper dm;FileOpener opener;
 public:
 std::string GetMetadataDir()const override{return "/work/meta";}
 std::string GetSlotSuffix()const override{return "_a";}
 std::string GetOtherSlotSuffix()const override{return "_b";}
 std::string GetSuperDevice(uint32_t n)const override{assert(n<2);return "/work/super";}
 const IPartitionOpener& GetPartitionOpener()const override{return opener;}
 bool IsOverlayfsSetup()const override{return false;}
 bool SetBootControlMergeStatus(MergeStatus s)override{assert(s==MergeStatus::NONE||s==MergeStatus::SNAPSHOTTED);if(s==MergeStatus::SNAPSHOTTED)++hal_completed;return true;}
 bool SetActiveBootSlot(unsigned)override{denied();}
 bool SetSlotAsUnbootable(unsigned)override{denied();}
 bool IsSlotMarkedSuccessful(unsigned)override{denied();}
 bool IsRecovery()const override{return true;}
 bool IsTestDevice()const override{return true;} // disables scratch allocation and daemon startup explicitly
 bool IsFirstStageInit()const override{return false;}
 std::unique_ptr<IImageManager> OpenImageManager()const override{return std::make_unique<FileImages>();}
 android::dm::IDeviceMapper& GetDeviceMapper()override{return dm;}
 bool IsTempMetadata()const override{return false;}
};
int main(int argc,char**argv){
 android::base::SetLogger(android::base::StderrLogger);assert(argc==2);scenario=argv[1];
 IPropertyFetcher::OverrideForTesting(std::make_shared<Props>());
 DeltaArchiveManifest manifest;assert(manifest.ParseFromString(read("/work/manifest.pb")));
 prepare_layout(manifest);fs::create_directories("/work/meta/snapshots");fs::create_directory("/work/cows");
 const auto before=metadata_prefix();auto manager=SnapshotManager::New(new InitInfo);
 assert(manager->BeginUpdate());auto result=manager->CreateUpdateSnapshots(manifest);
 bool success=scenario=="normal";assert(bool(result)==success);assert(active_views.empty());
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state")));assert(state.state()==UpdateState::Initiated);
 auto count=std::distance(fs::directory_iterator("/work/meta/snapshots"),fs::directory_iterator{});
 if(!success){
  assert(created==2&&paths==2&&count==0&&metadata_prefix()==before);
  if(scenario=="header-sync-error")assert(sync_injections==1);
  printf("PASS %s created=%u paths=%u cleanup=1 state=%d error=%d\n",argv[1],created,paths,int(state.state()),int(result.error_code()));return 0;
 }
 assert(created==10&&paths==10&&count==10&&state.using_snapuserd()&&state.userspace_snapshots());
 FileOpener opener;auto metadata=ReadMetadata(opener,"super",1);assert(metadata);
 auto target=MetadataBuilder::New(*metadata);assert(target);
 for(const auto& [n,values]:expected){
  SnapshotStatus status;assert(status.ParseFromString(read("/work/meta/snapshots/"+n)));
  assert(status.state()==SnapshotState::CREATED&&status.using_snapuserd());
  assert(status.device_size()==values.first&&status.cow_partition_size()==values.second&&status.cow_file_size()==0);
  assert(target->FindPartition(n)&&target->FindPartition(n)->size()==values.first);
  assert(target->FindPartition(n+"-cow")&&target->FindPartition(n+"-cow")->size()==values.second);
  android::base::unique_fd fd(open(file_views.at(n+"-cow").c_str(),O_RDONLY));assert(fd>=0);
  CowReader reader;assert(reader.Parse(std::move(fd)));
  assert(reader.GetHeader().prefix.major_version==manifest.dynamic_partition_metadata().cow_version());
  assert(reader.GetHeader().block_size==4096&&reader.GetOpIter()->AtEnd());
 }
 assert(fs::exists("/work/meta/old-partition-metadata"));
 // Recreate manager, proving persisted allocation state feeds actual completion.
 manager.reset();manager=SnapshotManager::New(new InitInfo);assert(manager->FinishedSnapshotWrites(false));
 assert(state.ParseFromString(read("/work/meta/state"))&&state.state()==UpdateState::Unverified&&hal_completed==1);
 assert(read("/work/meta/snapshot-boot")=="_a");
 printf("PASS normal initialized=10 parsed=10 published_lp=1 recreated_completion=1 state=%d hal=%u\n",int(state.state()),hal_completed);
}
