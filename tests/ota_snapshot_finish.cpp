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

namespace fs = std::filesystem;
using namespace android::snapshot;
using android::dm::DmTable;
using android::dm::DmDeviceState;
using MergeStatus = aidl::android::hardware::boot::MergeStatus;
static std::string sync_failure;
static unsigned sync_injections = 0, sync_completions = 0, merge_calls = 0;
static bool merge_ok = true, sync_interrupt = false;
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd) {
    struct stat actual{}, selected{};
    if (!sync_failure.empty() && fstat(fd, &actual) == 0 &&
        stat(sync_failure.c_str(), &selected) == 0 &&
        actual.st_dev == selected.st_dev && actual.st_ino == selected.st_ino) {
        if (!sync_interrupt || sync_injections == 0) {
            ++sync_injections; errno = sync_interrupt ? EINTR : EIO; return -1;
        }
        int result = __real_fsync(fd);
        if (result == 0) ++sync_completions;
        return result;
    }
    return __real_fsync(fd);
}
[[noreturn]] static void denied() { assert(false && "unexpected device operation"); abort(); }
class DenyMapper final : public android::dm::IDeviceMapper {
 public:
 bool CreateDevice(const std::string&, const DmTable&, std::string*, const std::chrono::milliseconds&) override { denied(); }
 DmDeviceState GetState(const std::string&) const override { denied(); }
 bool LoadTableAndActivate(const std::string&, const DmTable&) override { denied(); }
 bool LoadTable(const std::string&, const DmTable&) override { denied(); }
 bool GetTableInfo(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetTableStatus(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetTableStatusIma(const std::string&, std::vector<TargetInfo>*) override { denied(); }
 bool GetDmDevicePathByName(const std::string&, std::string*) override { denied(); }
 bool GetDeviceString(const std::string&, std::string*) override { denied(); }
 bool DeleteDeviceIfExists(const std::string&) override { denied(); }
};
class DenyOpener final : public android::fs_mgr::IPartitionOpener {
 public:
 android::base::unique_fd Open(const std::string&, int) const override { denied(); }
 bool GetInfo(const std::string&, android::fs_mgr::BlockDeviceInfo*) const override { denied(); }
 std::string GetDeviceString(const std::string&) const override { denied(); }
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
   assert(status == MergeStatus::SNAPSHOTTED); ++merge_calls; return merge_ok;
 }
 bool SetActiveBootSlot(unsigned int) override { denied(); }
 bool SetSlotAsUnbootable(unsigned int) override { denied(); }
 bool IsSlotMarkedSuccessful(unsigned int) override { denied(); }
 bool IsRecovery() const override { return true; }
 bool IsFirstStageInit() const override { return false; }
 std::unique_ptr<IImageManager> OpenImageManager() const override { denied(); }
 android::dm::IDeviceMapper& GetDeviceMapper() override { return dm; }
 bool IsTempMetadata() const override { return false; }
};
static std::string read(const std::string& path) {
 std::string data; assert(android::base::ReadFileToString(path, &data)); return data;
}
static void write(const std::string& path, const std::string& data) {
 assert(android::base::WriteStringToFile(data, path));
}
int main(int argc, char** argv) {
 assert(argc == 2); const std::string name = argv[1];
 fs::create_directories("/work/meta/snapshots");
 SnapshotUpdateStatus initial;
 initial.set_state(name == "wrong-state" ? UpdateState::Merging : UpdateState::Initiated);
 initial.set_using_snapuserd(true); initial.set_userspace_snapshots(true);
 initial.set_source_build_fingerprint("synthetic-source");
 initial.set_merge_phase(MergePhase::FIRST_PHASE); initial.set_io_uring_enabled(true);
 initial.set_o_direct(true); initial.set_skip_verification(true);
 initial.set_cow_op_merge_size(123); initial.set_num_worker_threads(2);
 initial.set_verify_block_size(4096); initial.set_num_verification_threads(4);
 initial.set_ublk_snapshots_enabled(true); initial.set_legacy_snapuserd(true);
 std::string bytes; assert(initial.SerializeToString(&bytes));
 write("/work/meta/state", bytes);
 SnapshotStatus snapshot;
 snapshot.set_name("system_b"); snapshot.set_using_snapuserd(true);
 std::string snapbytes; assert(snapshot.SerializeToString(&snapbytes));
 write("/work/meta/snapshots/system_b", snapbytes);
 const bool wipe = name == "wipe" || name == "forward-write-error";
 write("/work/meta/rollback-indicator", "old rollback");
 write("/work/meta/allow-forward-merge", "old forward");
 if (name == "missing-metadata") fs::remove_all("/work/meta");
 if (name == "missing-snapshots") fs::remove_all("/work/meta/snapshots");
 if (name == "invalid-snapshot") write("/work/meta/snapshots/system_b", "\xff");
 if (name == "boot-rename-error") fs::create_directory("/work/meta/snapshot-boot");
 if (name == "rollback-remove-error") {
   fs::remove("/work/meta/rollback-indicator"); fs::create_directory("/work/meta/rollback-indicator");
   write("/work/meta/rollback-indicator/child", "keep");
 }
 if (name == "forward-write-error") {
   fs::remove("/work/meta/allow-forward-merge"); fs::create_directory("/work/meta/allow-forward-merge");
 }
 if (name == "state-open-error") fs::create_directory("/work/meta/state.tmp");
 if (name == "merge-status-error") merge_ok = false;
 if (name == "boot-sync-error") sync_failure = "/work/meta/snapshot-boot.tmp";
 if (name == "state-sync-error") sync_failure = "/work/meta/state.tmp";
 if (name == "boot-sync-interrupted" || name == "state-sync-interrupted") {
   sync_interrupt = true;
   sync_failure = name == "boot-sync-interrupted" ? "/work/meta/snapshot-boot.tmp" : "/work/meta/state.tmp";
 }
 auto manager = SnapshotManager::New(new Info);
 bool result = manager->FinishedSnapshotWrites(wipe);
 bool success = name == "normal" || name == "wipe" || name == "idempotent" || sync_interrupt;
 printf("RESULT name=%s returned=%d expected=%d merge_calls=%u sync_injections=%u sync_completions=%u\n",
        name.c_str(), result, success, merge_calls, sync_injections, sync_completions); fflush(stdout);
 assert(result == success);
 assert(sync_completions == unsigned(sync_interrupt));
 if (name == "missing-metadata") { assert(merge_calls == 0); return 0; }
 SnapshotUpdateStatus after; assert(after.ParseFromString(read("/work/meta/state")));
 if (success) {
   initial.set_state(UpdateState::Unverified); assert(initial.SerializeAsString() == after.SerializeAsString());
   assert(read("/work/meta/snapshot-boot") == "_a");
   assert(!fs::exists("/work/meta/rollback-indicator"));
   assert(fs::exists("/work/meta/allow-forward-merge") == wipe);
   if (wipe) assert(read("/work/meta/allow-forward-merge") == "1");
   assert(merge_calls == 1);
   if (name == "idempotent") {
     // An already-Unverified state returns before inspecting markers or snapshots.
     write("/work/meta/snapshot-boot", "keep"); fs::remove_all("/work/meta/snapshots");
     assert(manager->FinishedSnapshotWrites(true)); assert(merge_calls == 1);
     assert(read("/work/meta/snapshot-boot") == "keep");
     assert(!fs::exists("/work/meta/allow-forward-merge"));
   }
 } else {
   assert(after.SerializeAsString() == bytes);
   bool reached_state = name == "state-open-error" || name == "merge-status-error" || name == "state-sync-error";
   assert(merge_calls == unsigned(reached_state));
   if (reached_state) assert(read("/work/meta/snapshot-boot") == "_a");
   if (name == "boot-sync-error") assert(!fs::exists("/work/meta/snapshot-boot"));
   if (name == "boot-sync-error" || name == "state-sync-error")
     assert(fs::is_regular_file(sync_failure)); // failed temporary file remains, unpublished
 }
 assert(sync_injections == unsigned(name == "boot-sync-error" || name == "state-sync-error" || sync_interrupt));
 printf("PASS %s actual state/flags checked; no device effects\n", name.c_str());
}
