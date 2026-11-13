// Actual SnapshotManager allocation with stock manifest and synthetic LP layout.
// Only private sparse regular files; device mapper creation deliberately fails.
#define main unused_completion_main
#include "ota_snapshot_finish.cpp"
#undef main
#include <liblp/builder.h>
#include <liblp/liblp.h>
#include <liblp/property_fetcher.h>
#include <libfiemap/image_manager.h>
#include <update_engine/update_metadata.pb.h>
#include <fcntl.h>
#include <android-base/logging.h>
#include <set>
using namespace android::fs_mgr;
using namespace chromeos_update_engine;
static uint64_t super_size;
static unsigned map_attempts=0, image_attempts=0;
static bool no_kernel=false, cancel_after_map=false;
static std::string scenario;
static std::map<std::string,std::pair<uint64_t,uint64_t>> expected;
extern "C" bool model_kernel(android::dm::DeviceMapper*,const std::string&,android::dm::DmTargetTypeInfo*) __asm__("__wrap__ZN7android2dm12DeviceMapper15GetTargetByNameERKNSt3__112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEEPNS0_16DmTargetTypeInfoE");
extern "C" bool model_kernel(android::dm::DeviceMapper*,const std::string& n,android::dm::DmTargetTypeInfo* info){assert(n=="user"&&!info);return !no_kernel;}
class Props final:public IPropertyFetcher {
 public:
 std::string GetProperty(const std::string& k,const std::string& d) override {
  if(k=="ro.vendor.build.version.release_or_codename")return "17";
  return d;
 }
 bool GetBoolProperty(const std::string& k,bool d) override {
  if(k=="ro.virtual_ab.enabled"||k=="ro.virtual_ab.userspace.snapshots.enabled")return true;
  return d;
 }
};
class FileOpener final:public IPartitionOpener {
 public:
 android::base::unique_fd Open(const std::string& n,int flags)const override {
  assert(n=="super"||n=="/work/super");
  return android::base::unique_fd(open("/work/super",flags));
 }
 bool GetInfo(const std::string& n,BlockDeviceInfo* i)const override {
  assert(n=="super"||n=="/work/super");*i=BlockDeviceInfo("super",super_size,0,0,4096);return true;
 }
 std::string GetDeviceString(const std::string& n)const override {
  assert(n=="super"||n=="/work/super");return "7:0"; // explicit dev_t string for table construction, never opened
 }
};
class NoMap final:public android::dm::IDeviceMapper {
 public:
 bool CreateDevice(const std::string& n,const DmTable& t,std::string*,const std::chrono::milliseconds&)override {
  assert(n.ends_with("_b-cow")&&t.num_targets()>0);++map_attempts;
  unsigned planned=0;
  for(const auto& [name,values]:expected){SnapshotStatus status;
   assert(status.ParseFromString(read("/work/meta/snapshots/"+name)));
   assert(status.state()==SnapshotState::CREATED&&status.using_snapuserd());
   assert(status.device_size()==values.first&&status.snapshot_size()==values.first);
   assert(status.cow_partition_size()==values.second&&status.cow_file_size()==0);
   ++planned;
  }
  assert(planned==10);printf("PLANNED checked stock sizes and COW estimates=%u\n",planned);
  printf("BOUNDARY mapping rejected %s targets=%zu\n",n.c_str(),t.num_targets());
  if(cancel_after_map)sync_failure="/work/meta/state.tmp";
  return false;
 }
 DmDeviceState GetState(const std::string&)const override{return DmDeviceState::INVALID;}
 bool LoadTableAndActivate(const std::string&,const DmTable&)override{denied();}
 bool LoadTable(const std::string&,const DmTable&)override{denied();}
 bool GetTableInfo(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetTableStatus(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetTableStatusIma(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetDmDevicePathByName(const std::string&,std::string*)override{denied();}
 bool GetDeviceString(const std::string&,std::string*)override{denied();}
 bool DeleteDeviceIfExists(const std::string&)override{return true;} // no modeled mappings exist
};
class NoImages final:public android::fiemap::IImageManager {
 public:
 android::fiemap::FiemapStatus CreateBackingImage(const std::string&,uint64_t,int,std::function<bool(uint64_t,uint64_t)>&&)override{++image_attempts;denied();}
 bool DeleteBackingImage(const std::string&)override{denied();}
 bool MapImageDevice(const std::string&,const std::chrono::milliseconds&,std::string*)override{denied();}
 bool UnmapImageDevice(const std::string&)override{denied();}
 bool BackingImageExists(const std::string&)override{return false;}
 bool IsImageMapped(const std::string&)override{return false;}
 bool MapImageWithDeviceMapper(const IPartitionOpener&,const std::string&,std::string*)override{denied();}
 bool GetMappedImageDevice(const std::string&,std::string*)override{denied();}
 bool MapAllImages(const std::function<bool(std::set<std::string>)>&)override{denied();}
 bool DisableImage(const std::string&)override{denied();}
 bool RemoveDisabledImages()override{denied();}
 std::vector<std::string> GetAllBackingImages()override{return {};}
 android::fiemap::FiemapStatus ZeroFillNewImage(const std::string&,uint64_t)override{denied();}
 bool RemoveAllImages()override{return true;}
 bool DisableAllImages()override{return true;} // empty image inventory
 bool IsImageDisabled(const std::string&)override{denied();}
};
class FileInfo final:public ISnapshotManager::IDeviceInfo {
 NoMap dm;FileOpener opener;
 public:
 std::string GetMetadataDir()const override{return "/work/meta";}
 std::string GetSlotSuffix()const override{return "_a";}
 std::string GetOtherSlotSuffix()const override{return "_b";}
 std::string GetSuperDevice(uint32_t s)const override{assert(s<2);return "/work/super";}
 const IPartitionOpener& GetPartitionOpener()const override{return opener;}
 bool IsOverlayfsSetup()const override{return scenario=="overlay";}
 bool SetBootControlMergeStatus(MergeStatus s)override{assert(s==MergeStatus::NONE);return true;} // explicit HAL result boundary
 bool SetActiveBootSlot(unsigned)override{denied();}
 bool SetSlotAsUnbootable(unsigned)override{denied();}
 bool IsSlotMarkedSuccessful(unsigned)override{denied();}
 bool IsRecovery()const override{return true;}
 bool IsTestDevice()const override{return true;}
 bool IsFirstStageInit()const override{return false;}
 std::unique_ptr<IImageManager> OpenImageManager()const override{return std::make_unique<NoImages>();}
 android::dm::IDeviceMapper& GetDeviceMapper()override{return dm;}
 bool IsTempMetadata()const override{return false;}
};
static std::string metadata_prefix(){
 android::base::unique_fd fd(open("/work/super",O_RDONLY));assert(fd>=0);
 std::string bytes(1024*1024,'\0');assert(pread(fd.get(),bytes.data(),bytes.size(),0)==ssize_t(bytes.size()));return bytes;
}
static void prepare_layout(const DeltaArchiveManifest& m,uint64_t capacity=0){
 const auto& groups=m.dynamic_partition_metadata().groups();assert(groups.size()==1);
 uint64_t occupied=0;std::set<std::string> names;
 for(const auto& g:groups)for(const auto& n:g.partition_names())names.insert(n);
 for(const auto& p:m.partitions())if(names.contains(p.partition_name()))occupied+=p.new_partition_info().size();
 assert(names.size()==10);
 for(const auto& p:m.partitions())if(names.contains(p.partition_name())){
  assert(p.has_estimate_cow_size());expected[p.partition_name()+"_b"]={p.new_partition_info().size(),(p.estimate_cow_size()+2*1024*1024+4095)&~uint64_t(4095)};
 }
 // Explicit synthetic layout, not inferred phone free space or source version.
 super_size=capacity?capacity:(scenario=="no-space"?((occupied+4*1024*1024+4095)&~uint64_t(4095)):32ULL*1024*1024*1024);
 auto b=MetadataBuilder::New(super_size,65536,2);assert(b);b->SetVirtualABDeviceFlag();
 for(const auto& g:groups){assert(b->AddGroup(g.name()+"_a",g.size()));
  for(const auto& p:m.partitions())if(names.contains(p.partition_name())){
   auto* part=b->AddPartition(p.partition_name()+"_a",g.name()+"_a",LP_PARTITION_ATTR_READONLY);
   assert(part&&b->ResizePartition(part,p.new_partition_info().size()));
  }
 }
 auto metadata=b->Export();assert(metadata);
 {android::base::unique_fd fd(open("/work/super",O_RDWR|O_CREAT|O_TRUNC,0600));assert(fd>=0&&ftruncate(fd.get(),super_size)==0);}
 FileOpener opener;assert(FlashPartitionTable(opener,"super",*metadata));
}
#ifndef OTA_ALLOCATION_LIBRARY
int main(int argc,char**argv){
 android::base::SetLogger(android::base::StderrLogger);
 assert(argc==2);scenario=argv[1];no_kernel=scenario=="no-kernel";
 IPropertyFetcher::OverrideForTesting(std::make_shared<Props>());
 DeltaArchiveManifest m;assert(m.ParseFromString(read("/work/manifest.pb")));
 prepare_layout(m);
 fs::create_directories("/work/meta/snapshots");auto manager=SnapshotManager::New(new FileInfo);
 assert(manager->BeginUpdate());
 if(scenario=="missing-estimate")for(auto& p:*m.mutable_partitions())p.clear_estimate_cow_size();
 if(scenario=="bad-cow-version")m.mutable_dynamic_partition_metadata()->set_cow_version(99);
 if(scenario=="wrong-state"){SnapshotUpdateStatus s;s.set_state(UpdateState::Unverified);write("/work/meta/state",s.SerializeAsString());}
 const auto before=metadata_prefix();
 auto result=manager->CreateUpdateSnapshots(m);
 assert(metadata_prefix()==before);
 SnapshotUpdateStatus after;assert(after.ParseFromString(read("/work/meta/state")));
 printf("OBSERVED code=%d required=%llu maps=%u\n",int(result.error_code()),(unsigned long long)result.required_size(),map_attempts);fflush(stdout);
 assert(!result&&image_attempts==0);
 assert(after.state()==(scenario=="wrong-state"?UpdateState::Unverified:UpdateState::Initiated));
 assert(map_attempts==unsigned(scenario=="map-denied"));
 if(scenario=="no-space")assert(result.error_code()==Return::ErrorCode::NO_SPACE&&result.required_size()>0);
 else assert(result.error_code()==Return::ErrorCode::ERROR);
 assert(std::distance(fs::directory_iterator("/work/meta/snapshots"),fs::directory_iterator{})==0);
 FileOpener check;auto unchanged=ReadMetadata(check,"super",0);auto target=ReadMetadata(check,"super",1);
 assert(unchanged&&target);for(const auto& p:target->partitions)assert(!GetPartitionName(p).ends_with("_b"));
 printf("PASS %s code=%d required=%llu maps=%u images=%u state=%d source_partitions=%zu\n",argv[1],int(result.error_code()),(unsigned long long)result.required_size(),map_attempts,image_attempts,int(after.state()),unchanged->partitions.size());
}

#endif
