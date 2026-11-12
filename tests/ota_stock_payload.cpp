// Unmodified full stock payload streamed through original ARM64 engine.
#include <map>
#include <set>
#include <sys/stat.h>
#include <libsnapshot/cow_reader.h>
#include <libsnapshot/cow_writer.h>
#include "libsnapshot_cow/snapshot_reader.h"
#include "update_engine/common/action_processor.h"
#include "update_engine/common/dynamic_partition_control_interface.h"
#include "update_engine/common/hash_calculator.h"
#include "update_engine/payload_consumer/filesystem_verifier_action.h"
#include "update_engine/payload_consumer/postinstall_runner_action.h"
#include "update_engine/payload_consumer/vabc_partition_writer.h"
#include <brillo/message_loops/base_message_loop.h>
#include <xz.h>
#include <endian.h>
#include "update_engine/common/fake_boot_control.h"
#include "update_engine/common/fake_hardware.h"
#include "update_engine/common/prefs.h"
#include "update_engine/payload_consumer/delta_performer.h"
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

static std::vector<std::string> final_events;

// Device mapping is the explicit test boundary, never a real SnapshotManager.
// Every unexpected interface call fails instead of silently claiming support.
class FileControl final : public DynamicPartitionControlInterface {
 public:
    std::map<std::string, uint64_t> sizes;
    std::set<std::string> dynamic;
    uint64_t compression_factor = 0;
    std::string compression;
    uint32_t cow_version = 0;
    bool deny_open = false;
    unsigned opens = 0, maps = 0, unmaps = 0, prepares = 0;
    bool deny_prepare = false;
    bool finish_ok = true;
    unsigned finishes = 0;
    FeatureFlag GetVirtualAbCompressionXorFeatureFlag() override {
        return FeatureFlag(FeatureFlag::Value::NONE);
    }
    std::unique_ptr<ICowWriter> OpenCowWriter(const std::string& name,
            const std::optional<std::string>& source, std::optional<uint64_t> label) override {
        assert(dynamic.contains(name) && !source.has_value() && !label);
        ++opens;
        if (deny_open) return nullptr;
        CowOptions options;
        options.compression = compression;
        options.compression_factor = compression_factor;
        options.op_count_max = sizes.at(name) / 4096 + 1024;
        options.max_blocks = sizes.at(name) / 4096;
        options.scratch_space = false;
        options.num_compress_threads = 1;
        int flags = O_RDWR | O_CLOEXEC;
        if (!label) flags |= O_CREAT | O_TRUNC;
        return CreateCowWriter(cow_version, options,
            unique_fd(open(("/work/" + name + ".cow").c_str(), flags, 0600)), label);
    }
    bool UpdateUsesSnapshotCompression() override { return true; }
    bool IsDynamicPartition(const std::string& name, uint32_t slot) override {
        assert(slot == 1); return dynamic.contains(name);
    }
    bool MapAllPartitions() override { ++maps; return true; }
    bool UnmapAllPartitions() override { ++unmaps; return true; }
#define NOFLAG(name) FeatureFlag name() override { assert(false); return FeatureFlag(FeatureFlag::Value::NONE); }
    NOFLAG(GetDynamicPartitionsFeatureFlag)
    FeatureFlag GetVirtualAbFeatureFlag() override {
        return FeatureFlag(FeatureFlag::Value::LAUNCH);
    }
    NOFLAG(GetVirtualAbCompressionFeatureFlag)
    NOFLAG(GetVirtualAbUserspaceSnapshotsFeatureFlag)
#undef NOFLAG
    bool OptimizeOperation(const std::string&, const InstallOperation&, InstallOperation*) override { assert(false); return false; }
    void Cleanup() override { assert(false); }
    bool PreparePartitionsForUpdate(uint32_t source, uint32_t target,
            const DeltaArchiveManifest& manifest, bool update, uint64_t* required, ErrorCode*) override {
        assert(source == 0 && target == 1 && update);
        assert(manifest.partitions_size() > 1);
        for (const auto& group : manifest.dynamic_partition_metadata().groups())
            dynamic.insert(group.partition_names().begin(), group.partition_names().end());
        for (const auto& p : manifest.partitions()) {
            const auto& name = p.partition_name();
            assert(name.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_") == std::string::npos);
            assert(p.has_new_partition_info() && !p.has_old_partition_info());
            sizes[name] = p.new_partition_info().size();
            if (!dynamic.contains(name)) {
                unique_fd fd(open(("/work/" + name + ".bin").c_str(), O_CREAT | O_TRUNC | O_RDWR, 0600));
                assert(fd >= 0 && ftruncate(fd, sizes[name]) == 0);
            }
        }
        compression = manifest.dynamic_partition_metadata().vabc_compression_param();
        compression_factor = manifest.dynamic_partition_metadata().compression_factor();
        cow_version = manifest.dynamic_partition_metadata().cow_version();
        assert(manifest.dynamic_partition_metadata().cow_version() == 3);
        ++prepares;
        *required = deny_prepare ? 1048576 : 0;
        return !deny_prepare;
    }
    bool FinishUpdate(bool powerwash) override {
        assert(!powerwash); ++finishes; final_events.push_back("finish"); return finish_ok;
    }
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
    bool completed = false, verifier_ran = false, postinstall_ran = false;
    ErrorCode verifier_result = ErrorCode::kError;
    ErrorCode result = ErrorCode::kError;
    void ActionCompleted(ActionProcessor*, AbstractAction* action, ErrorCode code) override {
        if (action->Type() == FilesystemVerifierAction::StaticType()) {
            verifier_ran = true; verifier_result = code; result = code;
        } else if (action->Type() == PostinstallRunnerAction::StaticType()) {
            postinstall_ran = true; result = code;
        }
    }
    void ProcessingDone(const ActionProcessor*, ErrorCode code) override {
        assert(verifier_ran && result == code);
        completed = true;
        brillo::MessageLoop::current()->BreakLoop();
    }
};


class FileBoot final : public FakeBootControl {
 public:
    bool slot_ok = true;
    unsigned switches = 0;
    bool SetActiveBootSlot(Slot slot) override {
        assert(slot == 1); ++switches; final_events.push_back("slot"); return slot_ok;
    }
    std::optional<PartitionDevice> GetPartitionDevice(const std::string& name,
            uint32_t slot, uint32_t current, bool untouched = false) const override {
        assert(slot == 1 && current == 0 && !untouched);
        auto* control = static_cast<FileControl*>(const_cast<FileBoot*>(this)->GetDynamicPartitionControl());
        assert(control->sizes.contains(name));
        const auto path = "/work/" + name + ".bin";
        return PartitionDevice{path, path, control->dynamic.contains(name)};
    }
};

int main(int argc, char** argv) {
    assert(argc == 5);
    xz_crc32_init();
    const uint64_t zip_offset = std::stoull(argv[1]);
    const uint64_t payload_size = std::stoull(argv[2]);
    const uint64_t metadata_size = std::stoull(argv[3]);
    brillo::Blob expected_hash;
    const std::string hex = argv[4];
    assert(hex.size() == 64);
    for (size_t i = 0; i < hex.size(); i += 2)
        expected_hash.push_back(std::stoul(hex.substr(i, 2), nullptr, 16));
    FileBoot boot;
    auto owner = std::make_unique<FileControl>(); auto* control = owner.get();
    boot.SetDynamicPartitionControl(std::move(owner));
    FakeHardware hardware;
    MemoryPrefs prefs;
    InstallPlan plan; plan.source_slot = 0; plan.target_slot = 1;
    plan.hash_checks_mandatory = true;
    InstallPlan::Payload payload; payload.size = payload_size; payload.metadata_size = metadata_size;
    DeltaPerformer performer(&prefs, &boot, &hardware, nullptr, &plan, &payload, true);
    // Use original Recovery trust behavior. No test key or signature replacement.
    unique_fd input(open("/work/source.zip", O_RDONLY | O_CLOEXEC)); assert(input >= 0);
    std::vector<char> buffer(1024 * 1024);
    uint64_t position = 0;
    while (position < payload_size) {
        const auto count = std::min(uint64_t(buffer.size()), payload_size - position);
        const ssize_t got = pread(input, buffer.data(), count, zip_offset + position);
        assert(got == ssize_t(count));
        ErrorCode code = ErrorCode::kSuccess;
        const bool written = performer.Write(buffer.data(), count, &code);
        if (!written) {
            printf("REJECT offset=%llu code=%d\n", (unsigned long long)position, int(code)); fflush(stdout);
            return 2;
        }
        position += count;
        if (position % (64 * 1024 * 1024) == 0 || position == payload_size) {
            printf("STREAM %llu/%llu\n", (unsigned long long)position, (unsigned long long)payload_size); fflush(stdout);
        }
    }
    assert(performer.Close() == 0);
    assert(performer.VerifyPayload(expected_hash, payload_size) == ErrorCode::kSuccess);
    printf("PAYLOAD verified partitions=%zu dynamic=%zu opened=%u\n", plan.partitions.size(), control->dynamic.size(), control->opens); fflush(stdout);
    assert(plan.partitions.size() == control->sizes.size() && control->opens == control->dynamic.size());
    for (const auto& name : control->dynamic) {
        const auto size = control->sizes.at(name);
        auto reader = std::make_unique<CowReader>();
        assert(reader->Parse(unique_fd(open(("/work/"+name+".cow").c_str(), O_RDONLY)), kEndOfInstallLabel));
        CompressedSnapshotReader view(std::move(reader), std::nullopt, size);
        unique_fd output(open(("/work/"+name+".bin").c_str(), O_CREAT | O_TRUNC | O_WRONLY, 0600)); assert(output >= 0);
        uint64_t pos = 0;
        while (pos < size) {
            const size_t count = std::min(uint64_t(buffer.size()), size-pos);
            assert(view.Read(buffer.data(), count) == ssize_t(count));
            assert(write(output, buffer.data(), count) == ssize_t(count)); pos += count;
        }
        assert(view.Close());
        printf("VIEW %s %llu\n", name.c_str(), (unsigned long long)size); fflush(stdout);
    }
    assert(!plan.write_verity);
    brillo::BaseMessageLoop loop; loop.SetAsCurrent();
    ActionProcessor processor; Done done; processor.set_delegate(&done);
    auto feed = std::make_unique<Feed>(); feed->plan = plan;
    auto verifier = std::make_unique<FilesystemVerifierAction>(control);
    BondActions(feed.get(), verifier.get());
    processor.EnqueueAction(std::move(feed)); processor.EnqueueAction(std::move(verifier));
    processor.StartProcessing(); if (!done.completed) loop.Run();
    assert(done.completed && done.verifier_result == ErrorCode::kSuccess);
    assert(control->maps == 1 && control->unmaps == 1 && boot.switches == 0);
    printf("PASS full-stock-payload bytes=%llu partitions=%zu opens=%u maps=%u unmaps=%u\n",
        (unsigned long long)position, plan.partitions.size(), control->opens, control->maps, control->unmaps);
}
