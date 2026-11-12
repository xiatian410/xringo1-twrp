#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sys/wait.h>
#include <unistd.h>
#include "backup_manifest.hpp"

namespace fs = std::filesystem;
namespace bm = twrp_backup_manifest;
#define CHECK(x) do { if (!(x)) { std::cerr << "FAIL line " << __LINE__ << ": " << #x << '\n'; return 1; } } while (0)
static void put(const fs::path& p, const std::string& s) {
  std::ofstream f(p, std::ios::binary); f << s; assert(f.good());
}
int main(int argc, char** argv) {
  CHECK(argc == 2);
  const std::string mode = argv[1];
  const fs::path root = fs::current_path(), folder = root / "backup";
  CHECK(root.string().starts_with("/tmp/dijun-manifest-"));
  fs::create_directory(folder);
  if (mode == "legacy") {
    put(folder / "data.ext4.win000", "archive");
    CHECK(bm::Validate(folder));
    return 0;
  }
  if (mode.starts_with("crash-")) {
    const pid_t child = fork(); CHECK(child >= 0);
    if (!child) {
      bm::Session session;
      if (!session.Begin(folder)) _exit(9);
      if (mode != "crash-marker") put(folder / "data.ext4.win000", "partial");
      if (mode == "crash-complete" && !session.Commit({"data.ext4.win000"})) _exit(8);
      _exit(0);
    }
    int status = 0; CHECK(waitpid(child, &status, 0) == child && status == 0);
    CHECK(bm::Validate(folder) == (mode == "crash-complete"));
    return 0;
  }
  bm::Session session;
  CHECK(session.Begin(folder));
  CHECK(!bm::Validate(folder));
  put(folder / "data.ext4.win000", "part zero");
  put(folder / "data.ext4.win001", "part one");
  put(folder / "data.info", "metadata");
  put(folder / "recovery.log", "post-commit diagnostic");
  if (mode == "missing-required") CHECK(!session.Commit({"absent.win"}));
  else CHECK(session.Commit({"data.ext4.win000", "data.ext4.win001"}));
  if (mode == "missing-required") { CHECK(!bm::Validate(folder)); return 0; }
  CHECK(bm::Validate(folder));
  if (mode == "missing-tail") fs::remove(folder / "data.ext4.win001");
  if (mode == "short-tail") put(folder / "data.ext4.win001", "short");
  if (mode == "extra-file") put(folder / "extra", "added");
  if (mode == "symlink-payload") {
    fs::remove(folder / "data.ext4.win001");
    fs::create_symlink(folder / "data.ext4.win000", folder / "data.ext4.win001");
  }
  if (mode == "fifo-payload") {
    fs::remove(folder / "data.ext4.win001");
    CHECK(mkfifo((folder / "data.ext4.win001").c_str(), 0600) == 0);
  }
  if (mode == "unknown-version")
    put(folder / bm::kName, "TWRP-BACKUP-MANIFEST 2\nCOMPLETE\n");
  if (mode == "duplicate")
    put(folder / bm::kName, std::string(bm::kHeader) + "COMPLETE\n9\tdata.ext4.win000\n9\tdata.ext4.win000\n");
  if (mode == "traversal")
    put(folder / bm::kName, std::string(bm::kHeader) + "COMPLETE\n9\t../escape\n");
  if (mode == "truncated-record")
    put(folder / bm::kName, std::string(bm::kHeader) + "COMPLETE\n9\tdata.ext4.win000");
  if (mode == "manifest-symlink") {
    fs::rename(folder / bm::kName, root / "saved-manifest");
    fs::create_symlink(root / "saved-manifest", folder / bm::kName);
  }
  if (mode == "legacy-after-delete") fs::remove(folder / bm::kName);
  const bool expected = mode == "valid" || mode == "legacy-after-delete";
  CHECK(bm::Validate(folder) == expected);
  std::cout << "PASS: production manifest with real private files\n";
}
