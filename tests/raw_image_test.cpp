#include <algorithm>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <format>
#include <fstream>
#include <memory>
#include <string>
#include <vector>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <android-base/unique_fd.h>
#include <android-base/scopeguard.h>

namespace fs=std::filesystem;
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"FAIL line %d: %s (errno=%d)\n",__LINE__,#x,errno); exit(1); } } while(0)
#define LOGINFO(...) printf(__VA_ARGS__)
#define LOGERR(...) printf(__VA_ARGS__)
#define TW_BACKUP_TEXT "backup"
#define TW_RESTORE_TEXT "restore"
constexpr unsigned long long kMiB=1024ULL*1024;
enum class PartitionManagerOp { kBackup=0,kRestore=1 };
struct ProgressTracking {
    uint64_t partition_size=0,bytes=0; bool finished=false;
    void SetPartitionSize(uint64_t n){partition_size=n;}
    void UpdateSize(uint64_t n){CHECK(n>=bytes && n<=partition_size);bytes=n;}
    void UpdateDisplayDetails(bool force){finished=force;}
};
struct PartitionSettings {
    std::string backup_folder="backup"; uint64_t total_restore_size=0;
    PartitionManagerOp pm_method=PartitionManagerOp::kBackup; ProgressTracking *progress=nullptr;
};
struct TWPartitionManager {
    std::atomic_bool stop_backup=false;
    int CheckBackupCancel() const;
} PartitionManager;
namespace gui2_console {
template<class...T> void log_error(T&&...){}
template<class...T> void info(T&&...){}
std::string text(const std::string& s){return s;}
}
namespace TWFunc {
uint64_t GetFileSize(const std::string& s){std::error_code ec;auto n=fs::file_size(s,ec);return ec?0:n;}
template<class...T> void GuiOperationText(T&&...){}
}
struct TWPartition {
    uint64_t backup_size_=2*kMiB+137;
    std::string actual_block_device_="partition.bin",backup_file_name_="partition.emmc.win";
    std::string backup_name_="partition",current_file_system_="emmc",display_name_="fixture",backup_display_name_="fixture";
    bool RawReadWrite(const PartitionSettings*) const;
    bool BackupImage(PartitionSettings*);
    bool RestoreImage(PartitionSettings*);
    std::string GetRestoreFileSystem(PartitionSettings*){return "emmc";}
    bool BlkDiscard() const;
};

