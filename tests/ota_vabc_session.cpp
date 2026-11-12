// Offline fixture: original VABC / COW / verifier code, regular files only.
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

static std::vector<char> load(const char* path) {
    std::ifstream stream(path, std::ios::binary);
    assert(stream.good());
    return {std::istreambuf_iterator<char>(stream), {}};
}
static void store(const char* path, const std::vector<char>& data) {
    unique_fd fd(open(path, O_CREAT | O_TRUNC | O_WRONLY | O_CLOEXEC, 0600));
    assert(fd >= 0 && write(fd, data.data(), data.size()) == ssize_t(data.size()));
}
// Device mapping is the explicit test boundary, never a real SnapshotManager.
// Every unexpected interface call fails instead of silently claiming support.
class FileControl final : public DynamicPartitionControlInterface {
 public:
    bool deny_open = false;
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
    bool MapAllPartitions() override { ++maps; return true; }
    bool UnmapAllPartitions() override { ++unmaps; return true; }
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
    assert(argc == 3);
    xz_crc32_init();
    const std::string mode = argv[1];
    auto input = load("/work/input.bin");
    auto expected = load("/work/expected.bin");
    assert(expected.size() == 65536);
    store("/work/source.bin", std::vector<char>(kSize, char(0x5a)));
    InstallPlan plan;
    plan.target_slot = 1;
    plan.write_verity = false;
    auto& part = plan.partitions.emplace_back();
    part.name = "system";
    part.block_size = 4096;
    part.target_size = kSize;
    part.source_path = "/work/source.bin";
    part.target_path = part.readonly_target_path = "/work/view.bin";
    PartitionUpdate update;
    update.set_partition_name("system");
    InstallOperation op;
    op.set_type(static_cast<InstallOperation::Type>(std::stoul(argv[2])));
    op.set_data_length(input.size());
    for (uint64_t start : {0, 24}) {
        auto* e = op.add_dst_extents(); e->set_start_block(start); e->set_num_blocks(8);
    }
    FileControl control;
    VABCPartitionWriter writer(update, part, &control, 4096);
    if (mode == "open-fail") {
        control.deny_open = true;
        assert(!writer.Init(&plan, false, 0));
        assert(!writer.FinishedInstallOps() && writer.Close() == 0 && control.opens == 1);
        printf("PASS mode=open-fail init=0 finish=0 close=0\n"); return 0;
    }
    assert(writer.Init(&plan, false, 0));
    const bool executed = writer.PerformReplaceOperation(op, input.data(), input.size());
    const bool want_operation = mode != "bad-bz" && mode != "bad-xz" && mode != "oversize";
    assert(executed == want_operation);
    // On failure, finish is a diagnostic probe, not the real OTA success path.
    writer.CheckpointUpdateProgress(1);
    if (mode == "zero") {
        InstallOperation zero;
        zero.set_type(InstallOperation::ZERO);
        auto* e = zero.add_dst_extents(); e->set_start_block(8); e->set_num_blocks(8);
        assert(writer.PerformZeroOrDiscardOperation(zero));
        writer.CheckpointUpdateProgress(2);
    }
    assert(writer.FinishedInstallOps());
    assert(writer.Close() == 0 && writer.Close() == 0);
    auto reader = std::make_unique<CowReader>();
    assert(reader->Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC)), kEndOfInstallLabel));
    assert(reader->VerifyMergeOps());
    CompressedSnapshotReader view(std::move(reader), part.source_path, kSize);
    std::vector<char> actual(kSize);
    // Exercise seeks and unaligned multi-block reads through the real reader.
    assert(view.Seek(0, SEEK_SET) == 0);
    size_t done = 0;
    while (done < actual.size()) {
        size_t count = std::min(size_t(7013), actual.size() - done);
        assert(view.Read(actual.data()+done, count) == ssize_t(count)); done += count;
    }
    assert(view.Close());
    std::vector<char> wanted(kSize, char(0x5a));
    memcpy(wanted.data(), expected.data(), 32768);
    memcpy(wanted.data()+24*4096, expected.data()+32768, 32768);
    if (mode == "zero") memset(wanted.data()+8*4096, 0, 8*4096);
    const bool valid_content = mode != "short" && mode != "bad-bz" && mode != "bad-xz";
    assert((actual == wanted) == valid_content);
    if (!valid_content) assert(actual == std::vector<char>(kSize, char(0x5a)));
    store("/work/readback.bin", actual);
    // Stand-in for dm-user/snapuserd mapping: materialize the ORIGINAL reader's
    // output, then run the ORIGINAL asynchronous verifier on that ordinary file.
    store("/work/view.bin", actual);
    assert(HashCalculator::RawHashOfBytes(wanted.data(), wanted.size(), &part.target_hash));
    if (mode == "wrong-hash") part.target_hash[0] ^= 1;
    const bool want_verify = valid_content && mode != "wrong-hash";
    brillo::BaseMessageLoop loop;
    loop.SetAsCurrent();
    ActionProcessor processor;
    Done delegate;
    processor.set_delegate(&delegate);
    auto feed = std::make_unique<Feed>(); feed->plan = plan;
    auto verifier = std::make_unique<FilesystemVerifierAction>(&control);
    BondActions(feed.get(), verifier.get());
    processor.EnqueueAction(std::move(feed));
    processor.EnqueueAction(std::move(verifier));
    processor.StartProcessing();
    if (!delegate.completed) loop.Run();
    assert(delegate.completed && !processor.IsRunning());
    assert(delegate.result == (want_verify ? ErrorCode::kSuccess : ErrorCode::kNewRootfsVerificationError));
    assert(control.maps == 1 && control.unmaps == 1 && control.opens == 1);
    printf("PASS mode=%s operation_return=%d finish=1 close=0 content_complete=%d verifier_code=%d map=%u unmap=%u\n",
           mode.c_str(), executed, valid_content, int(delegate.result), control.maps, control.unmaps);
}
