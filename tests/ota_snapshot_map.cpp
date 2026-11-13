// Original asynchronous verifier with explicit map failures and regular files.
#include <libsnapshot/cow_reader.h>
#include <libsnapshot/cow_writer.h>
#include "libsnapshot_cow/snapshot_reader.h"
#include "update_engine/common/action_processor.h"
#include "update_engine/common/dynamic_partition_control_interface.h"
#include "update_engine/common/hash_calculator.h"
#include "update_engine/payload_consumer/filesystem_verifier_action.h"
#include "update_engine/payload_consumer/vabc_partition_writer.h"
#include <brillo/message_loops/base_message_loop.h>
#include <xz.h>
#include <fcntl.h>
#include <unistd.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

using android::base::unique_fd;
using namespace android::snapshot;
using namespace chromeos_update_engine;
constexpr size_t kSize = 32 * 4096;

static void store(const char* path, const std::vector<char>& data) {
    unique_fd fd(open(path, O_CREAT | O_TRUNC | O_WRONLY | O_CLOEXEC, 0600));
    assert(fd >= 0 && write(fd, data.data(), data.size()) == ssize_t(data.size()));
}
// Device mapping is the explicit test boundary, never a real SnapshotManager.
// Every unexpected interface call fails instead of silently claiming support.
class FileControl final : public DynamicPartitionControlInterface {
 public:
    bool deny_open = false;
    bool map_ok = true;
    bool unmap_ok = true;
    unsigned opens = 0, maps = 0, unmaps = 0;
    FeatureFlag GetVirtualAbCompressionXorFeatureFlag() override {
        return FeatureFlag(FeatureFlag::Value::NONE);
    }
    std::unique_ptr<ICowWriter> OpenCowWriter(const std::string& name,
            const std::optional<std::string>& source, std::optional<uint64_t> label) override {
        assert(name == "system" && source == "/work/source.bin");
        ++opens;
        if (deny_open) return nullptr;
        CowOptions options;
        options.compression = "lz4";
        options.compression_factor = 65536;
        options.op_count_max = 128;
        options.max_blocks = 32;
        options.scratch_space = false;
        options.num_compress_threads = 1;
        int flags = O_RDWR | O_CLOEXEC;
        if (!label) flags |= O_CREAT | O_TRUNC;
        return CreateCowWriter(3, options,
            unique_fd(open("/work/test.cow", flags, 0600)), label);
    }
    bool UpdateUsesSnapshotCompression() override { return true; }
    bool IsDynamicPartition(const std::string& name, uint32_t slot) override {
        assert(name == "system" && slot == 1); return true;
    }
    bool MapAllPartitions() override { ++maps; return map_ok; }
    bool UnmapAllPartitions() override { ++unmaps; return unmap_ok; }
#define NOFLAG(name) FeatureFlag name() override { assert(false); return FeatureFlag(FeatureFlag::Value::NONE); }
    NOFLAG(GetDynamicPartitionsFeatureFlag)
    NOFLAG(GetVirtualAbFeatureFlag)
    NOFLAG(GetVirtualAbCompressionFeatureFlag)
    NOFLAG(GetVirtualAbUserspaceSnapshotsFeatureFlag)
#undef NOFLAG
    bool OptimizeOperation(const std::string&, const InstallOperation&, InstallOperation*) override { assert(false); return false; }
    void Cleanup() override { assert(false); }
    bool PreparePartitionsForUpdate(uint32_t, uint32_t, const DeltaArchiveManifest&, bool, uint64_t*, ErrorCode*) override { assert(false); return false; }
    bool FinishUpdate(bool) override { assert(false); return false; }
    std::unique_ptr<AbstractAction> GetCleanupPreviousUpdateAction(BootControlInterface*, PrefsInterface*, CleanupPreviousUpdateActionDelegateInterface*) override { assert(false); return nullptr; }
    bool ResetUpdate(PrefsInterface*) override { assert(false); return false; }
    bool ListDynamicPartitionsForSlot(uint32_t, uint32_t, std::vector<std::string>*) override { assert(false); return false; }
    bool GetDeviceDir(std::string*) override { assert(false); return false; }
    bool VerifyExtentsForUntouchedPartitions(uint32_t, uint32_t, const std::vector<std::string>&) override { assert(false); return false; }
    std::unique_ptr<FileDescriptor> OpenCowFd(const std::string&, const std::optional<std::string>&, bool) override { assert(false); return nullptr; }
};

class Feed final : public InstallPlanAction {
 public:
    InstallPlan plan;
    void PerformAction() override {
        SetOutputObject(plan);
        processor_->ActionComplete(this, ErrorCode::kSuccess);
    }
    std::string Type() const override { return "FilePlanFeeder"; }
};
class Done final : public ActionProcessorDelegate {
 public:
    bool completed = false, verifier_ran = false;
    ErrorCode result = ErrorCode::kError;
    void ActionCompleted(ActionProcessor*, AbstractAction* action, ErrorCode code) override {
        if (action->Type() == FilesystemVerifierAction::StaticType()) {
            verifier_ran = true; result = code;
        }
    }
    void ProcessingDone(const ActionProcessor*, ErrorCode code) override {
        assert(verifier_ran && result == code);
        completed = true;
        brillo::MessageLoop::current()->BreakLoop();
    }
};


int main(int argc, char** argv) {
    assert(argc == 2);
    const std::string mode = argv[1];
    FileControl control;
    control.map_ok = mode != "initial-fail" && mode != "initial-fail-missing-path" && mode != "remap-fail";
    control.unmap_ok = mode != "cleanup-fail" && mode != "remap-unmap-fail" && mode != "hash-mismatch-unmap-fail";
    InstallPlan plan;
    plan.target_slot = 1;
    // With write_verity requested but no tree/FEC, original code enters its
    // remap-before-hash path, without actually generating any verity data.
    plan.write_verity = mode.starts_with("remap-");
    auto& part = plan.partitions.emplace_back();
    part.name = "system"; part.block_size = 4096; part.target_size = 4096;
    part.target_path = part.readonly_target_path = mode == "initial-fail-missing-path" ? "/work/missing.bin" : "/work/view.bin";
    std::vector<char> data(4096, 'A');
    store("/work/view.bin", data);
    assert(HashCalculator::RawHashOfBytes(data.data(), data.size(), &part.target_hash));
    if (mode.starts_with("hash-mismatch")) part.target_hash[0] ^= 1;
    brillo::BaseMessageLoop loop; loop.SetAsCurrent();
    ActionProcessor processor; Done delegate; processor.set_delegate(&delegate);
    auto feed = std::make_unique<Feed>(); feed->plan = plan;
    auto verifier = std::make_unique<FilesystemVerifierAction>(&control);
    BondActions(feed.get(), verifier.get());
    processor.EnqueueAction(std::move(feed)); processor.EnqueueAction(std::move(verifier));
    processor.StartProcessing(); if (!delegate.completed) loop.Run();
    printf("mode=%s code=%d map=%u unmap=%u\n", mode.c_str(), int(delegate.result), control.maps, control.unmaps);
    fflush(stdout);
    const auto wanted = mode.starts_with("hash-mismatch") ? ErrorCode::kNewRootfsVerificationError :
        !control.map_ok || !control.unmap_ok ? ErrorCode::kFilesystemVerifierError : ErrorCode::kSuccess;
    assert(delegate.completed && !processor.IsRunning() && delegate.result == wanted);
    assert(control.maps == (mode == "remap-unmap-fail" ? 0u : 1u));
    assert(control.unmaps == (mode == "remap-fail" ? 2u : 1u) && control.opens == 0);
    puts("PASS");
}
