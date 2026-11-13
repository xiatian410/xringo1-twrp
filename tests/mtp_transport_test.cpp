// Exercise TWRP's real FFS implementations using pipes and disposable files.
// USB endpoint ioctls naturally take their documented fallback on pipes.
#include <cassert>
#include <atomic>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <string>
#include <sys/stat.h>
#include <poll.h>
#include <asyncio/AsyncIO.h>
#include <type_traits>
#include <vector>
#include <unistd.h>
#include <android-base/properties.h>
#include "MtpDescriptors.h"
#include "MtpFfsHandle.h"
#include "MtpFfsCompatHandle.h"

static aio_context_t fault_context = 0;
static std::atomic<int> getevents_fault{0};
static std::atomic<int> getevents_calls{0};
static std::atomic<int> completion_fault{0};
static std::atomic<int> completion_skip{0};
extern "C" int __real_io_getevents(aio_context_t,long,long,io_event*,timespec*);
extern "C" int __wrap_io_getevents(aio_context_t ctx,long min,long max,io_event* events,timespec* timeout) {
    if (ctx == fault_context) {
        ++getevents_calls;
        if (const int error = getevents_fault.exchange(0)) { errno = error; return -1; }
    }
    const int result = __real_io_getevents(ctx,min,max,events,timeout);
    if (ctx == fault_context && result > 0) {
        if (completion_skip > 0) --completion_skip;
        else if (const int error = completion_fault.exchange(0)) {
            events[0].res = error == -1 ? events[0].res - 1 : -error;
        }
    }
    return result;
}
static int fault_fd = -1;
static bool short_write = false;
static std::atomic<int> full_file_fd{-1};
static std::atomic<int> read_fault_fd{-1};
static std::atomic<int> read_fault{0};
extern "C" ssize_t __real_pread64(int, void*, size_t, off64_t);
extern "C" ssize_t __wrap_pread64(int fd, void* data, size_t length, off64_t offset) {
    if (fd == read_fault_fd.load()) {
        if (const int error = read_fault.exchange(0)) {
            if (error == -1) return __real_pread64(fd, data, length - 1, offset);
            errno = error; return -1;
        }
    }
    return __real_pread64(fd, data, length, offset);
}
static std::atomic<int> write_fault_after{-1};
extern "C" ssize_t __real_pwrite64(int, const void*, size_t, off64_t);
extern "C" ssize_t __wrap_pwrite64(int fd, const void* data, size_t length, off64_t offset) {
    if (fd == full_file_fd.load()) { errno = ENOSPC; return -1; }
    return __real_pwrite64(fd, data, length, offset);
}
extern "C" ssize_t __real_write(int, const void*, size_t);
extern "C" ssize_t __wrap_write(int fd, const void* data, size_t length) {
    if (fd == fault_fd) {
        if (write_fault_after > 0) { --write_fault_after; return __real_write(fd, data, length); }
        if (short_write) return length ? length - 1 : 0;
        errno = EIO;
        return -1;
    }
    return __real_write(fd, data, length);
}

static void require(bool condition, const char* message) {
    if (!condition) { std::cerr << "FAIL: " << message << std::endl; std::exit(1); }
}

