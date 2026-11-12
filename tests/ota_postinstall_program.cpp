// Actual ARM64 PostinstallRunnerAction and Subprocess child, no real mounts.
// Match production libchrome release ABI; fixture assertions enabled below.
#define NDEBUG
#include "update_engine/payload_consumer/postinstall_runner_action.h"
#include "update_engine/common/action_processor.h"
#include "update_engine/common/fake_boot_control.h"
#include "update_engine/common/fake_hardware.h"
#include "update_engine/common/subprocess.h"
#include "update_engine/aosp/dynamic_partition_control_android.h"
#include <brillo/asynchronous_signal_handler.h>
#include <brillo/message_loops/base_message_loop.h>
#include <base/bind.h>
#include <android-base/file.h>
#undef NDEBUG
#include <cassert>
#ifdef NDEBUG
#error Fixture assertions must be enabled
#endif
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <signal.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
using namespace chromeos_update_engine;
static std::string mode;
static unsigned mounts=0, unmounts=0, readonlys=0, finishes=0, switches=0;
static bool mounted=false;
extern "C" int __real_execv(const char*, char* const[]);
extern "C" int __wrap_execv(const char* path, char* const argv[]) {
 // Explicit QEMU exec bridge: argv for postinstall itself is preserved.
 assert(std::string(path)=="/work/mount/bin/postinstall");
 assert(argv[0] && argv[1] && argv[2] && !argv[3]);
 std::vector<std::string> args={"/qemu","-L","/android","-E",
     "LD_LIBRARY_PATH=/android/system/lib64","/android/system/bin/linker64",path,argv[1],argv[2]};
 std::vector<char*> ptrs; for(auto& s:args)ptrs.push_back(s.data());ptrs.push_back(nullptr);
 return __real_execv("/qemu",ptrs.data());
}
// Link wrappers isolate exactly the device/mount boundaries of original utils.
#define WRAP_ALIAS(name, symbol, params) extern "C" bool name params __asm__("__wrap_" symbol); extern "C" bool name params
WRAP_ALIAS(is_mount, "_ZN22chromeos_update_engine5utils12IsMountpointERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE", (const std::string& p)) { assert(p=="/postinstall"||p=="/work/mount"); return mounted; }
WRAP_ALIAS(set_ro, "_ZN22chromeos_update_engine5utils22SetBlockDeviceReadOnlyERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEEb", (const std::string& p, bool ro)) { assert(p=="/work/device"&&ro);++readonlys;return true; }
WRAP_ALIAS(do_mount, "_ZN22chromeos_update_engine5utils15MountFilesystemERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEES9_mS9_S9_", (const std::string& p,const std::string& target,unsigned long,const std::string&,const std::string&)) { assert(p=="/work/device"&&target=="/work/mount");++mounts;mounted=mode!="mount-fail";return mounted; }
WRAP_ALIAS(do_unmount, "_ZN22chromeos_update_engine5utils17UnmountFilesystemERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEE", (const std::string& p)) { assert(p=="/work/mount"||p=="/postinstall");++unmounts;mounted=false;return true; }
namespace chromeos_update_engine {
class PostinstallRunnerActionTest {
 public: static void SetDir(PostinstallRunnerAction& a) { a.SetMountDir("/work/mount"); }
};
}
class Control final: public DynamicPartitionControlAndroid {
 public:
 Control():DynamicPartitionControlAndroid(0) {}
 FeatureFlag GetVirtualAbFeatureFlag() override { return FeatureFlag(FeatureFlag::Value::LAUNCH); }
 bool FinishUpdate(bool wipe) override { assert(!wipe);++finishes;return true; }
 bool UnmapAllPartitions() override { return true; }
};
class Boot final: public FakeBootControl {
 public: bool SetActiveBootSlot(Slot slot) override { assert(slot==1);++switches;return true; }
};
class Feed final: public InstallPlanAction {
 public:
 void PerformAction() override {
  InstallPlan plan; plan.source_slot=0;plan.target_slot=1;plan.switch_slot_on_reboot=true;
  plan.download_url="file:///synthetic-payload";
  InstallPlan::Partition partition;partition.name="system";partition.readonly_target_path="/work/device";
  partition.filesystem_type="ext4";partition.run_postinstall=true;
  partition.postinstall_path="bin/postinstall";partition.postinstall_optional=mode=="optional-exit7";
  plan.partitions.push_back(partition);SetOutputObject(plan);processor_->ActionComplete(this,ErrorCode::kSuccess);
 }
 std::string Type() const override { return "FixturePlan"; }
};
class Done final:public ActionProcessorDelegate {
 public: bool done=false,stopped=false;ErrorCode result=ErrorCode::kError;
 void ProcessingDone(const ActionProcessor*,ErrorCode code) override {done=true;result=code;brillo::MessageLoop::current()->BreakLoop();}
 void ProcessingStopped(const ActionProcessor*) override {stopped=true;brillo::MessageLoop::current()->BreakLoop();}
};
class Progress final: public PostinstallRunnerAction::DelegateInterface {
 public: std::vector<double> values; void ProgressUpdate(double value) override {assert(value>=0&&value<=1);values.push_back(value);}
};
static void cancel_when_ready(ActionProcessor* p) {
 if (std::filesystem::exists("/work/program-entered")) {p->StopProcessing();return;}
 brillo::MessageLoop::current()->PostDelayedTask(FROM_HERE,base::Bind(&cancel_when_ready,p),base::TimeDelta::FromMilliseconds(5));
}
int main(int argc,char**argv) {
 assert(argc==2);mode=argv[1];
 // Bound ProcessImpl's fd-close loop; no inherited real device handles exist.
 struct rlimit limit{256,256};assert(setrlimit(RLIMIT_NOFILE,&limit)==0);
 std::filesystem::create_directories("/work/mount/bin");
 assert(android::base::WriteStringToFile(mode,"/work/mode"));
 assert(android::base::WriteStringToFile("regular fixture","/work/device"));
 if(mode=="missing-program")assert(unlink("/work/mount/bin/postinstall")==0);
 brillo::BaseMessageLoop loop;loop.SetAsCurrent();brillo::AsynchronousSignalHandler signals;signals.Init();
 Subprocess subprocess;subprocess.Init(&signals);
 Boot boot;boot.SetDynamicPartitionControl(std::make_unique<Control>());FakeHardware hardware;
 Done delegate;Progress progress;
 {
  ActionProcessor processor;processor.set_delegate(&delegate);
  auto feed=std::make_unique<Feed>();auto action=std::make_unique<PostinstallRunnerAction>(&boot,&hardware);
  PostinstallRunnerActionTest::SetDir(*action);action->set_delegate(&progress);
  BondActions(feed.get(),action.get());processor.EnqueueAction(std::move(feed));processor.EnqueueAction(std::move(action));
  if(mode=="cancel")loop.PostDelayedTask(FROM_HERE,base::Bind(&cancel_when_ready,&processor),base::TimeDelta::FromMilliseconds(5));
  processor.StartProcessing();if(!delegate.done&&!delegate.stopped)loop.Run();
 }
 const bool ok=mode=="normal"||mode=="optional-exit7";
 ErrorCode wanted=ok?ErrorCode::kSuccess:mode=="mount-fail"?ErrorCode::kPostInstallMountError:
   mode=="exit3"?ErrorCode::kPostinstallBootedFromFirmwareB:mode=="exit4"?ErrorCode::kPostinstallFirmwareRONotUpdatable:ErrorCode::kPostinstallRunnerError;
 printf("RESULT %s done=%d stopped=%d code=%d finishes=%u switches=%u mounts=%u unmounts=%u progress=%zu\n",mode.c_str(),delegate.done,delegate.stopped,int(delegate.result),finishes,switches,mounts,unmounts,progress.values.size());fflush(stdout);
 if(mode=="cancel")assert(delegate.stopped&&!delegate.done);else assert(delegate.done&&delegate.result==wanted);
 assert(finishes==unsigned(ok)&&switches==unsigned(ok));assert(mounts==1&&readonlys==1&&!mounted);
 assert(unmounts==unsigned(mode!="mount-fail"));
 const bool entered=mode!="mount-fail"&&mode!="missing-program";
 assert(std::filesystem::exists("/work/program-entered")==entered);
 if(entered&&mode!="cancel"){
   assert(std::find(progress.values.begin(),progress.values.end(),0.25)!=progress.values.end());
   assert(std::find(progress.values.begin(),progress.values.end(),0.75)!=progress.values.end());
 }
 if(entered){std::string text;assert(android::base::ReadFileToString("/work/program-entered",&text));assert(text=="ARM64 slot=1 progress_fd=3\n");}
 // Every real child must have been reaped, including cancellation.
 int status;errno=0;assert(waitpid(-1,&status,WNOHANG)==-1&&errno==ECHILD);
 puts("PASS actual ARM64 child and original parent lifecycle; mount/HAL boundaries explicit");
}
