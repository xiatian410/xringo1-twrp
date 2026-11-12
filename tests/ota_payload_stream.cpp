// Synthetic payload streamed through original ARM64 DeltaPerformer, VABC and verifier.
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
    unsigned opens = 0, maps = 0, unmaps = 0, prepares = 0;
    bool deny_prepare = false;
    FeatureFlag GetVirtualAbCompressionXorFeatureFlag() override {
        return FeatureFlag(FeatureFlag::Value::NONE);
    }
    std::unique_ptr<ICowWriter> OpenCowWriter(const std::string& name,
            const std::optional<std::string>& source, std::optional<uint64_t> label) override {
        assert(name == "system" && !source.has_value());
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
    bool PreparePartitionsForUpdate(uint32_t source, uint32_t target,
            const DeltaArchiveManifest& manifest, bool update, uint64_t* required, ErrorCode*) override {
        assert(source == 0 && target == 1 && update);
        assert(manifest.partitions_size() == 1 && manifest.partitions(0).partition_name() == "system");
        assert(manifest.dynamic_partition_metadata().cow_version() == 3);
        ++prepares;
        *required = deny_prepare ? 1048576 : 0;
        return !deny_prepare;
    }
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


class FileBoot final : public FakeBootControl {
 public:
    std::optional<PartitionDevice> GetPartitionDevice(const std::string& name,
            uint32_t slot, uint32_t current, bool untouched = false) const override {
        assert(name == "system" && slot == 1 && current == 0 && !untouched);
        return PartitionDevice{"/work/view.bin", "/work/view.bin", true};
    }
};
static void be64(std::string* out, uint64_t value) {
    value = htobe64(value); out->append(reinterpret_cast<char*>(&value), sizeof(value));
}
int main(int argc, char** argv) {
    assert(argc == 3);
    xz_crc32_init();
    const std::string mode = argv[1];
    auto encoded = load("/work/input.bin");
    const auto expected = load("/work/expected.bin");
    assert(expected.size() == 65536);
    DeltaArchiveManifest manifest;
    manifest.set_block_size(4096);
    manifest.set_minor_version(mode == "bad-minor" ? 99 : 0);
    manifest.set_max_timestamp(INT64_MAX);
    auto* dynamic = manifest.mutable_dynamic_partition_metadata();
    dynamic->set_snapshot_enabled(true);
    dynamic->set_vabc_enabled(true);
    dynamic->set_vabc_compression_param("lz4");
    dynamic->set_cow_version(3);
    auto* partition = manifest.add_partitions();
    partition->set_partition_name("system");
    brillo::Blob target_hash, operation_hash;
    assert(HashCalculator::RawHashOfBytes(expected.data(), expected.size(), &target_hash));
    assert(HashCalculator::RawHashOfBytes(encoded.data(), encoded.size(), &operation_hash));
    partition->mutable_new_partition_info()->set_size(expected.size());
    partition->mutable_new_partition_info()->set_hash(target_hash.data(), target_hash.size());
    auto* op = partition->add_operations();
    op->set_type(static_cast<InstallOperation::Type>(std::stoul(argv[2])));
    op->set_data_offset(0);
    op->set_data_length(encoded.size());
    if (mode == "bad-operation-hash") operation_hash[0] ^= 1;
    op->set_data_sha256_hash(operation_hash.data(), operation_hash.size());
    auto* extent = op->add_dst_extents(); extent->set_start_block(0); extent->set_num_blocks(16);
    // Framing-only signature message, deliberately NOT a cryptographic signature.
    // Recovery's existing compile-time path skips VerifySignature, but requires
    // a nonempty signature block when a key is configured.
    Signatures framing;
    framing.add_signatures()->set_data("unsigned-fixture-marker");
    std::string signature_bytes;
    assert(framing.SerializeToString(&signature_bytes));
    if (mode != "missing-signature") {
        manifest.set_signatures_offset(encoded.size());
        manifest.set_signatures_size(signature_bytes.size());
    }
    std::string proto;
    assert(manifest.SerializeToString(&proto));
    std::string stream = mode == "bad-magic" ? "Fail" : "CrAU";
    be64(&stream, mode == "bad-major" ? 99 : 2);
    be64(&stream, proto.size());
    uint32_t signature_size = 0;
    stream.append(reinterpret_cast<char*>(&signature_size), 4);
    stream += proto;
    const size_t metadata_size = stream.size();
    stream.append(encoded.data(), encoded.size());
    if (mode != "missing-signature") stream += signature_bytes;
    const size_t total_size = stream.size();
    brillo::Blob payload_hash;
    assert(HashCalculator::RawHashOfBytes(stream.data(), stream.size(), &payload_hash));
    if (mode == "truncated-signature") stream.resize(stream.size()-1);
    if (mode == "truncated-data") stream.resize(metadata_size+encoded.size()-1);
    FileBoot boot;
    auto control_owner = std::make_unique<FileControl>();
    auto* control = control_owner.get();
    control->deny_open = mode == "open-fail";
    control->deny_prepare = mode == "prepare-fail";
    boot.SetDynamicPartitionControl(std::move(control_owner));
    FakeHardware hardware;
    MemoryPrefs prefs;
    InstallPlan plan;
    plan.source_slot = 0; plan.target_slot = 1;
    plan.hash_checks_mandatory = true;
    InstallPlan::Payload payload;
    payload.size = total_size;
    payload.metadata_size = metadata_size + (mode == "bad-metadata-size" ? 1 : 0);
    DeltaPerformer performer(&prefs, &boot, &hardware, nullptr, &plan, &payload, false);
    performer.set_public_key_path("/work/public.pem");
    bool accepted = true;
    ErrorCode error = ErrorCode::kSuccess;
    size_t position = 0;
    // Split header, protobuf and data at many boundaries. No private fields seeded.
    while (position < stream.size()) {
        const size_t count = std::min(size_t(113), stream.size()-position);
        accepted = performer.Write(stream.data()+position, count, &error);
        position += count;
        if (!accepted) break;
    }
    ErrorCode wanted = ErrorCode::kSuccess;
    if (mode == "bad-magic") wanted = ErrorCode::kDownloadInvalidMetadataMagicString;
    if (mode == "bad-major") wanted = ErrorCode::kUnsupportedMajorPayloadVersion;
    if (mode == "bad-minor") wanted = ErrorCode::kUnsupportedMinorPayloadVersion;
    if (mode == "bad-metadata-size") wanted = ErrorCode::kDownloadInvalidMetadataSize;
    if (mode == "bad-operation-hash") wanted = ErrorCode::kDownloadOperationHashMismatch;
    if (mode == "prepare-fail") wanted = ErrorCode::kNotEnoughSpace;
    if (mode == "open-fail") wanted = ErrorCode::kInstallDeviceOpenError;
    printf("mode=%s accepted=%d error=%d prepares=%u opens=%u consumed=%zu/%zu\n",
           mode.c_str(), accepted, int(error), control->prepares, control->opens, position, stream.size());
    fflush(stdout);
    assert(error == wanted && accepted == (wanted == ErrorCode::kSuccess));
    const int closed = performer.Close();
    if (wanted != ErrorCode::kSuccess || mode.starts_with("truncated-")) {
        if (mode.starts_with("truncated-")) {
            assert(closed < 0);
            assert(performer.VerifyPayload(payload_hash, total_size) == ErrorCode::kPayloadSizeMismatchError);
        }
        assert(!performer.IsManifestValid() || !plan.partitions.empty() || mode == "prepare-fail");
        // Incomplete operation/hash writes nothing; incomplete tail signature
        // can be rejected after the complete operation has already written.
        if (control->opens && !control->deny_open) {
            CowReader reader;
            assert(reader.Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC))));
            size_t written_blocks = 0;
            for (auto it = reader.GetOpIter(); !it->AtEnd(); it->Next()) {
                const auto* item = it->Get();
                if (item->type() == kCowReplaceOp)
                    written_blocks += size_t(1) << item->compression_bits();
            }
            assert(written_blocks == (mode == "truncated-signature" ? 16u : 0u));
        }
        puts(mode == "truncated-signature" ? "PASS rejected-after-data-write" : "PASS rejected-before-data-write");
        return 0;
    }
    assert(closed == 0);
    const auto verify_payload = performer.VerifyPayload(payload_hash, total_size);
    if (mode == "missing-signature") {
        assert(verify_payload == ErrorCode::kSignedDeltaPayloadExpectedError);
        puts("PASS missing-signature-rejected-after-operation");
        return 0;
    }
    assert(verify_payload == ErrorCode::kSuccess);
    assert(control->opens == 1 && control->prepares == 1);
    assert(plan.partitions.size() == 1 && plan.partitions[0].target_hash == target_hash);
    auto reader = std::make_unique<CowReader>();
    assert(reader->Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC)), kEndOfInstallLabel));
    CompressedSnapshotReader view(std::move(reader), std::nullopt, expected.size());
    std::vector<char> actual(expected.size());
    assert(view.Read(actual.data(), actual.size()) == ssize_t(actual.size()));
    assert(view.Close() && actual == expected);
    store("/work/readback.bin", actual);
    store("/work/view.bin", actual);
    brillo::BaseMessageLoop loop; loop.SetAsCurrent();
    ActionProcessor processor; Done delegate; processor.set_delegate(&delegate);
    auto feed = std::make_unique<Feed>(); feed->plan = plan;
    auto verifier = std::make_unique<FilesystemVerifierAction>(control);
    BondActions(feed.get(), verifier.get());
    processor.EnqueueAction(std::move(feed)); processor.EnqueueAction(std::move(verifier));
    processor.StartProcessing(); if (!delegate.completed) loop.Run();
    assert(delegate.completed && delegate.result == ErrorCode::kSuccess);
    assert(control->maps == 1 && control->unmaps == 1);
    puts("PASS stream-to-VABC-to-target-verifier");
}