namespace android {
template<class T> class MtpFfsHandleTest {
    T handle{-1};
    base::unique_fd control, bulk_in, bulk_out, interrupt;
public:
    MtpFfsHandleTest() {
        int fds[2];
        require(pipe(fds) == 0, "control pipe");
        control.reset(fds[0]); handle.mControl.reset(fds[1]);
        require(pipe(fds) == 0, "bulk in pipe");
        require(fcntl(fds[0], F_SETPIPE_SZ, 1048576) == 1048576, "pipe capacity");
        bulk_in.reset(fds[0]); handle.mBulkIn.reset(fds[1]);
        require(pipe(fds) == 0, "bulk out pipe");
        require(fcntl(fds[0], F_SETPIPE_SZ, 1048576) == 1048576, "pipe capacity");
        bulk_out.reset(fds[1]); handle.mBulkOut.reset(fds[0]);
        require(pipe(fds) == 0, "interrupt pipe");
        interrupt.reset(fds[0]); handle.mIntr.reset(fds[1]);
    }
    ~MtpFfsHandleTest() { handle.close(); }

    void descriptors(bool ptp) {
        base::test_properties.clear();
        require(handle.start(ptp) == 0, "start transport");
        require(base::test_properties["sys.usb.ffs.mtp.ready"] == "1", "ready after start");
        desc_v2 descriptors{};
        functionfs_strings strings{};
        require(::read(control, &descriptors, sizeof(descriptors)) == sizeof(descriptors), "startup descriptors");
        require(::read(control, &strings, sizeof(strings)) == sizeof(strings), "startup strings");
        require(memcmp(&descriptors, ptp ? &ptp_desc_v2 : &mtp_desc_v2, sizeof(descriptors)) == 0, "MTP/PTP descriptors");
        require(memcmp(&strings, &mtp_strings, sizeof(strings)) == 0, "FFS strings");
    }
    void roundtrip(const std::string& path) {
        std::vector<unsigned char> expected(255001), received(expected.size());
        for (size_t i = 0; i < expected.size(); ++i) expected[i] = (i * 17 + 23) % 251;
        require(::write(bulk_out, expected.data(), expected.size()) == static_cast<ssize_t>(expected.size()), "host sends bytes");
        require(handle.read(received.data(), received.size()) == static_cast<int>(received.size()), "bulk read");
        require(received == expected, "bulk read integrity");
        require(handle.write(expected.data(), expected.size()) == static_cast<int>(expected.size()), "bulk write");
        require(::read(bulk_in, received.data(), received.size()) == static_cast<ssize_t>(received.size()), "host reads bytes");
        require(received == expected, "bulk write integrity");

        base::unique_fd file(::open(path.c_str(), O_CREAT|O_EXCL|O_RDWR, 0600));
        require(file >= 0, "exclusive fixture file");
        mtp_file_range range{};
        range.fd = file.get(); range.length = expected.size(); range.offset = 4096;
        require(::write(bulk_out, expected.data(), expected.size()) == static_cast<ssize_t>(expected.size()), "file receive bytes");
        require(handle.receiveFile(range, false) == 0, "receiveFile");
        require(pread(file, received.data(), received.size(), 4096) == static_cast<ssize_t>(received.size()), "received file size");
        require(received == expected, "receiveFile content at requested offset");
        range.command = 0x1009; range.transaction_id = 0x12345678;
        require(handle.sendFile(range) == 0, "sendFile");
        mtp_data_header header{};
        require(::read(bulk_in, &header, sizeof(header)) == sizeof(header), "sendFile header");
        require(header.type == 2 && header.command == range.command && header.transaction_id == range.transaction_id &&
                header.length == expected.size() + sizeof(header), "transaction header values");
        require(::read(bulk_in, received.data(), received.size()) == static_cast<ssize_t>(received.size()), "sendFile body");
        require(received == expected, "sendFile integrity");
        range.length = 0;
        require(handle.receiveFile(range, false) == 0, "zero-length receive");
        range.fd = -1; range.length = 10;
        require(handle.sendFile(range) == -1, "invalid source descriptor rejected");
        range.fd = file.get(); range.length = 17;
        require(::write(bulk_out, expected.data(), range.length) == 17, "disk-full input");
        full_file_fd = file.get();
        require(handle.receiveFile(range, false) == -1, "ENOSPC receive rejected");
        require(errno == ENOSPC, "disk-full errno preserved");
        full_file_fd = -1;
        if constexpr (std::is_same_v<T, MtpFfsCompatHandle>) {
            require(ftruncate(file, 0) == 0, "truncate disposable fixture");
            range.length = 0xffffffffU; range.offset = 0;
            require(::write(bulk_out, expected.data(), expected.size()) == static_cast<ssize_t>(expected.size()), "unknown-length input");
            require(handle.receiveFile(range, false) == 0, "unknown-length receive");
            struct stat info{};
            require(fstat(file, &info) == 0 && info.st_size == static_cast<off_t>(expected.size()), "unknown-length file contains only received bytes");
            require(pread(file, received.data(), received.size(), 0) == static_cast<ssize_t>(received.size()) && received == expected, "unknown-length integrity");
        }
        std::cout << "PASS: bulk and file roundtrip, offsets, header, empty file, bad source, ENOSPC" << std::endl;
    }
    void completion_error(const std::string& mode) {
        fault_context = handle.mCtx;
        getevents_calls = 0;
        getevents_fault = mode == "completion-eintr" ? EINTR :
                          mode == "completion-eagain" ? EAGAIN : EIO;
        const int expected_error = getevents_fault;
        const int result = handle.write("abcdefg", 7);
        if (mode == "completion-eintr") {
            require(result == 7 && getevents_calls >= 2, "completion EINTR retries");
            char data[7];
            require(::read(bulk_in,data,7)==7 && memcmp(data,"abcdefg",7)==0, "retry content");
        } else {
            require(result == -1 && errno == expected_error, "completion error preserved");
        }
        // close destroys the AIO context before releasing its request buffers.
        // No claim of continued traffic after an unconsumed completion error.
        handle.close();
        fault_context = 0;
        std::cout << "PASS: " << mode << " calls=" << getevents_calls << " result=" << result << std::endl;
    }
    void send_error(const std::string& path, const std::string& mode) {
        base::unique_fd file(::open(path.c_str(), O_CREAT|O_EXCL|O_RDWR, 0600));
        require(file >= 0, "send fixture");
        std::vector<unsigned char> content(250017, 0x65);
        require(::write(file, content.data(), content.size()) == static_cast<ssize_t>(content.size()), "fixture content");
        mtp_file_range range{};
        range.fd = file; range.length = content.size(); range.command = 0x1009;
        range.transaction_id = 7;
        const bool disk = mode.find("disk") != std::string::npos;
        const bool short_io = mode.find("short") != std::string::npos;
        if (disk) { read_fault_fd = file.get(); read_fault = short_io ? -1 : EIO; }
        else if constexpr (std::is_same_v<T, MtpFfsHandle>) {
            fault_context = handle.mCtx;
            // The first completion carries the header. Fail the later body.
            completion_skip = 1; completion_fault = short_io ? -1 : EIO;
        } else { fault_fd = handle.mBulkIn; write_fault_after = 1; short_write = short_io; }
        const int result = handle.sendFile(range);
        const int saved_errno = errno;
        read_fault_fd = -1; read_fault = 0; fault_fd = -1; fault_context = 0;
        write_fault_after = -1; completion_fault = 0; completion_skip = 0;
        require(result == -1 && saved_errno == EIO, "send failure returns -1/EIO");
        require(!handle.mCanceled || disk, "disk cancellation only");
        std::cout << "PASS: " << mode << " result=" << result << " errno=" << saved_errno << std::endl;
    }
    void disconnected() {
        bulk_out.reset();
        char byte = 0;
        require(handle.read(&byte, 1) == 0, "disconnected input EOF");
        bulk_in.reset();
        require(handle.write("x", 1) == -1, "disconnected output error");
    }
    void closed() {
        handle.close();
        require(base::test_properties["sys.usb.ffs.mtp.ready"] == "0", "ready cleared on close");
    }
    void bad_start(bool partial) {
        base::test_properties["sys.usb.ffs.mtp.ready"] = "1"; // stale prior attempt
        fault_fd = handle.mControl.get(); short_write = partial;
        require(handle.start(false) == -1, "descriptor failure rejected");
        require(base::test_properties["sys.usb.ffs.mtp.ready"] == "0", "failure cannot retain readiness");
        fault_fd = -1;
    }
};
}

