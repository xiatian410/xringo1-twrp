// Original controller cleanup aggregation; mapping operations are explicit doubles.
#include <libsnapshot/snapshot_stub.h>
#include "update_engine/aosp/dynamic_partition_control_android.h"
#include <cassert>
#include <cstdio>
#include <set>
#include <string>
#include <vector>
using namespace chromeos_update_engine;
using namespace android::snapshot;
static bool snapshot_ok=true;
static unsigned snapshot_calls=0;
class Snapshots final : public SnapshotManagerStub {
 public:
 bool UnmapAllSnapshots() override {++snapshot_calls;return snapshot_ok;}
};
struct Token final : AutoDevice {Token():AutoDevice("fixture-mounted") {}};
namespace chromeos_update_engine {
class DynamicPartitionControlAndroidTest {
 public:
 static void Seed(DynamicPartitionControlAndroid& c,bool metadata,const std::set<std::string>& names) {
  c.snapshot_=std::make_unique<Snapshots>();c.mapped_devices_=names;
  if(metadata)c.metadata_device_=std::make_unique<Token>();
 }
 static void Erase(DynamicPartitionControlAndroid& c,const std::string& name){c.mapped_devices_.erase(name);}
 static std::set<std::string> Remaining(DynamicPartitionControlAndroid& c){return c.mapped_devices_;}
 static void Clear(DynamicPartitionControlAndroid& c){c.mapped_devices_.clear();}
};
}
class Control final : public DynamicPartitionControlAndroid {
 public:
 bool vab=true;std::string fail;std::vector<std::string> attempts;
 Control():DynamicPartitionControlAndroid(0) {}
 FeatureFlag GetVirtualAbFeatureFlag() override {return FeatureFlag(vab?FeatureFlag::Value::LAUNCH:FeatureFlag::Value::NONE);}
 protected:
 bool IsRecovery() override {return true;}
 bool UnmapPartitionOnDeviceMapper(const std::string& name) override {
  attempts.push_back(name);if(name==fail)return false;
  DynamicPartitionControlAndroidTest::Erase(*this,name);return true;
 }
};
int main(int argc,char** argv){
 assert(argc==2);std::string name=argv[1];Control c;
 c.vab=name!="non-vab";
 bool metadata=name!="no-metadata"&&c.vab;
 snapshot_ok=name!="snapshot-fail"&&name!="combined-fail";
 if(name=="logical-fail"||name=="combined-fail")c.fail="system_b";
 std::set<std::string> initial={"system_b","vendor_b","system_a_ota"};
 if(name=="empty")initial.clear();
 if(name=="source-only")initial={"system_a_ota"};
 DynamicPartitionControlAndroidTest::Seed(c,metadata,initial);
 bool result=c.UnmapAllPartitions();
 auto remaining=DynamicPartitionControlAndroidTest::Remaining(c);
 // Clear before assertions: base destructor must never reach actual device mapper.
 DynamicPartitionControlAndroidTest::Clear(c);
 bool expected=snapshot_ok&&c.fail.empty();
 printf("name=%s result=%d expected=%d snapshots=%u attempts=%zu remaining=%zu\n",name.c_str(),result,expected,snapshot_calls,c.attempts.size(),remaining.size());fflush(stdout);
 assert(result==expected);
 assert(snapshot_calls==unsigned(metadata));
 std::vector<std::string> attempts;
 if(name!="empty"&&name!="source-only")attempts={"system_b","vendor_b"};
 assert(c.attempts==attempts);
 std::set<std::string> wanted;
 if(name!="empty")wanted.insert("system_a_ota");
 if(!c.fail.empty())wanted.insert(c.fail);
 assert(remaining==wanted);
 puts("PASS original unmap aggregation; snapshot/logical effects are doubles");
}
