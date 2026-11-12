// Intact ARM64 controller; metadata/storage/device effects are denied fixtures.
#include "update_engine/aosp/dynamic_partition_control_android.h"
#include <libsnapshot/snapshot_stub.h>
#include <cassert>
#ifdef NDEBUG
#error Fixture assertions must be enabled
#endif
#include <cstdio>
#include <string>
using namespace chromeos_update_engine;
using namespace android::snapshot;
static unsigned maps=0,mounts=0,directs=0,compression_queries=0;
static bool direct_ok=true,recovery=true,map_ok=false;
class NoMetadata final : public SnapshotManagerStub {
 public:
 std::unique_ptr<AutoDevice> EnsureMetadataMounted() override {++mounts;return nullptr;}
 bool UpdateUsesSnapuserd() override {++compression_queries;return false;}
 bool MapAllSnapshots(const std::chrono::milliseconds&) override {++maps;return map_ok;}
};
namespace chromeos_update_engine {
// Existing production friend; injection only sets ISnapshotManager boundary.
class DynamicPartitionControlAndroidTest {
 public:
 static void Inject(DynamicPartitionControlAndroid&d){d.snapshot_=std::make_unique<NoMetadata>();}
};
}
class Control final : public DynamicPartitionControlAndroid {
 public:
 Control():DynamicPartitionControlAndroid(0){DynamicPartitionControlAndroidTest::Inject(*this);}
 FeatureFlag GetDynamicPartitionsFeatureFlag() override {return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 FeatureFlag GetVirtualAbFeatureFlag() override {return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 protected:
 bool IsRecovery() override {return recovery;}
 bool EraseSystemOtherAvbFooter(uint32_t,uint32_t) override {return true;} // explicit no-op boundary; no AVB call
 bool PrepareDynamicPartitionsForUpdate(uint32_t a,uint32_t b,const DeltaArchiveManifest&,bool /*remove*/) override {
  assert(a==0&&b==1);++directs;return direct_ok;
 }
};
int main(int argc,char**argv){
 assert(argc==2);std::string name=argv[1];
 direct_ok=name!="direct-failure";recovery=name!="android-metadata-failure";map_ok=name=="snapshot-map-success";
 Control c;DeltaArchiveManifest manifest;auto*dm=manifest.mutable_dynamic_partition_metadata();dm->set_snapshot_enabled(name!="non-snapshot-target");dm->add_groups()->set_name("group");
 bool update=!name.starts_with("snapshot-map-");uint64_t required=99;ErrorCode error=ErrorCode::kSuccess;
 bool prepared=c.PreparePartitionsForUpdate(0,1,manifest,update,&required,&error);
 const bool expect=direct_ok&&recovery;assert(prepared==expect);
 if(prepared){
  // Actual verifier/writer callers gate snapshot mapping on compression mode.
  // Missing metadata is a boundary here, so it reports no active snapuserd.
  assert(!c.UpdateUsesSnapshotCompression());
  // Diagnostic direct call: snapshot-capable target alone does not imply
  // snapshots actually exist after fallback. This is NOT the caller path.
  bool mapped=c.MapAllPartitions();
  assert(mapped==(name=="snapshot-map-success"||name=="non-snapshot-target"));
  assert(c.FinishUpdate(false));
 }
 assert(mounts==1);assert(directs==unsigned(update&&recovery));assert(maps==unsigned(prepared&&name!="non-snapshot-target"));assert(compression_queries==unsigned(prepared));
 printf("PASS %s prepared=%d direct=%u snapshot_maps=%u metadata_mounts=%u\n",argv[1],prepared,directs,maps,mounts);
}