template<class T> void run(const std::string& prefix) {
    { android::MtpFfsHandleTest<T> test; test.descriptors(false); test.roundtrip(prefix); test.disconnected(); test.closed(); }
    { android::MtpFfsHandleTest<T> test; test.descriptors(true); test.closed(); }
    { android::MtpFfsHandleTest<T> test; test.bad_start(false); }
    { android::MtpFfsHandleTest<T> test; test.bad_start(true); }
}
int main(int argc, char** argv) {
    require(argc == 2 || argc == 3, "fixture directory argument");
    if (argc == 3) {
        const std::string mode = argv[2];
        if (mode.find("send-") == 0) {
            signal(SIGPIPE, SIG_IGN);
            if (mode.find("compat") != std::string::npos) {
                android::MtpFfsHandleTest<android::MtpFfsCompatHandle> test;
                test.descriptors(false); test.send_error(std::string(argv[1])+"/send-file", mode);
            } else {
                android::MtpFfsHandleTest<android::MtpFfsHandle> test;
                test.descriptors(false); test.send_error(std::string(argv[1])+"/send-file", mode);
            }
            return 0;
        }
        android::MtpFfsHandleTest<android::MtpFfsHandle> test;
        test.descriptors(false); test.completion_error(argv[2]); return 0;
    }
    signal(SIGPIPE, SIG_IGN);
    run<android::MtpFfsHandle>(std::string(argv[1]) + "/native-file");
    run<android::MtpFfsCompatHandle>(std::string(argv[1]) + "/compat-file");
    std::cout << "PASS: native AIO and compat FFS startup/close, MTP/PTP, descriptor errors, real file transfer" << std::endl;
}
