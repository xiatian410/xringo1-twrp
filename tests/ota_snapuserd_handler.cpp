// SPDX-License-Identifier: Apache-2.0
// Original client/server/handler. Only size and dm-user open have test doubles.
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <vector>
#include <chrono>
#include <thread>
#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/unique_fd.h>
#include <libsnapshot/cow_writer.h>
#include <libsnapshot/cow_reader.h>
#include <snapuserd/snapuserd_client.h>
#include <snapuserd/snapuserd_kernel.h>
#include "snapuserd_server.h"

using namespace android::snapshot;
using android::base::unique_fd;
static int control_fd = -1;
static bool deny_control = false;
static int size_calls = 0, control_opens = 0;
static dev_t base_dev;
static ino_t base_ino;
static bool fail_write = false, fail_sync = false;
static int injected_writes = 0, injected_syncs = 0;
static int crash_point = 0;
static bool is_base(int fd) {
    struct stat st{};
    return !fstat(fd, &st) && S_ISREG(st.st_mode) && st.st_dev==base_dev && st.st_ino==base_ino;
}
extern "C" ssize_t __real_pwrite(int, const void*, size_t, off_t);
extern "C" int __real_fsync(int);
extern "C" ssize_t __wrap_pwrite(int fd, const void* data, size_t size, off_t off) {
    if (crash_point && crash_point<4 && is_base(fd)) {
        if (crash_point==1) _exit(86);
        size_t amount=crash_point==2 ? 4096 : size;
        ssize_t result=__real_pwrite(fd, data, amount, off);
        if (result!=static_cast<ssize_t>(amount) || __real_fsync(fd)) _exit(87);
        _exit(86);
    }
    if (fail_write && is_base(fd)) { ++injected_writes; errno=EIO; return -1; }
    return __real_pwrite(fd, data, size, off);
}
extern "C" int __wrap_fsync(int fd) {
    if (fail_sync && is_base(fd)) { ++injected_syncs; errno=EIO; return -1; }
    return __real_fsync(fd);
}
extern "C" int __real_msync(void*, size_t, int);
extern "C" int __wrap_msync(void* address, size_t size, int flags) {
    int result=__real_msync(address,size,flags);
    if (crash_point==4 && result==0 && size==4096) {
        auto* header=static_cast<CowHeader*>(address);
        if (header->prefix.magic==kCowMagicNumber && header->num_merge_ops==2) _exit(86);
    }
    return result;
}
extern "C" int __real_open(const char*, int, ...);
extern "C" int __real___open_2(const char*, int);
static int control_open(const char* path) {
    if (strcmp(path, "/dev/dm-user/offline")) return -2;
    ++control_opens;
    if (deny_control) { errno = ENOENT; return -1; }
    return fcntl(control_fd, F_DUPFD_CLOEXEC, 0);
}
extern "C" int __wrap_open(const char* path, int flags, ...) {
    int ctl = control_open(path);
    if (ctl != -2) return ctl;
    mode_t mode = 0;
    if ((flags & O_CREAT) || (flags & O_TMPFILE) == O_TMPFILE) {
        va_list ap; va_start(ap, flags); mode = va_arg(ap, int); va_end(ap);
    }
    return __real_open(path, flags, mode);
}
extern "C" int __wrap___open_2(const char* path, int flags) {
    int ctl = control_open(path);
    return ctl != -2 ? ctl : __real___open_2(path, flags);
}
extern "C" uint64_t __wrap_get_block_device_size(int fd) {
    struct stat st{};
    if (fstat(fd, &st) || !is_base(fd) || st.st_size != 65536) return 0;
    ++size_calls;
    return st.st_size;
}
static bool readable(int fd) {
    pollfd p{fd, POLLIN, 0};
    return TEMP_FAILURE_RETRY(poll(&p, 1, 3000)) > 0;
}
static bool read_block(int fd, uint64_t sector, const std::vector<char>& expected) {
    dm_user_header request{7, DM_USER_REQ_MAP_READ, 0, sector, expected.size()};
    if (!android::base::WriteFully(fd, &request, sizeof(request)) || !readable(fd)) return false;
    dm_user_header reply{};
    if (!android::base::ReadFully(fd, &reply, sizeof(reply)) || reply.seq != 7 ||
        reply.type != DM_USER_RESP_SUCCESS) return false;
    std::vector<char> data(expected.size());
    return readable(fd) && android::base::ReadFully(fd, data.data(), data.size()) && data == expected;
}
static int restart_merge(const std::string& name, const std::vector<char>& initial,
                         const std::vector<char>& expected) {
    const int point=name=="resume-before-write" ? 1 : name=="resume-partial-write" ? 2 : name=="resume-after-write" ? 3 : 4;
    for (int phase=0; phase<2; ++phase) {
        unlink("/dev/socket/offline-snapuserd");
        int sockets[2], pipes[2];
        if (socketpair(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0, sockets) || pipe(pipes)) return 21;
        unique_fd kernel(sockets[0]), daemon(sockets[1]), r(pipes[0]), w(pipes[1]);
        control_fd=daemon.get();
        pid_t child=fork();
        if (child<0) return 22;
        if (!child) {
            kernel.reset(); r.reset(); crash_point=phase==0 ? point : 0;
            UserSnapshotServer server;
            server.Initialize(false);
            if (!server.Start("offline-snapuserd") || write(w,"1",1)!=1) _exit(23);
            w.reset(); bool ok=server.Run(); _exit(ok?0:24);
        }
        daemon.reset(); w.reset(); char marker=0;
        bool ok=readable(r) && read(r,&marker,1)==1 && marker=='1';
        auto client=ok ? SnapuserdClient::Connect("offline-snapuserd", std::chrono::milliseconds(500)) : nullptr;
        ok=ok && bool(client) && client->InitDmUserCow("offline","/work/cow","/work/base","/work/base")==128 &&
           client->AttachDmUser("offline");
        if (phase==1) {
            // Real startup reconstructs scratch BEFORE serving reads or resuming the merge.
            for (size_t block=0; ok && block<4; ++block) {
                ok=read_block(kernel,block*8,std::vector<char>(expected.begin()+block*4096,expected.begin()+(block+1)*4096));
            }
            printf("restart_snapshot_readback=%d\n",int(ok));
        }
        ok=ok && client->InitiateMerge("offline");
        if (phase==1) {
            bool done=false;
            for (int i=0; ok && i<300; ++i) {
                auto state=client->QuerySnapshotStatus("offline");
                if (state=="snapshot-merge-complete") { done=true; break; }
                if (state=="snapshot-merge-failed") { ok=false; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            std::vector<char> content(expected.size());
            unique_fd base(open("/work/base",O_RDONLY));
            ok=ok && done && base>=0 && android::base::ReadFully(base,content.data(),content.size()) && content==expected;
            ok=shutdown(kernel,SHUT_RDWR)==0 && ok;
            ok=ok && client->WaitForDeviceDelete("offline") && client->StopSnapuserd();
            printf("restart_merge_complete=%d whole_base_readback=%d\n",int(done),int(ok));
        }
        if (!ok) kill(child,SIGKILL);
        int status=0;
        bool waited=TEMP_FAILURE_RETRY(waitpid(child,&status,0))==child;
        ok=ok && waited && WIFEXITED(status) && WEXITSTATUS(status)==(phase==0?86:0);
        client.reset();
        CowReader persisted;
        bool parsed=persisted.Parse(unique_fd(open("/work/cow",O_RDONLY)));
        ok=ok && parsed && persisted.GetHeader().num_merge_ops==(phase==0 ? (point==4?2:0) : 4);
        if (phase==0) {
            std::vector<char> content(initial.size()), partial=initial;
            if (point>1) std::copy(expected.begin(),expected.begin()+(point==2?4096:8192),partial.begin());
            unique_fd base(open("/work/base",O_RDONLY)), cow(open("/work/cow",O_RDONLY));
            BufferState state{};
            ok=ok && base>=0 && android::base::ReadFully(base,content.data(),content.size()) && content==partial &&
               cow>=0 && android::base::ReadFullyAtOffset(cow,&state,sizeof(state),persisted.GetHeader().prefix.header_size) &&
               state.read_ahead_state==(point==4?kCowReadAheadInProgress:kCowReadAheadDone);
            printf("crash_point=%d child_exit=%d scratch_state=%d persisted_progress=%llu partial_base_readback=%d\n",point,
                   WIFEXITED(status)?WEXITSTATUS(status):-1,int(state.read_ahead_state),
                   parsed?static_cast<unsigned long long>(persisted.GetHeader().num_merge_ops):999ULL,int(ok));
        } else {
            printf("resume_progress=%llu result=%s\n",parsed?static_cast<unsigned long long>(persisted.GetHeader().num_merge_ops):999ULL,ok?"PASS":"FAIL");
        }
        if (!ok) return 25+phase;
    }
    return 0;
}

int main(int argc, char** argv) {
    android::base::InitLogging(argv, android::base::StderrLogger);
    if (argc != 2) return 2;
    const std::string name = argv[1];
    const bool resume = name.rfind("resume-", 0)==0;
    const bool ordered = name.rfind("ordered-", 0)==0 || resume;
    const bool merge = name.rfind("merge-", 0)==0 || ordered;
    const bool scratch = name=="ordered-scratch" || resume;
    fail_write = name=="merge-write-error" || name=="ordered-write-error";
    fail_sync = name=="merge-sync-error" || name=="ordered-sync-error";
    std::vector<char> raw(4096);
    for (size_t i=0; i<raw.size(); ++i) raw[i] = (i*7)%113;
    std::vector<char> initial(65536, 0x5a), expected_ordered;
    if (ordered) {
        for (size_t i=0; i<initial.size(); ++i) initial[i]=(i/4096*29+i%107)%251;
        expected_ordered=initial;
        std::copy(initial.begin()+4096, initial.begin()+8192, expected_ordered.begin());
        if (name=="ordered-xor") {
            for (size_t i=0; i<4096; ++i) expected_ordered[i]=initial[4096+21+i]^raw[i];
        } else {
            // Swap sources: neither destination may consume already-overwritten data.
            std::copy(initial.begin(), initial.begin()+4096, expected_ordered.begin()+4096);
            if (name!="ordered-copy") {
                for (size_t i=0; i<4096; ++i) expected_ordered[4096+i]=initial[21+i]^raw[i];
                std::copy(raw.begin(), raw.end(), expected_ordered.begin()+8192);
                std::fill(expected_ordered.begin()+12288, expected_ordered.begin()+16384, 0);
            }
        }
    }
    {
        unique_fd base(open("/work/base", O_CREAT|O_RDWR|O_TRUNC, 0600));
        struct stat st{};
        if (base < 0 || !android::base::WriteFully(base, initial.data(), initial.size()) || fstat(base, &st)) return 3;
        base_dev=st.st_dev; base_ino=st.st_ino;
        CowOptions options;
        options.compression = "lz4"; options.compression_factor = 65536;
        options.op_count_max = 128; options.max_blocks = 16; options.num_compress_threads = 1;
        options.scratch_space = scratch;
        unique_fd cow(open("/work/cow", O_CREAT|O_RDWR|O_TRUNC, 0600));
        auto writer = CreateCowWriter(3, options, std::move(cow));
        if (!writer) return 4;
        if (ordered) {
            uint32_t sequence[]={0, 1};
            const size_t ops=name=="ordered-xor" ? 1 : 2;
            if (!writer->AddSequenceData(ops, sequence)) return 4;
            if (name=="ordered-xor") {
                if (!writer->AddXorBlocks(0, raw.data(), raw.size(), 1, 21)) return 4;
            } else {
                if (!writer->AddCopy(0, 1)) return 4;
                if (name=="ordered-copy") {
                    if (!writer->AddCopy(1, 0)) return 4;
                } else {
                    if (!writer->AddXorBlocks(1, raw.data(), raw.size(), 0, 21) ||
                        !writer->AddRawBlocks(2, raw.data(), raw.size()) || !writer->AddZeroBlocks(3, 1)) return 4;
                }
            }
        } else if (!writer->AddRawBlocks(0, raw.data(), raw.size()) || !writer->AddZeroBlocks(1, 1)) return 4;
        if (!writer->Finalize()) return 4;
    }
    if (resume) return restart_merge(name,initial,expected_ordered);
    if (name == "corrupt-cow") {
        unique_fd cow(open("/work/cow", O_RDWR));
        uint64_t zero=0;
        if (pwrite(cow, &zero, sizeof(zero), 0) != sizeof(zero)) return 5;
    }
    int sockets[2], pipes[2];
    if (socketpair(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0, sockets) || pipe(pipes)) return 6;
    unique_fd kernel(sockets[0]), daemon(sockets[1]), ready_read(pipes[0]), ready_write(pipes[1]);
    control_fd = daemon.get(); deny_control = name == "missing-control";
    pid_t child = fork();
    if (child < 0) return 7;
    if (!child) {
        kernel.reset(); ready_read.reset();
        UserSnapshotServer server;
        server.Initialize(false);
        if (!server.Start("offline-snapuserd")) _exit(8);
        if (write(ready_write, "1", 1) != 1) _exit(9);
        ready_write.reset();
        bool result = server.Run();
        printf("server size_calls=%d control_opens=%d injected_writes=%d injected_syncs=%d result=%d\n", size_calls, control_opens, injected_writes, injected_syncs, int(result));
        fflush(stdout); _exit(result ? 0 : 10);
    }
    daemon.reset(); ready_write.reset();
    char marker=0;
    bool ok = readable(ready_read) && read(ready_read, &marker, 1)==1 && marker=='1';
    auto client = ok ? SnapuserdClient::Connect("offline-snapuserd", std::chrono::milliseconds(500)) : nullptr;
    ok = ok && bool(client) && client->SupportsSecondStageSocketHandoff() &&
         !client->SupportsUblk() && client->GetSnapuserdMode()=="dm-user";
    const bool reject = name=="corrupt-cow" || name=="missing-control";
    uint64_t sectors = ok ? client->InitDmUserCow("offline", "/work/cow", "/work/base", "/work/base") : 0;
    ok = ok && sectors == (reject ? 0 : 128);
    if (ok && !reject) {
        ok = client->QuerySnapshotStatus("offline") == "snapshot";
        if (ok && (name=="active-read-delete" || merge)) {
            ok = client->AttachDmUser("offline");
            if (ordered) {
                const size_t blocks=name=="ordered-xor" ? 1 : name=="ordered-copy" ? 2 : 4;
                for (size_t block=0; ok && block<blocks; ++block) {
                    std::vector<char> expected(expected_ordered.begin()+block*4096, expected_ordered.begin()+(block+1)*4096);
                    ok = read_block(kernel, block*8, expected);
                }
            } else {
                ok = ok && read_block(kernel, 0, raw) && read_block(kernel, 8, std::vector<char>(4096));
            }
            if (ok && merge) {
                ok = client->InitiateMerge("offline");
                bool complete = false, failed = false;
                for (int i=0; ok && i<300; ++i) {
                    auto state = client->QuerySnapshotStatus("offline");
                    if (state=="snapshot-merge-complete") { complete=true; break; }
                    if (state=="snapshot-merge-failed") { failed=true; break; }
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                }
                unique_fd base(open("/work/base", O_RDONLY));
                std::vector<char> content(65536), expected(65536, 0x5a);
                if (!fail_write) {
                    std::copy(raw.begin(), raw.end(), expected.begin());
                    std::fill(expected.begin()+4096, expected.begin()+8192, 0);
                }
                if (ordered) {
                    expected=expected_ordered;
                    if (fail_write) expected=initial;
                    if (fail_sync) std::copy(initial.begin()+8192, initial.end(), expected.begin()+8192);
                }
                const bool expected_fail = fail_write || fail_sync;
                ok = ok && complete==!expected_fail && failed==expected_fail && base>=0 &&
                     android::base::ReadFully(base, content.data(), content.size()) && content==expected;
                CowReader persisted;
                bool parsed=persisted.Parse(unique_fd(open("/work/cow", O_RDONLY)));
                const uint64_t wanted = expected_fail ? 0 : ordered && name!="ordered-copy" && name!="ordered-xor" ? 4 : name=="ordered-xor" ? 1 : 2;
                ok = ok && parsed && persisted.GetHeader().num_merge_ops==wanted;
                printf("persisted_merge_ops=%llu expected=%llu\n", parsed ? static_cast<unsigned long long>(persisted.GetHeader().num_merge_ops) : 999ULL, static_cast<unsigned long long>(wanted));
                printf("merge_complete=%d merge_failed=%d independent_base_readback=%d ordered=%d scratch=%d\n", int(complete), int(failed), int(ok), int(ordered), int(scratch));
            }
            // Emulate kernel control removal only after the original worker served reads.
            ok = shutdown(kernel, SHUT_RDWR)==0 && ok;
        }
        ok = ok && client->WaitForDeviceDelete("offline") &&
             client->QuerySnapshotStatus("offline")=="snapshot-merge-failed" && client->WaitForDeviceDelete("offline");
        if (ok && name=="reinitialize") {
            ok = client->InitDmUserCow("offline", "/work/cow", "/work/base", "/work/base")==128 &&
                 client->WaitForDeviceDelete("offline") && client->QuerySnapshotStatus("offline")=="snapshot-merge-failed";
        }
    }
    if (ok && reject) ok = client->WaitForDeviceDelete("offline") && client->QuerySnapshotStatus("offline")=="snapshot-merge-failed";
    ok = ok && client->StopSnapuserd();
    client.reset();
    int status=0;
    if (!ok) kill(child, SIGKILL);
    bool reaped = TEMP_FAILURE_RETRY(waitpid(child, &status, 0))==child;
    ok = ok && reaped && WIFEXITED(status) && WEXITSTATUS(status)==0;
    printf("case=%s init_sectors=%llu read_content=%d server_wait_status=%d result=%s\n",name.c_str(),
           static_cast<unsigned long long>(sectors), int(ok && (name=="active-read-delete" || merge)), status, ok?"PASS":"FAIL");
    return ok?0:1;
}
