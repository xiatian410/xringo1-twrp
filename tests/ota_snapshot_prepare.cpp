// Real controller -> SnapshotManager allocation -> cancellation -> direct LP prep.
#include "update_engine/aosp/dynamic_partition_control_android.h"
#define OTA_ALLOCATION_LIBRARY
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include "ota_snapshot_allocate.cpp"
#pragma clang diagnostic pop
static unsigned direct_unmaps=0,stores=0;
struct MountedToken final:AutoDevice{MountedToken():AutoDevice("fixture-mounted") {}};
namespace chromeos_update_engine {
class DynamicPartitionControlAndroidTest {
 public:static void Inject(DynamicPartitionControlAndroid& c){
 c.snapshot_=SnapshotManager::New(new FileInfo);
 c.metadata_device_=std::make_unique<MountedToken>();
 }
};
}
class FileControl final:public DynamicPartitionControlAndroid {
 FileOpener opener;
 public:
 FileControl():DynamicPartitionControlAndroid(0){DynamicPartitionControlAndroidTest::Inject(*this);}
 FeatureFlag GetDynamicPartitionsFeatureFlag()override{return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 FeatureFlag GetVirtualAbFeatureFlag()override{return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 bool GetDeviceDir(std::string* p)override{*p="/work";return true;}
 std::string GetSuperPartitionName(uint32_t s)override{assert(s<2);return "super";}
 bool IsRecovery()override{return true;}
 bool EraseSystemOtherAvbFooter(uint32_t a,uint32_t b)override{assert(a==0&&b==1);return true;} // no AVB effect
 std::unique_ptr<MetadataBuilder> LoadMetadataBuilder(const std::string& p,uint32_t s)override {
  assert(p=="/work/super"&&s==0);return MetadataBuilder::New(opener,p,s);
 }
 std::unique_ptr<MetadataBuilder> LoadMetadataBuilder(const std::string& p,uint32_t a,uint32_t b)override {
  assert(p=="/work/super"&&a==0&&b==1);return MetadataBuilder::NewForUpdate(opener,p,a,b);
 }
 bool UnmapPartitionOnDeviceMapper(const std::string& n)override {
  assert(n.ends_with("_a")||n.ends_with("_b"));++direct_unmaps;
  SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state")));
  assert(state.state()==UpdateState::None); // cancellation must precede direct preparation
  return scenario!="unmap-error";
 }
 bool StoreMetadata(const std::string& p,MetadataBuilder* b,uint32_t s)override {
  assert(p=="/work/super"&&s==1);++stores;
  auto metadata=b->Export();assert(metadata);
  if(scenario=="store-error")return false;
  return UpdatePartitionTable(opener,p,*metadata,s);
 }
};
int main(int argc,char**argv){
 android::base::SetLogger(android::base::StderrLogger);assert(argc==2);scenario=argv[1];
 cancel_after_map=scenario=="cancel-sync-error";
 IPropertyFetcher::OverrideForTesting(std::make_shared<Props>());
 DeltaArchiveManifest m;assert(m.ParseFromString(read("/work/manifest.pb")));
 bool tight=scenario=="no-space";
 // Still synthetic. Keep group limit within super so allocation, not group check, fails.
 uint64_t capacity=tight?m.dynamic_partition_metadata().groups(0).size()+4*1024*1024:0;
 prepare_layout(m,capacity);fs::create_directories("/work/meta/snapshots");
 const auto before=metadata_prefix();
 FileOpener baseline_opener;auto baseline=ReadMetadata(baseline_opener,"super",0);assert(baseline&&WriteToImageFile("/work/source.before",*baseline));
 FileControl control;uint64_t required=99;ErrorCode error=ErrorCode::kSuccess;
 bool ok=control.PreparePartitionsForUpdate(0,1,m,true,&required,&error);
 bool expected_ok=scenario=="no-space"||scenario=="map-denied";
 printf("OBSERVED %s ok=%d required=%llu maps=%u unmaps=%u stores=%u sync_failures=%u\n",argv[1],ok,(unsigned long long)required,map_attempts,direct_unmaps,stores,sync_injections);fflush(stdout);
 assert(ok==expected_ok&&image_attempts==0);
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state")));
 assert(state.state()==(cancel_after_map?UpdateState::Initiated:UpdateState::None));
 assert(map_attempts==unsigned(!tight));
 assert(stores==unsigned(expected_ok||scenario=="store-error"));
 assert(direct_unmaps==(cancel_after_map?0u:scenario=="unmap-error"?1u:10u));
 assert(sync_injections==unsigned(cancel_after_map));
 assert(required==0);
 assert(std::distance(fs::directory_iterator("/work/meta/snapshots"),fs::directory_iterator{})==0);
 FileOpener opener;auto source=ReadMetadata(opener,"super",0);auto target=ReadMetadata(opener,"super",1);
 assert(source&&target&&source->partitions.size()==10&&target->partitions.size()==10);
 assert(WriteToImageFile("/work/source.after",*source));assert(read("/work/source.before")==read("/work/source.after"));
 if(!expected_ok)assert(metadata_prefix()==before);
 uint64_t overlap_sectors=0;
 if(expected_ok)for(const auto& a:source->extents)for(const auto& b:target->extents){
  if(a.target_type!=LP_TARGET_TYPE_LINEAR||b.target_type!=LP_TARGET_TYPE_LINEAR||a.target_source!=b.target_source)continue;
  auto start=std::max(a.target_data,b.target_data),end=std::min(a.target_data+a.num_sectors,b.target_data+b.num_sectors);
  if(end>start)overlap_sectors+=end-start;
 }
 if(expected_ok)assert(overlap_sectors>0);
 printf("DIRECT layout overlap_sectors=%llu source_metadata_preserved=1\n",(unsigned long long)overlap_sectors);
 auto src=MetadataBuilder::New(*source);auto dst=MetadataBuilder::New(*target);assert(src&&dst);
 for(const auto& [name,values]:expected){
  const auto a=name.substr(0,name.size()-2)+"_a";
  assert(src->FindPartition(a)&&src->FindPartition(a)->size()==values.first);
  auto part=dst->FindPartition(expected_ok?name:a);assert(part&&part->size()==values.first);
  if(expected_ok)assert(!dst->FindPartition(a));
 }
 printf("PASS %s result=%d source_metadata_unchanged=1 target_published=%d state=%d\n",argv[1],ok,expected_ok,int(state.state()));
}
