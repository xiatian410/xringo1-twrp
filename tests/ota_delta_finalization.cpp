// Original DeltaPerformer translation unit; test-only friend seeds the parsed
// manifest boundary. No signature-parser, device, or VABC implementation claim.
#include "update_engine/payload_consumer/delta_performer.h"
#include "update_engine/payload_consumer/partition_writer_interface.h"
#include "update_engine/common/hash_calculator.h"
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

namespace chromeos_update_engine {
struct Calls {
    unsigned writes = 0, finishes = 0, closes = 0;
    bool write_ok = true, finish_ok = true;
    int close_result = 0;
};
class BoundaryWriter final : public PartitionWriterInterface {
 public:
    explicit BoundaryWriter(Calls* calls) : calls_(calls) {}
    bool Init(const InstallPlan*, bool, size_t) override { assert(false); return false; }
    void CheckpointUpdateProgress(size_t) override { assert(false); }
    int Close() override { ++calls_->closes; return calls_->close_result; }
    bool PerformReplaceOperation(const InstallOperation& op, const void* data, size_t size) override {
        ++calls_->writes;
        assert(op.data_length() == 4096 && size == 4096);
        for (size_t i = 0; i < size; ++i) assert(static_cast<const char*>(data)[i] == 'A');
        return calls_->write_ok;
    }
    bool PerformZeroOrDiscardOperation(const InstallOperation&) override { assert(false); return false; }
    bool PerformSourceCopyOperation(const InstallOperation&, ErrorCode*) override { assert(false); return false; }
    bool PerformDiffOperation(const InstallOperation&, ErrorCode*, const void*, size_t) override { assert(false); return false; }
    bool FinishedInstallOps() override { ++calls_->finishes; return calls_->finish_ok; }
 private:
    Calls* calls_;
};
// Uses the existing production friend declaration, without redefining private.
class DeltaPerformerTest {
 public:
    static void Prepare(DeltaPerformer& performer, Calls* calls, bool switching,
                        bool bad_hash, const std::vector<char>& data) {
        performer.manifest_valid_ = true;
        performer.block_size_ = 4096;
        performer.num_total_operations_ = 1;
        performer.current_partition_ = 0;
        performer.next_operation_num_ = 0;
        performer.partitions_.emplace_back().set_partition_name("system");
        if (switching) {
            performer.partitions_.emplace_back().set_partition_name("vendor");
            performer.acc_num_operations_ = {0, 1};
        } else {
            performer.acc_num_operations_ = {1};
        }
        auto* op = performer.partitions_.back().add_operations();
        op->set_type(InstallOperation::REPLACE);
        op->set_data_offset(0);
        op->set_data_length(data.size());
        auto* e = op->add_dst_extents(); e->set_start_block(0); e->set_num_blocks(1);
        brillo::Blob hash;
        assert(HashCalculator::RawHashOfBytes(data.data(), data.size(), &hash));
        if (bad_hash) hash[0] ^= 1;
        op->set_data_sha256_hash(hash.data(), hash.size());
        performer.partition_writer_ = std::make_unique<BoundaryWriter>(calls);
    }
    static size_t Next(const DeltaPerformer& p) { return p.next_operation_num_; }
};
}  // namespace chromeos_update_engine

using namespace chromeos_update_engine;
int main(int argc, char** argv) {
    assert(argc == 2);
    const std::string mode = argv[1];
    const bool switching = mode.starts_with("switch-");
    Calls calls;
    calls.write_ok = mode != "operation-fail";
    calls.finish_ok = mode != "final-finish-fail" && mode != "switch-finish-fail";
    calls.close_result = mode == "final-close-fail" || mode == "switch-close-fail" ? -EIO : 0;
    InstallPlan plan;
    plan.hash_checks_mandatory = true;
    InstallPlan::Payload payload;
    payload.size = 4096;
    DeltaPerformer performer(nullptr, nullptr, nullptr, nullptr, &plan, &payload, false);
    const std::vector<char> data(4096, 'A');
    DeltaPerformerTest::Prepare(performer, &calls, switching, mode == "hash-fail", data);
    ErrorCode error = ErrorCode::kError;
    bool result;
    if (mode == "chunked") {
        result = performer.Write(data.data(), 123, &error);
        assert(result && error == ErrorCode::kSuccess && calls.writes == 0 && calls.finishes == 0);
        result = performer.Write(data.data()+123, data.size()-123, &error);
    } else {
        result = performer.Write(data.data(), data.size(), &error);
    }
    const bool expected = mode == "success" || mode == "chunked";
    ErrorCode wanted = ErrorCode::kSuccess;
    if (mode == "operation-fail") wanted = ErrorCode::kDownloadOperationExecutionError;
    else if (mode == "hash-fail") wanted = ErrorCode::kDownloadOperationHashMismatch;
    else if (!expected) wanted = ErrorCode::kDownloadWriteError;
    // Print before assertions to retain the actual old behavior in the report.
    printf("mode=%s write_return=%d error=%d writes=%u finish=%u close=%u next=%zu\n",
           mode.c_str(), result, int(error), calls.writes, calls.finishes, calls.closes,
           DeltaPerformerTest::Next(performer));
    fflush(stdout);
    assert(result == expected && error == wanted);
    assert(calls.writes == (switching || mode == "hash-fail" ? 0u : 1u));
    assert(calls.finishes == (mode == "operation-fail" || mode == "hash-fail" ? 0u : 1u));
    assert(calls.closes == (calls.finishes && calls.finish_ok ? 1u : 0u));
    assert(DeltaPerformerTest::Next(performer) == (switching || mode == "hash-fail" || mode == "operation-fail" ? 0u : 1u));
    // Explicit cleanup after observing the error; no further operations allowed.
    performer.CloseCurrentPartition();
    puts("PASS");
}
