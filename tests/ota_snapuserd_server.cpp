// SPDX-License-Identifier: Apache-2.0
// Real server public Start/Run with private Unix sockets; no snapshot handlers.
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cstdio>
#include <cstring>
#include <string>

#include <android-base/logging.h>
#include <android-base/unique_fd.h>
#include "snapuserd_server.h"

using android::base::unique_fd;
using android::snapshot::UserSnapshotServer;

static bool ready(int fd) {
    pollfd p{fd, POLLIN, 0};
    return TEMP_FAILURE_RETRY(poll(&p, 1, 2000)) > 0;
}
static unique_fd connect_peer() {
    unique_fd fd(socket(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0));
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, "/dev/socket/offline-snapuserd");
    if (fd < 0 || connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr))) return {};
    return fd;
}
static bool send_text(int fd, const std::string& value) {
    return TEMP_FAILURE_RETRY(send(fd, value.data(), value.size(), MSG_NOSIGNAL)) ==
           static_cast<ssize_t>(value.size());
}
static bool response(int fd, const std::string& expected) {
    if (!ready(fd)) return false;
    char buf[512];
    ssize_t size = TEMP_FAILURE_RETRY(recv(fd, buf, sizeof(buf), 0));
    return size >= 0 && std::string(buf, size) == expected;
}

int main(int argc, char** argv) {
    android::base::InitLogging(argv, android::base::StderrLogger);
    if (argc != 2) return 2;
    const std::string name = argv[1];
    int pipefd[2];
    if (pipe(pipefd)) return 2;
    unique_fd pipe_read(pipefd[0]), pipe_write(pipefd[1]);
    pid_t child = fork();
    if (child < 0) return 2;
    if (!child) {
        pipe_read.reset();
        UserSnapshotServer server;
        if (!server.Start("offline-snapuserd")) _exit(3);
        if (write(pipe_write, "1", 1) != 1) _exit(4);
        pipe_write.reset();
        bool ok = server.Run();
        _exit(ok ? 0 : 5);
    }
    pipe_write.reset();
    char marker = 0;
    bool ok = ready(pipe_read) && read(pipe_read, &marker, 1) == 1 && marker == '1';
    unique_fd peer = ok ? connect_peer() : unique_fd();
    ok = ok && peer >= 0;
    if (ok && (name == "normal-query" || name == "query-then-half-close")) {
        ok = send_text(peer, "query") && response(peer, "active");
    }
    if (ok && (name == "empty-half-close" || name == "query-then-half-close")) {
        ok = shutdown(peer, SHUT_WR) == 0 && response(peer, "");
    } else if (ok && name == "buffered-query-half-close") {
        ok = send_text(peer, "query") && shutdown(peer, SHUT_WR) == 0 &&
             response(peer, "active") && response(peer, "");
    } else if (ok && name == "unknown-command") {
        ok = send_text(peer, "unknown") && response(peer, "fail") && response(peer, "");
    } else if (ok && name == "malformed-delete") {
        ok = send_text(peer, "delete") && response(peer, "fail") &&
             send_text(peer, "query") && response(peer, "active");
    } else if (ok && name == "supports") {
        ok = send_text(peer, "supports,second_stage_socket_handoff") && response(peer, "success") &&
             send_text(peer, "supports,unknown") && response(peer, "fail");
    }
    peer.reset();
    // A fresh connection must still work after the first peer disconnects.
    unique_fd second = ok ? connect_peer() : unique_fd();
    ok = ok && second >= 0 && send_text(second, "query") && response(second, "active") &&
         send_text(second, "stop") && response(second, "");
    second.reset();
    int status = 0;
    // stop closes the socket as the actual Run loop returns; wait is finite in runner.
    if (!ok) kill(child, SIGKILL); // only this fixture's owned child
    bool reaped = TEMP_FAILURE_RETRY(waitpid(child, &status, 0)) == child;
    ok = ok && reaped && WIFEXITED(status) && WEXITSTATUS(status) == 0;
    printf("case=%s server_wait_status=%d second_query=%d result=%s\n", name.c_str(), status,
           static_cast<int>(ok), ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
