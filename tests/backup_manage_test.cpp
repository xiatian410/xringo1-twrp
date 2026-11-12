#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <fcntl.h>
#include <linux/fs.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "backend/twrp_tools_backend.h"
#include "twrp_operation_executor.h"
namespace fs=std::filesystem;
static std::string root;
#define TW_BACKUPS_FOLDER_VAR "backups"
#define LOGERR(...) ((void)0)
namespace DataManager {static std::string GetStrValue(const char*){return root;}}
namespace gui2_console {template<class... A>void log_error(A...){}}
struct TWFunc {
 static int RemoveDir(const std::string& path,bool skip_parent);
};
#include "remove.inc"

namespace gui2_backend {
static void operation_start(const std::string&){}
static void operation_end(int){}
static bool partition_tool_target_allowed(const std::string&){return true;}
template<class... A>static int unused(A...){assert(false);return 1;}
static int cmd(const std::string&s){return std::system(s.c_str())==0?0:1;}
static int repair(const std::string&s){return unused(s);}
static int resize(const std::string&s){return unused(s);}
static int changefilesystem(const std::string&a,const std::string&b){return unused(a,b);}
static int applycustomtwrpfolder(const std::string&s){return unused(s);}
static int fixabrecoverybootloop(){return unused();}
static int mergesnapshots(){return unused();}
static int disableAVB2(){return unused();}
static int refreshsizes(){return unused();}
static int copylog(){return unused();}
static int fixcontexts(){return unused();}
static int unmapsuperdevices(){return unused();}
static int reflashtwrp(){return unused();}
static int repackimage(){return unused();}
bool twrp_tools_backend::details(const std::string&,partition_details*){return false;}
tool_availability twrp_tools_backend::availability(){return {};}
std::string twrp_tools_backend::twrp_folder(){return {};}
std::string twrp_tools_backend::storage_path(){return {};}
bool twrp_tools_backend::path_exists(const std::string&){return false;}
bool twrp_tools_backend::users_locked(){return false;}
#include "worker.inc"
}
static bool run(gui2_backend::twrp_tools_backend&b,gui2_backend::tool_job job,const std::string&p,const std::string&v=""){
 assert(b.start(job,p,v));auto end=std::chrono::steady_clock::now()+std::chrono::seconds(3);
 while(b.status()==gui2_backend::tool_state::RUNNING){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
 bool ok=b.status()==gui2_backend::tool_state::DONE;b.acknowledge();return ok;
}
int main(int argc,char**argv){
 assert(argc==3);std::string c=argv[1];fs::path w=argv[2];fs::current_path(w);root=(w/"backups").string();
 if(c=="special-root")root=(w/"root$(touch ROOT_INJECTED)").string();fs::create_directory(root);
 fs::path source=fs::path(root)/((c=="special-source"||c=="delete-special")?"old$(touch INJECTED)":"old");
 fs::create_directory(source);std::ofstream(source/"data")<<"keep";
 fs::path outside=w/"outside";fs::create_directory(outside);std::ofstream(outside/"sentinel")<<"keep";
 fs::path actual=source;
 if(c=="different-parent"||c=="delete-outside")actual=outside;
 if(c=="symlink-source"||c=="delete-symlink"){fs::remove_all(source);fs::create_directory_symlink(outside,source);}
 if(c=="existing-target"){fs::create_directory(fs::path(root)/"new");std::ofstream(fs::path(root)/"new"/"sentinel")<<"keep";}
 if(c=="missing-source")fs::remove_all(source);
 std::string name=c=="invalid-name"?"../escaped":"new";
 gui2_backend::twrp_tools_backend backend;bool del=c.starts_with("delete-");
 bool ok=run(backend,del?gui2_backend::tool_job::DELETE_BACKUP:gui2_backend::tool_job::RENAME_BACKUP,actual.string(),name);
 bool reject=c=="different-parent"||c=="existing-target"||c=="invalid-name"||c=="symlink-source"||c=="delete-outside"||c=="delete-symlink"||c=="missing-source";
 assert(ok==!reject);assert(!fs::exists(w/"INJECTED")&&!fs::exists(w/"ROOT_INJECTED"));assert(fs::exists(outside/"sentinel"));assert(!fs::exists(w/"escaped"));
 if(!reject){assert(!fs::exists(source));if(!del)assert(fs::exists(fs::path(root)/"new"/"data"));}
 if(c=="existing-target")assert(fs::exists(source/"data")&&fs::exists(fs::path(root)/"new"/"sentinel"));
 if(c=="reused-worker"){assert(run(backend,gui2_backend::tool_job::RENAME_BACKUP,(fs::path(root)/"new").string(),"again"));assert(run(backend,gui2_backend::tool_job::DELETE_BACKUP,(fs::path(root)/"again").string()));assert(fs::is_empty(root));}
 std::printf("PASS %s\n",c.c_str());
}