static fs::path root;
static std::string scenario;
static dev_t partition_dev; static ino_t partition_ino;
static uint64_t capacity=2*kMiB+137;
static bool fake_block=true,active=false,backing=false;
static unsigned reads,writes,syncs,closes,renames,discards,capacity_calls,metadata_calls;
static uint64_t read_bytes,write_bytes;
static bool injected_read=false,injected_write=false,injected_sync=false;
static std::string fd_path(int fd) {
    char p[64],buf[4096];snprintf(p,sizeof p,"/proc/self/fd/%d",fd);
    ssize_t n=readlink(p,buf,sizeof(buf)-1);if(n<0)return {};buf[n]=0;return buf;
}
static bool is_partition(int fd) {
    struct stat s{};return fstat(fd,&s)==0 && s.st_dev==partition_dev && s.st_ino==partition_ino;
}
static bool owned(const std::string& name) {
    auto p=fs::weakly_canonical(fs::absolute(name));
    return p==root || p.string().starts_with(root.string()+"/");
}
static bool output_fd(int fd) {
    return active && (backing ? fd_path(fd).starts_with((root/"backup").string()+"/") : is_partition(fd));
}
static int fixture_open(const char *path,int flags,...) {
    CHECK(owned(path)); mode_t mode=0;
    if(flags&O_CREAT){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);}
    if(scenario=="directory-open-error" && (flags&O_DIRECTORY)){errno=EACCES;return -1;}
    // Linux ignores O_TRUNC on block devices. Reproduce that behavior for the
    // designated file, rather than inventing an old-code failure on real blocks.
    struct stat st{};
    if(fake_block && stat(path,&st)==0 && st.st_dev==partition_dev && st.st_ino==partition_ino)flags&=~O_TRUNC;
    return open(path,flags,mode);
}
static int fixture_fstat(int fd,struct stat *s) {
    int rc=fstat(fd,s);
    if(rc==0 && fake_block && s->st_dev==partition_dev && s->st_ino==partition_ino) {
        s->st_mode=(s->st_mode&07777)|S_IFBLK;s->st_rdev=1234;
    }
    return rc;
}
static int fixture_ioctl(int fd,unsigned long request,...) {
    CHECK(is_partition(fd)); va_list ap;va_start(ap,request);void *arg=va_arg(ap,void*);va_end(ap);
    if(request==BLKGETSIZE64) {
        ++capacity_calls;
        if(scenario=="capacity-error"){errno=EIO;return -1;}
        if(scenario=="capacity-eintr" && capacity_calls==1){errno=EINTR;return -1;}
        *static_cast<uint64_t*>(arg)=capacity;return 0;
    }
    CHECK(request==BLKDISCARD);++discards;
    if(scenario=="discard-error"){errno=EOPNOTSUPP;return -1;}
    auto *range=static_cast<uint64_t*>(arg);CHECK(range[0]==0 && range[1]==capacity);
    // No block ioctl is executed. Destructive discard is confined to this file.
    CHECK(ftruncate(fd,0)==0);CHECK(ftruncate(fd,capacity)==0);return 0;
}
bool TWPartition::BlkDiscard() const {
    int fd=fixture_open(actual_block_device_.c_str(),O_WRONLY);CHECK(fd>=0);
    uint64_t range[2]={0,capacity};int rc=fixture_ioctl(fd,BLKDISCARD,range);CHECK(close(fd)==0);return rc==0;
}
static ssize_t fixture_read(int fd,void *p,size_t n) {
    CHECK(fd_path(fd).starts_with(root.string()+"/"));++reads;
    if(scenario=="read-eintr" && !injected_read){injected_read=true;errno=EINTR;return -1;}
    if(scenario=="read-zero" && read_bytes){return 0;}
    if(scenario=="read-error" && read_bytes){errno=EIO;return -1;}
    if(scenario=="short-read" || scenario=="cancel-read")n=std::min(n,size_t(4093));
    ssize_t rc=read(fd,p,n);if(rc>0)read_bytes+=rc;
    if(scenario=="cancel-read")PartitionManager.stop_backup=true;
    return rc;
}
static ssize_t fixture_write(int fd,const void *p,size_t n) {
    CHECK(output_fd(fd));++writes;
    if(scenario=="write-eintr" && !injected_write){injected_write=true;errno=EINTR;return -1;}
    if(scenario=="write-zero")return 0;
    if(scenario=="full-disk" && write_bytes){errno=ENOSPC;return -1;}
    if(scenario=="short-write" || scenario=="full-disk" || scenario=="cancel-write")n=std::min(n,size_t(4093));
    ssize_t rc=write(fd,p,n);if(rc>0)write_bytes+=rc;
    if(scenario=="process-exit" && rc>0)_exit(73);
    if(scenario=="cancel-write")PartitionManager.stop_backup=true;
    return rc;
}
static int fixture_fsync(int fd) {
    ++syncs;struct stat st{};CHECK(fstat(fd,&st)==0);
    if((scenario=="sync-error" && !S_ISDIR(st.st_mode)) || (scenario=="directory-sync-error" && S_ISDIR(st.st_mode))){errno=EIO;return -1;}
    if(scenario=="sync-eintr" && !injected_sync){injected_sync=true;errno=EINTR;return -1;}
    return fsync(fd);
}
static int fixture_close(int fd) {
    bool out=output_fd(fd);if(out)++closes;int rc=close(fd);
    if(out && scenario=="cancel-close")PartitionManager.stop_backup=true;
    if(out && scenario=="close-error"){errno=EIO;return -1;}
    return rc;
}
static int fixture_rename(const char *from,const char *to) {
    CHECK(owned(from)&&owned(to));++renames;
    if(scenario=="rename-error"){errno=EIO;return -1;}
    int rc=rename(from,to);if(scenario=="commit-exit" && rc==0)_exit(74);return rc;
}
static int fixture_mkstemp(char *path){CHECK(owned(path));return mkstemp(path);}
static int tw_set_default_metadata(const char *path) {
    CHECK(owned(path));++metadata_calls;return scenario=="optional-metadata-error"?-1:0;
}

#define open fixture_open
#define fstat fixture_fstat
#define ioctl fixture_ioctl
#define read fixture_read
#define write fixture_write
#define fsync fixture_fsync
#define close fixture_close
#define rename fixture_rename
#define mkstemp fixture_mkstemp
// PRODUCTION_METHODS
#undef open
#undef fstat
#undef ioctl
#undef read
#undef write
#undef fsync
#undef close
#undef rename
#undef mkstemp

