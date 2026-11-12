#include <libsnapshot/cow_reader.h>
#include <libsnapshot/cow_writer.h>
#include <fcntl.h>
#include <unistd.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <set>
#include <vector>

using android::base::unique_fd;
using namespace android::snapshot;

int main(int argc, char** argv) {
    assert(argc == 5);
    const uint32_t version = std::stoul(argv[1]);
    const size_t factor = std::stoul(argv[3]);
    const std::string mode = argv[4];
    CowOptions options;
    options.compression = argv[2];
    options.compression_factor = factor;
    options.op_count_max = 128;
    options.max_blocks = 128;
    options.scratch_space = false;
    options.num_compress_threads = 1;
    unique_fd fd(open("/work/test.cow", O_CREAT | O_TRUNC | O_RDWR | O_CLOEXEC, 0600));
    assert(fd >= 0);
    auto writer = CreateCowWriter(version, options, std::move(fd));
    if (mode == "reject-options") {
        assert(!writer);
        puts("PASS rejected unsupported options");
        return 0;
    }
    assert(writer);
    if (mode == "capacity") {
        assert(!writer->AddZeroBlocks(0, 129));
        assert(writer->Finalize());
        puts("PASS rejected operation capacity overflow");
        return 0;
    }
    std::vector<unsigned char> expected(factor);
    for (size_t i = 0; i < expected.size(); ++i)
        expected[i] = (i / 4096 + i % 31) % 251;
    assert(writer->AddRawBlocks(0, expected.data(), expected.size()));
    assert(writer->AddZeroBlocks(32, 2));
    assert(writer->AddLabel(41));
    assert(writer->Finalize());
    writer.reset();
    if (mode == "bad-magic") {
        unique_fd corrupt(open("/work/test.cow", O_RDWR | O_CLOEXEC));
        const char zeros[8] = {};
        assert(pwrite(corrupt, zeros, sizeof(zeros), 0) == sizeof(zeros));
    }
    CowReader reader;
    const bool parsed = reader.Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC)));
    if (mode == "bad-magic") {
        assert(!parsed);
        puts("PASS rejected corrupt COW magic");
        return 0;
    }
    assert(parsed);
    assert(reader.GetHeader().prefix.major_version == version);
    assert(reader.GetHeader().block_size == 4096);
    assert(reader.GetMaxCompressionSize() == factor);
    assert(reader.header_v3().compression_algorithm == kCowCompressLz4);
    // v3 labels live in the resume buffer, not v2's last_label_ field.
    assert(reader.header_v3().resume_point_count == 1);
    CowReader resumed;
    assert(resumed.Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC)), 41));
    CowReader missing_label;
    assert(!missing_label.Parse(unique_fd(open("/work/test.cow", O_RDONLY | O_CLOEXEC)), 42));
    size_t replaced = 0, zeroed = 0;
    std::set<uint64_t> zero_blocks;
    std::vector<unsigned char> readback;
    for (auto iter = reader.GetOpIter(); !iter->AtEnd(); iter->Next()) {
        const auto* op = iter->Get();
        if (op->type() == kCowReplaceOp) {
            const size_t size = size_t(4096) << op->compression_bits();
            assert(op->data_length > 0 && op->data_length < size);
            std::vector<unsigned char> actual(size);
            assert(reader.ReadData(op, actual.data(), actual.size()) == ssize_t(size));
            const size_t offset = op->new_block * 4096;
            assert(offset == replaced && offset + size <= expected.size());
            assert(memcmp(actual.data(), expected.data() + offset, size) == 0);
            readback.insert(readback.end(), actual.begin(), actual.end());
            replaced += size;
        } else if (op->type() == kCowZeroOp) {
            assert(zero_blocks.insert(op->new_block).second);
            ++zeroed;
        }
    }
    assert(replaced == expected.size() && zeroed == 2);
    assert(zero_blocks == std::set<uint64_t>({32, 33}));
    assert(resumed.header_v3().op_count == reader.header_v3().op_count);
    unique_fd output(open("/work/readback.bin", O_CREAT | O_TRUNC | O_WRONLY, 0600));
    assert(write(output, readback.data(), readback.size()) == ssize_t(readback.size()));
    printf("PASS version=%u compression=%s factor=%zu raw_bytes=%zu zero_blocks=%zu label=%llu\n",
           version, argv[2], factor, replaced, zeroed, 41ULL);
}
