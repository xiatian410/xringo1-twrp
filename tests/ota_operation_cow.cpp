#include <libsnapshot/cow_reader.h>
#include <libsnapshot/cow_writer.h>
#include "update_engine/payload_consumer/install_operation_executor.h"
#include "update_engine/payload_consumer/snapshot_extent_writer.h"
#include <xz.h>
#include <fcntl.h>
#include <unistd.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <set>
#include <string>
#include <vector>

using android::base::unique_fd;
using namespace android::snapshot;
using namespace chromeos_update_engine;

static std::vector<char> load(const char* path) {
    std::ifstream stream(path, std::ios::binary);
    assert(stream.good());
    return {std::istreambuf_iterator<char>(stream), {}};
}

// Execute exact serialized stock operations and destination extents. Expected
// bytes are independently sliced from the hash-verified extracted partition.
static int stock_operation() {
    auto protobuf = load("/work/operation.pb");
    InstallOperation operation;
    assert(operation.ParseFromArray(protobuf.data(), protobuf.size()));
    auto input = load("/work/input.bin");
    auto expected = load("/work/expected.bin");
    assert(input.size() == operation.data_length());
    uint64_t max_blocks = 0, output_size = 0;
    for (const auto& e : operation.dst_extents()) {
        assert(e.num_blocks() && e.start_block() + e.num_blocks() >= e.start_block());
        max_blocks = std::max(max_blocks, e.start_block() + e.num_blocks());
        output_size += e.num_blocks() * 4096;
    }
    assert(output_size == expected.size() && output_size <= 8 * 1024 * 1024);
    CowOptions options;
    options.compression = "lz4"; options.compression_factor = 65536;
    options.op_count_max = max_blocks + 128; options.max_blocks = max_blocks;
    options.scratch_space = false; options.num_compress_threads = 1;
    auto writer = CreateCowWriter(3, options,
        unique_fd(open("/work/test.cow", O_CREAT | O_TRUNC | O_RDWR | O_CLOEXEC, 0600)));
    assert(writer);
    InstallOperationExecutor executor(4096);
    assert(executor.ExecuteReplaceOperation(operation,
        std::make_unique<SnapshotExtentWriter>(writer.get()), input.data()));
    assert(writer->Finalize()); writer.reset();
    CowReader reader;
    assert(reader.Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC))));
    std::vector<char> actual(expected.size(), '\0');
    std::set<uint64_t> blocks;
    for (auto it = reader.GetOpIter(); !it->AtEnd(); it->Next()) {
        const auto* op = it->Get();
        assert(op->type() == kCowReplaceOp);
        size_t size = size_t(4096) << op->compression_bits();
        size_t offset = 0; bool found = false;
        for (const auto& e : operation.dst_extents()) {
            if (op->new_block >= e.start_block() &&
                op->new_block + size / 4096 <= e.start_block() + e.num_blocks()) {
                offset += (op->new_block - e.start_block()) * 4096;
                found = true; break;
            }
            offset += e.num_blocks() * 4096;
        }
        assert(found && offset + size <= actual.size());
        assert(reader.ReadData(op, actual.data() + offset, size) == ssize_t(size));
        for (size_t b = 0; b < size / 4096; ++b) assert(blocks.insert(op->new_block + b).second);
    }
    assert(actual == expected && blocks.size() * 4096 == expected.size());
    unique_fd output(open("/work/readback.bin", O_CREAT | O_TRUNC | O_WRONLY, 0600));
    assert(write(output, actual.data(), actual.size()) == ssize_t(actual.size()));
    printf("PASS stock type=%d input=%zu output=%zu blocks=%zu\n",
        int(operation.type()), input.size(), actual.size(), blocks.size());
    return 0;
}

int main(int argc, char** argv) {
    if (argc == 2 && std::string(argv[1]) == "stock") {
        xz_crc32_init(); return stock_operation();
    }
    assert(argc == 5);
    xz_crc32_init();
    const auto type = static_cast<InstallOperation::Type>(std::stoul(argv[1]));
    const std::string mode = argv[4];
    auto data = load("/work/input.bin");
    const auto expected = load("/work/expected.bin");
    assert(expected.size() == 65536);
    InstallOperation operation;
    operation.set_type(type);
    operation.set_data_length(data.size());
    for (const uint64_t start : {0, 24}) {
        auto* extent = operation.add_dst_extents();
        extent->set_start_block(start);
        extent->set_num_blocks(8);
    }
    CowOptions options;
    options.compression = argv[2];
    options.compression_factor = std::stoul(argv[3]);
    options.op_count_max = 128;
    options.max_blocks = mode == "target-overflow" ? 16 : 128;
    options.scratch_space = false;
    options.num_compress_threads = 1;
    auto writer = CreateCowWriter(3, options,
        unique_fd(open("/work/test.cow", O_CREAT | O_TRUNC | O_RDWR | O_CLOEXEC, 0600)));
    assert(writer);
    InstallOperationExecutor executor(4096);
    const bool executed = executor.ExecuteReplaceOperation(operation,
        std::make_unique<SnapshotExtentWriter>(writer.get()), data.data());
    const bool want_success = mode == "roundtrip" || mode == "short-raw";
    assert(executed == want_success);
    assert(writer->Finalize());
    writer.reset();
    CowReader reader;
    assert(reader.Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC))));
    std::vector<char> actual(65536, '\0');
    std::set<size_t> blocks;
    for (auto it = reader.GetOpIter(); !it->AtEnd(); it->Next()) {
        auto* op = it->Get();
        assert(op->type() == kCowReplaceOp);
        const size_t size = size_t(4096) << op->compression_bits();
        const size_t destination = op->new_block * 4096;
        const size_t offset = destination < 32768 ? destination : destination - 65536;
        assert(destination < 32768 || (destination >= 98304 && destination < 131072));
        assert(offset + size <= actual.size());
        assert(reader.ReadData(op, actual.data() + offset, size) == ssize_t(size));
        for (size_t i = 0; i < size / 4096; ++i)
            assert(blocks.insert(op->new_block + i).second);
    }
    if (mode == "roundtrip") {
        assert(actual == expected && blocks.size() == 16);
        for (size_t i = 0; i < 8; ++i) assert(blocks.contains(i) && blocks.contains(24 + i));
    } else if (mode == "short-raw") {
        // Operation-level true means input consumed, not full extents filled.
        // No 1 MiB extent buffer flush occurs for a 4096-byte short input.
        assert(executed && blocks.empty() && actual != expected);
        assert(actual == std::vector<char>(65536, '\0'));
    } else if (mode == "target-overflow" || mode == "oversize-raw") {
        assert(!executed && !blocks.empty());
        assert(actual != expected || mode == "oversize-raw");
        if (mode == "target-overflow") {
            assert(blocks.size() == 8);
            assert(memcmp(actual.data(), expected.data(), 32768) == 0);
            assert(std::vector<char>(actual.begin() + 32768, actual.end()) ==
                   std::vector<char>(32768, '\0'));
        } else {
            assert(blocks.size() == 16 && actual == expected);
        }
    } else {
        assert(!executed && blocks.empty());
    }
    unique_fd output(open("/work/readback.bin", O_CREAT | O_TRUNC | O_WRONLY, 0600));
    assert(write(output, actual.data(), actual.size()) == ssize_t(actual.size()));
    printf("PASS mode=%s type=%d operation_return=%d stored_blocks=%zu complete=%d\n",
           mode.c_str(), int(type), executed, blocks.size(), actual == expected);
}
