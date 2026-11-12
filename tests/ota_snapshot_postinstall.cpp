// Reuse deny-all hardware boundaries and actual fsync injection from leaf scope.
#define main snapshot_leaf_main
#include "ota_snapshot_finish.cpp"
#undef main
#include "update_engine/aosp/dynamic_partition_control_android.h"
#include "update_engine/common/action_processor.h"
#include "update_engine/common/fake_boot_control.h"
#include "update_engine/common/fake_hardware.h"
#include "update_engine/payload_consumer/postinstall_runner_action.h"
#include <brillo/message_loops/base_message_loop.h>
using namespace chromeos_update_engine;
static unsigned finishes = 0, switches = 0;
static bool slot_ok = true;
static std::vector<std::string> events;
struct MetadataToken final : AutoDevice {
 MetadataToken() : AutoDevice("fixture-already-mounted") {}
};
namespace chromeos_update_engine {
// Existing production friend sets only dependencies and metadata-mount token.
class DynamicPartitionControlAndroidTest {
 public:
 static void Inject(DynamicPartitionControlAndroid& control) {
   control.snapshot_ = SnapshotManager::New(new Info);
   control.metadata_device_ = std::make_unique<MetadataToken>();
 }
};
}
class Control final : public DynamicPartitionControlAndroid {
 public:
 Control() : DynamicPartitionControlAndroid(0) { DynamicPartitionControlAndroidTest::Inject(*this); }
 FeatureFlag GetVirtualAbFeatureFlag() override { return FeatureFlag(FeatureFlag::Value::LAUNCH); }
 bool FinishUpdate(bool wipe) override {
   ++finishes; events.push_back("finish");
   return DynamicPartitionControlAndroid::FinishUpdate(wipe);
 }
 protected:
 bool IsRecovery() override { return true; }
};
class Boot final : public FakeBootControl {
 public:
 bool SetActiveBootSlot(Slot slot) override {
   assert(slot == 1); ++switches; events.push_back("slot"); return slot_ok;
 }
};
class Feed final : public InstallPlanAction {
 public:
 void PerformAction() override {
   InstallPlan plan; plan.source_slot = 0; plan.target_slot = 1;
   plan.switch_slot_on_reboot = true;
   // Empty URL follows original no-script path; real postinstall scripts untested.
   SetOutputObject(plan); processor_->ActionComplete(this, ErrorCode::kSuccess);
 }
 std::string Type() const override { return "FixturePlan"; }
};
class Done final : public ActionProcessorDelegate {
 public:
 bool done = false; ErrorCode result = ErrorCode::kError;
 void ProcessingDone(const ActionProcessor*, ErrorCode code) override {
   done = true; result = code; brillo::MessageLoop::current()->BreakLoop();
 }
};
static ErrorCode run(Boot& boot) {
 FakeHardware hardware; // Explicit no-op hardware boundary; no vbmeta/device writes.
 brillo::BaseMessageLoop loop; loop.SetAsCurrent();
 ActionProcessor processor; Done delegate; processor.set_delegate(&delegate);
 auto feed = std::make_unique<Feed>();
 auto postinstall = std::make_unique<PostinstallRunnerAction>(&boot, &hardware);
 BondActions(feed.get(), postinstall.get());
 processor.EnqueueAction(std::move(feed)); processor.EnqueueAction(std::move(postinstall));
 processor.StartProcessing(); if (!delegate.done) loop.Run();
 assert(delegate.done); return delegate.result;
}
static SnapshotUpdateStatus status() {
 SnapshotUpdateStatus s; assert(s.ParseFromString(read("/work/meta/state"))); return s;
}
int main(int argc, char** argv) {
 assert(argc == 2); std::string name = argv[1];
 fs::create_directories("/work/meta/snapshots");
 SnapshotUpdateStatus initial; initial.set_state(UpdateState::Initiated);
 initial.set_using_snapuserd(true); initial.set_userspace_snapshots(true);
 initial.set_source_build_fingerprint("synthetic-source");
 write("/work/meta/state", initial.SerializeAsString());
 SnapshotStatus snapshot; snapshot.set_name("system_b"); snapshot.set_using_snapuserd(true);
 write("/work/meta/snapshots/system_b", snapshot.SerializeAsString());
 if (name == "boot-sync-retry") sync_failure = "/work/meta/snapshot-boot.tmp";
 if (name == "state-sync-retry") sync_failure = "/work/meta/state.tmp";
 if (name == "state-open-retry") fs::create_directory("/work/meta/state.tmp");
 if (name == "merge-status-retry") merge_ok = false;
 if (name == "slot-retry") slot_ok = false;
 const bool success = name == "normal";
 {
   Boot boot; boot.SetDynamicPartitionControl(std::make_unique<Control>());
   ErrorCode code = run(boot);
   printf("FIRST name=%s code=%d finishes=%u switches=%u merges=%u sync_errors=%u\n",
     name.c_str(), int(code), finishes, switches, merge_calls, sync_injections); fflush(stdout);
   assert(code == (success ? ErrorCode::kSuccess : ErrorCode::kPostinstallRunnerError));
   assert(finishes == 1);
   assert(switches == unsigned(success || name == "slot-retry"));
   const bool published = success || name == "slot-retry";
   assert(status().state() == (published ? UpdateState::Unverified : UpdateState::Initiated));
   if (!success) assert(events == (name == "slot-retry" ? std::vector<std::string>{"finish", "slot"} : std::vector<std::string>{"finish"}));
 }
 if (!success) {
   // Recreate control and manager with actual persisted files, not seeded state.
   sync_failure.clear(); merge_ok = true; slot_ok = true;
   if (name == "state-open-retry") assert(fs::remove("/work/meta/state.tmp"));
   unsigned prior_merges = merge_calls, prior_switches = switches;
   Boot boot; boot.SetDynamicPartitionControl(std::make_unique<Control>());
   ErrorCode code = run(boot);
   assert(code == ErrorCode::kSuccess && finishes == 2 && switches == prior_switches + 1);
   assert(merge_calls == prior_merges + unsigned(name != "slot-retry"));
   assert(events[events.size()-2] == "finish" && events.back() == "slot");
   printf("RETRY code=%d finishes=%u switches=%u merges=%u reused_state=1\n", int(code), finishes, switches, merge_calls);
 }
 initial.set_state(UpdateState::Unverified);
 assert(status().SerializeAsString() == initial.SerializeAsString());
 assert(read("/work/meta/snapshot-boot") == "_a");
 assert(!fs::exists("/work/meta/rollback-indicator") && !fs::exists("/work/meta/allow-forward-merge"));
 assert(sync_injections == unsigned(name == "boot-sync-retry" || name == "state-sync-retry"));
 puts("PASS actual postinstall -> control -> SnapshotManager; device effects denied");
}