static std::string bytes(size_t n,unsigned seed) {
    std::string s(n,' ');for(size_t i=0;i<n;++i)s[i]=char((i*97+seed)%251);return s;
}
static void put(const fs::path& path,const std::string& data){std::ofstream f(path,std::ios::binary|std::ios::trunc);f.write(data.data(),data.size());CHECK(f.good());}
static std::string get(const fs::path& path){std::ifstream f(path,std::ios::binary);CHECK(f.good());return {std::istreambuf_iterator<char>(f),{}};}
static void no_temporary_files(){for(const auto& f:fs::directory_iterator("backup"))CHECK(f.path().filename()=="partition.emmc.win");}
int main(int argc,char **argv) {
    CHECK(argc==3);root=fs::canonical(fs::current_path());CHECK(root.string().starts_with("/tmp/dijun-raw-"));CHECK(fs::exists(".fixture"));
    backing=std::string(argv[1])=="backup";scenario=argv[2];
    CHECK(backing || std::string(argv[1])=="restore");
    fs::create_directory("backup");
    std::string partition=bytes(capacity,31), image=bytes(capacity-131,47),old_backup="previous complete backup";
    put("partition.bin",partition);put("backup/partition.emmc.win",backing?old_backup:image);
    struct stat st{};CHECK(stat("partition.bin",&st)==0);partition_dev=st.st_dev;partition_ino=st.st_ino;
    ProgressTracking progress;PartitionSettings settings;settings.progress=&progress;settings.pm_method=backing?PartitionManagerOp::kBackup:PartitionManagerOp::kRestore;
    TWPartition part;bool expected=true,preflight=false;
    if(scenario=="no-progress")settings.progress=nullptr;
    if(scenario=="cached-size-low")part.backup_size_=17;
    if(scenario=="cached-size-high")part.backup_size_=capacity+17;
    if(scenario=="oversized"){image=bytes(capacity+1,47);put("backup/partition.emmc.win",image);expected=false;preflight=true;}
    if(scenario=="empty-image"){put("backup/partition.emmc.win","");expected=false;preflight=true;}
    if(scenario=="zero-capacity"){capacity=0;expected=false;preflight=true;}
    if(scenario=="capacity-error" || scenario=="directory-open-error"){expected=false;preflight=true;}
    if(scenario=="missing-source"){fs::remove(backing?"partition.bin":"backup/partition.emmc.win");expected=false;preflight=true;}
    if(scenario=="missing-target"){fs::remove("partition.bin");expected=false;preflight=true;}
    if(scenario=="ordinary-file"){fake_block=false;expected=false;preflight=true;}
    if(scenario=="block-alias"){fs::create_symlink("partition.bin","by-name");part.actual_block_device_="by-name";}
    if(scenario=="backup-symlink"){put("other.bin",old_backup);fs::remove("backup/partition.emmc.win");fs::create_symlink("../other.bin","backup/partition.emmc.win");expected=false;preflight=true;}
    if(scenario=="same-source"){fs::remove("backup/partition.emmc.win");fs::create_hard_link("partition.bin","backup/partition.emmc.win");expected=false;preflight=true;}
    if(scenario=="cancel-before"){PartitionManager.stop_backup=true;expected=false;preflight=true;}
    for(const auto *s:{"read-zero","read-error","write-zero","full-disk","sync-error","close-error","rename-error","directory-sync-error","cancel-read","cancel-write","cancel-close"})if(scenario==s)expected=false;
    active=true;
    bool rc=backing?part.BackupImage(&settings):part.RestoreImage(&settings);
    active=false;
    CHECK(rc==expected);
    if(scenario=="roundtrip") {
        CHECK(backing && rc && get("backup/partition.emmc.win")==partition);
        put("partition.bin",bytes(partition.size(),99));
        progress=ProgressTracking{};backing=false;settings.pm_method=PartitionManagerOp::kRestore;
        active=true;rc=part.RestoreImage(&settings);active=false;
        CHECK(rc);image=partition;
    }
    if(preflight || scenario=="cancel-read"){CHECK(writes==0);CHECK(discards==0);}
    if(backing) {
        if(scenario=="same-source")CHECK(get("partition.bin")==partition);
        else if(scenario=="backup-symlink"){CHECK(fs::is_symlink("backup/partition.emmc.win"));CHECK(get("other.bin")==old_backup);}
        else if(rc || scenario=="directory-sync-error")CHECK(get("backup/partition.emmc.win")==partition);
        else CHECK(get("backup/partition.emmc.win")==old_backup);
        no_temporary_files();
    } else {
        if(scenario=="missing-target")CHECK(!fs::exists("partition.bin"));
        else if(preflight || scenario=="cancel-read")CHECK(get("partition.bin")==partition);
        else if(rc) {
            auto result=get("partition.bin");CHECK(result.size()==partition.size());CHECK(result.substr(0,image.size())==image);
#ifndef TW_ENABLE_BLKDISCARD
            CHECK(result.substr(image.size())==partition.substr(image.size()));
#endif
        }
#ifndef TW_ENABLE_BLKDISCARD
        else {
            // A failed restore is not rolled back, but only successfully
            // written bytes may change; capacity and the untouched tail remain.
            auto result=get("partition.bin");CHECK(result.size()==partition.size());
            CHECK(result.substr(0,write_bytes)==image.substr(0,write_bytes));
            CHECK(result.substr(write_bytes)==partition.substr(write_bytes));
        }
#endif
    }
    if(settings.progress){CHECK(progress.finished==rc);if(rc)CHECK(progress.bytes==(backing?partition.size():image.size()));}
    if(rc)CHECK(syncs>0);
    printf("PASS bytes_read=%llu bytes_written=%llu writes=%u fsync=%u closes=%u rename=%u discard=%u\n",(unsigned long long)read_bytes,(unsigned long long)write_bytes,writes,syncs,closes,renames,discards);
}
