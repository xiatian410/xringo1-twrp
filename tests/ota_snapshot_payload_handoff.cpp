// Original allocation -> controller writer -> VABC operations on private files.
// The runner extracts existing initialization support, without changing it.
#include "update_engine/aosp/dynamic_partition_control_android.h"
#include "update_engine/payload_consumer/vabc_partition_writer.h"
#include "libsnapshot_cow/snapshot_reader.h"
#include <xz.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmacro-redefined"
#include "snapshot_init_support.inc"
#pragma clang diagnostic pop

// Unlike the initialization-only mapper, remapping must preserve COW bytes.
class PersistentMapper final : public android::dm::IDeviceMapper {
 public:
 bool CreateDevice(const std::string& name,const DmTable& table,std::string* path,const std::chrono::milliseconds&) override {
  assert(name.ends_with("_b-cow")||name.ends_with("_b-base"));
  const auto part=name.substr(0,name.size()-(name.ends_with("-cow")?4:5));
  assert(expected.contains(part)&&table.valid()&&!table.readonly());
  const auto size=name.ends_with("-cow")?expected.at(part).second:expected.at(part).first;
  assert(table.num_sectors()*512==size&&!active_views.contains(name));
  auto target="/work/cows/"+name;
  android::base::unique_fd fd(open(target.c_str(),O_CREAT|O_EXCL|O_RDWR,0600));
  if(fd<0){assert(errno==EEXIST);fd.reset(open(target.c_str(),O_RDWR));struct stat st{};assert(fd>=0&&fstat(fd.get(),&st)==0&&uint64_t(st.st_size)==size);}
  else assert(ftruncate(fd.get(),size)==0);
  ++created;file_views[name]=target;active_views.insert(name);*path=target;return true;
 }
 DmDeviceState GetState(const std::string& n)const override{return active_views.contains(n)?DmDeviceState::ACTIVE:DmDeviceState::INVALID;}
 bool LoadTableAndActivate(const std::string&,const DmTable&)override{denied();}
 bool LoadTable(const std::string&,const DmTable&)override{denied();}
 bool GetTableInfo(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetTableStatus(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetTableStatusIma(const std::string&,std::vector<TargetInfo>*)override{denied();}
 bool GetDmDevicePathByName(const std::string& n,std::string* p)override{if(!active_views.contains(n))return false;*p=file_views.at(n);return true;}
 bool GetDeviceString(const std::string& n,std::string* p)override{assert(active_views.contains(n));*p="7:0";return true;}
 bool DeleteDeviceIfExists(const std::string& n)override{active_views.erase(n);return true;}
};
static PersistentMapper mapper;
// Bionic realpath depends on procfs, absent in the private chroot. Only the
// already known regular super file is accepted; no arbitrary path succeeds.
extern "C" bool file_realpath(const std::string&,std::string*) __asm__("__wrap__ZN7android4base8RealpathERKNSt3__112basic_stringIcNS1_11char_traitsIcEENS1_9allocatorIcEEEEPS7_");
extern "C" bool file_realpath(const std::string& path,std::string* result){
 assert(path=="/work/super");struct stat st{};assert(lstat(path.c_str(),&st)==0&&S_ISREG(st.st_mode));*result=path;return true;
}
class HandoffInfo final : public ISnapshotManager::IDeviceInfo {
 FileOpener opener;
 public:
 std::string GetMetadataDir()const override{return "/work/meta";}
 std::string GetSlotSuffix()const override{return "_a";}
 std::string GetOtherSlotSuffix()const override{return "_b";}
 std::string GetSuperDevice(uint32_t s)const override{assert(s<2);return "/work/super";}
 const IPartitionOpener& GetPartitionOpener()const override{return opener;}
 bool IsOverlayfsSetup()const override{return false;}
 bool SetBootControlMergeStatus(MergeStatus s)override{assert(s==MergeStatus::NONE||s==MergeStatus::SNAPSHOTTED);if(s==MergeStatus::SNAPSHOTTED)++hal_completed;return true;}
 bool SetActiveBootSlot(unsigned)override{denied();}
 bool SetSlotAsUnbootable(unsigned)override{denied();}
 bool IsSlotMarkedSuccessful(unsigned)override{denied();}
 bool IsRecovery()const override{return true;}
 bool IsTestDevice()const override{return true;}
 bool IsFirstStageInit()const override{return false;}
 std::unique_ptr<IImageManager> OpenImageManager()const override{return std::make_unique<FileImages>();}
 android::dm::IDeviceMapper& GetDeviceMapper()override{return mapper;}
 bool IsTempMetadata()const override{return false;}
};
// CreateLogicalPartition otherwise uses the global real kernel mapper. Preserve
// original defaults/table construction, then explicitly delegate the DM boundary.
extern "C" bool file_base(CreateLogicalPartitionParams,std::string*) __asm__("__wrap__ZN7android6fs_mgr22CreateLogicalPartitionENS0_28CreateLogicalPartitionParamsEPNSt3__112basic_stringIcNS2_11char_traitsIcEENS2_9allocatorIcEEEE");
extern "C" bool file_base(CreateLogicalPartitionParams params,std::string* path){
 CreateLogicalPartitionParams::OwnedData owned;assert(params.InitDefaults(&owned));
 DmTable table;assert(CreateDmTable(params,&table));
 return mapper.CreateDevice(params.GetDeviceName(),table,path,params.timeout_ms);
}
namespace chromeos_update_engine {
class DynamicPartitionControlAndroidTest {
 public:static void Inject(DynamicPartitionControlAndroid& c){
  c.snapshot_=SnapshotManager::New(new HandoffInfo);c.target_slot_=1;
 }
};
}
class HandoffControl final : public DynamicPartitionControlAndroid {
 public:
 HandoffControl():DynamicPartitionControlAndroid(0){DynamicPartitionControlAndroidTest::Inject(*this);}
 bool GetDeviceDir(std::string* p)override{*p="/work";return true;}
 std::string GetSuperPartitionName(uint32_t s)override{assert(s==1);return "super";}
};
static void verify(const PartitionUpdate& update,unsigned n){
 auto reader=std::make_unique<CowReader>();
 assert(reader->Parse(android::base::unique_fd(open("/work/cows/mi_ext_b-cow",O_RDONLY)),n));
 CompressedSnapshotReader view(std::move(reader),std::nullopt,update.new_partition_info().size());
 std::string wanted=read("/work/expected.bin"),actual;
 uint64_t pos=0;
 for(unsigned i=0;i<n;i++)for(const auto& e:update.operations(i).dst_extents()){
  auto length=e.num_blocks()*4096;std::string bytes(length,'\0');
  assert(view.Seek(e.start_block()*4096,SEEK_SET)==int64_t(e.start_block()*4096));
  assert(view.Read(bytes.data(),bytes.size())==ssize_t(bytes.size()));
  assert(wanted.substr(pos,length)==bytes);pos+=length;actual+=bytes;
 }
 assert(view.Close());write("/work/readback.bin",actual);
}
int main(int argc,char**argv){
 android::base::SetLogger(android::base::StderrLogger);assert(argc==2);scenario=argv[1];xz_crc32_init();
 IPropertyFetcher::OverrideForTesting(std::make_shared<Props>());
 DeltaArchiveManifest manifest;assert(manifest.ParseFromString(read("/work/manifest.pb")));
 prepare_layout(manifest);fs::create_directories("/work/meta/snapshots");fs::create_directory("/work/cows");
 const auto before=metadata_prefix();
 auto manager=SnapshotManager::New(new HandoffInfo);assert(manager->BeginUpdate());assert(manager->CreateUpdateSnapshots(manifest));
 assert(created==10&&active_views.empty()&&metadata_prefix()!=before);
 const auto it=std::find_if(manifest.partitions().begin(),manifest.partitions().end(),[](const auto& p){return p.partition_name()=="mi_ext";});assert(it!=manifest.partitions().end());
 const auto& update=*it;assert(update.operations_size()>2);
 InstallPlan plan;plan.source_slot=0;plan.target_slot=1;plan.write_verity=false;
 auto& part=plan.partitions.emplace_back();part.name="mi_ext";part.block_size=4096;part.target_size=update.new_partition_info().size();
 HandoffControl control;
 if(scenario=="corrupt-header"){
  android::base::unique_fd fd(open("/work/cows/mi_ext_b-cow",O_RDWR));uint64_t bad=0;assert(fd>=0&&pwrite(fd.get(),&bad,sizeof(bad),0)==sizeof(bad));
  VABCPartitionWriter writer(update,part,&control,4096);assert(!writer.Init(&plan,false,0));assert(!writer.FinishedInstallOps());assert(writer.Close()==0);
  assert(manager->UnmapUpdateSnapshot("mi_ext_b")&&active_views.empty());
  SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state"))&&state.state()==UpdateState::Initiated&&hal_completed==0);
  puts("PASS corrupt-header init_rejected=1 unmap=1 state=1 completed=0");return 0;
 }
 unsigned completed=0;
 {
  VABCPartitionWriter writer(update,part,&control,4096);assert(writer.Init(&plan,false,0));
  auto input=read("/work/input0.bin");assert(writer.PerformReplaceOperation(update.operations(0),input.data(),input.size()));writer.CheckpointUpdateProgress(1);++completed;
  if(scenario=="normal"){
   input=read("/work/input1.bin");assert(writer.PerformReplaceOperation(update.operations(1),input.data(),input.size()));writer.CheckpointUpdateProgress(2);++completed;
  }
  assert(writer.Close()==0);
 }
 assert(manager->UnmapUpdateSnapshot("mi_ext_b")&&active_views.empty());verify(update,completed);
 if(scenario=="resume"){
  // New objects and the same persisted files; label1 must survive remapping.
  manager.reset();manager=SnapshotManager::New(new HandoffInfo);plan.is_resume=true;HandoffControl resumed;
  VABCPartitionWriter writer(update,part,&resumed,4096);assert(writer.Init(&plan,false,1));
  auto input=read("/work/input1.bin");assert(writer.PerformReplaceOperation(update.operations(1),input.data(),input.size()));writer.CheckpointUpdateProgress(2);++completed;assert(writer.Close()==0);
  assert(manager->UnmapUpdateSnapshot("mi_ext_b")&&active_views.empty());verify(update,completed);
 }
 assert(completed==2&&hal_completed==0);
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state"))&&state.state()==UpdateState::Initiated);
 // Only two of this partition's operations ran; never publish completion.
 printf("PASS %s allocated=10 stock_operations=2 bytes=4194304 unmap=1 state=1 completed=0\n",argv[1]);
}
