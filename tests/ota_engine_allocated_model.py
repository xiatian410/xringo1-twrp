"""Replace seeded allocation with original controller/SnapshotManager/COW flow.

Reuses explicit private-file mapper and postinstall models. No physical mapping,
mount, AVB effect, actual source LP, scratch/daemon, boot or merge is claimed.
"""
from pathlib import Path

from ota_vabc_session import ROOT
from zip_stock_support import sha
from ota_engine_finish_model import extend as finish_extend


def prepare(work, sources):
    for name in ['tests/ota_engine_allocated_model.py', 'tests/ota_snapshot_payload_handoff.cpp',
                 'tests/ota_snapshot_initialize.cpp', 'tests/ota_snapshot_allocate.cpp',
                 'tests/ota_snapshot_finish.cpp']:
        path = ROOT / name
        sources[str(path)] = sha(path)
    support = (ROOT / 'tests/ota_snapshot_initialize.cpp').read_text().split('int main(int argc,char**argv){', 1)[0]
    (work / 'snapshot_init_support.inc').write_text(support)


def extend(adapter, sources):
    # Keep original mount/readonly/script/slot models; remove the old seeded
    # SnapshotManager prefix entirely and supply actual allocation instead.
    adapter = finish_extend(adapter, sources)
    marker = '// Unmodified full stock payload streamed through original ARM64 engine.'
    assert adapter.count(marker) == 1
    adapter = marker + adapter.split(marker, 1)[1]
    handoff = (ROOT / 'tests/ota_snapshot_payload_handoff.cpp').read_text().split('static void verify(', 1)[0]
    assert 'class HandoffControl final' in handoff
    handoff = handoff.replace('namespace chromeos_update_engine {\nclass DynamicPartitionControlAndroidTest',
        'struct AllocatedToken final:AutoDevice {AllocatedToken():AutoDevice("model-already-mounted") {}};\n'
        'namespace chromeos_update_engine {\nclass DynamicPartitionControlAndroidTest')
    handoff = handoff.replace('c.snapshot_=SnapshotManager::New(new HandoffInfo);c.target_slot_=1;',
        'c.snapshot_=SnapshotManager::New(new HandoffInfo);c.target_slot_=1;'
        'c.metadata_device_=std::make_unique<AllocatedToken>();')
    handoff = handoff.replace('public:static void Inject',
        'public:static bool Unmap(DynamicPartitionControlAndroid& c,const std::string& n){'
        'return c.snapshot_->UnmapUpdateSnapshot(n+"_b");} static void Inject')
    handoff = handoff.replace('assert(s==1);return "super";', 'assert(s<2);return "super";')
    old = 'HandoffControl():DynamicPartitionControlAndroid(0){DynamicPartitionControlAndroidTest::Inject(*this);}'
    assert old in handoff
    handoff = handoff.replace(old, old + r'''
 FeatureFlag GetDynamicPartitionsFeatureFlag()override{return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 FeatureFlag GetVirtualAbFeatureFlag()override{return FeatureFlag(FeatureFlag::Value::LAUNCH);}
 bool IsRecovery()override{return true;}
 bool EraseSystemOtherAvbFooter(uint32_t a,uint32_t b)override{assert(a==0&&b==1);return true;} // explicit no AVB effect
 std::unique_ptr<MetadataBuilder> LoadMetadataBuilder(const std::string& p,uint32_t s)override{
  assert(p=="/work/super"&&s==0);FileOpener opener;return MetadataBuilder::New(opener,p,s);
 }
 bool UnmapWritten(const std::string& n){return DynamicPartitionControlAndroidTest::Unmap(*this,n);}
''')
    handoff += r'''
static std::unique_ptr<HandoffControl> allocated_control;
static void model_prepare_allocated(const DeltaArchiveManifest& manifest){
 assert(!allocated_control);IPropertyFetcher::OverrideForTesting(std::make_shared<Props>());
 prepare_layout(manifest);fs::create_directories("/work/meta/snapshots");fs::create_directory("/work/cows");
 const auto before=metadata_prefix();allocated_control=std::make_unique<HandoffControl>();
 uint64_t required=99;ErrorCode error=ErrorCode::kSuccess;
 bool ok=allocated_control->PreparePartitionsForUpdate(0,1,manifest,true,&required,&error);
 assert(ok&&required==0&&created==10&&active_views.empty()&&metadata_prefix()!=before);
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state"))&&state.state()==UpdateState::Initiated);
 assert(std::distance(fs::directory_iterator("/work/meta/snapshots"),fs::directory_iterator{})==10);
 puts("MODEL actual controller allocation initialized=10 state=1 seeded=0");fflush(stdout);
}
static bool model_finish(bool wipe){
 assert(!wipe&&allocated_control);bool ok=allocated_control->FinishUpdate(wipe);
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state")));
 assert(ok&&state.state()==UpdateState::Unverified&&hal_completed==1);
 assert(read("/work/meta/snapshot-boot")=="_a");
 printf("MODEL actual FinishedSnapshotWrites result=%d state=%d merges=%u\n",ok,int(state.state()),hal_completed);fflush(stdout);return ok;
}
static void model_slot(){
 SnapshotUpdateStatus state;assert(state.ParseFromString(read("/work/meta/state"))&&state.state()==UpdateState::Unverified&&hal_completed==1);
 write("/work/model-active-slot","1");puts("MODEL active slot=1 after Unverified");fflush(stdout);
}
'''
    old = 'model_prepare(dynamic);'
    assert adapter.count(old) == 1
    adapter = adapter.replace(old, 'model_prepare_allocated(manifest);')
    start = adapter.index('        CowOptions options;')
    end = adapter.index('\n    }\n    bool UpdateUsesSnapshotCompression()', start)
    adapter = adapter[:start] + '        return allocated_control->OpenCowWriter(name,source,label);' + adapter[end:]
    adapter = adapter.replace('("/work/"+name+".cow")', '("/work/cows/"+name+"_b-cow")')
    old = 'bool UnmapAllPartitions() override { ++unmaps; return true; }'
    assert old in adapter
    adapter = adapter.replace(old, r'''bool UnmapAllPartitions() override {
        ++unmaps;for(const auto& n:dynamic)assert(allocated_control->UnmapWritten(n));
        assert(active_views.empty());puts("MODEL actual snapshot unmapping active=0");fflush(stdout);return true;
    }''')
    old = 'void Cleanup() override { printf("BOUNDARY Cleanup file model\\n"); }'
    assert old in adapter
    adapter = adapter.replace(old, r'''void Cleanup() override {
        if (allocated_control) {
            allocated_control->Cleanup();
            allocated_control.reset();
            puts("MODEL released controller during Cleanup");
        }
        puts("BOUNDARY Cleanup file model");fflush(stdout);
    }''')
    # Headers declaring global extent templates must precede using-directives
    # in shared allocation support, as in the already tested handoff fixture.
    headers = adapter[:adapter.index('using android::base::unique_fd;')]
    return headers + '\n' + handoff + '\n' + adapter
