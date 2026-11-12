#include <algorithm>
#include <cassert>
#include <charconv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <unistd.h>
#include <vector>
#include "abx.hpp"
#include "gui2/third_party/rapidxml.hpp"
#include "tinyxml2.h"
namespace fs=std::filesystem;
#define TW_INCLUDE_FBE
#define TW_INCLUDE_CRYPTO
#define LOGINFO(...) ((void)0)
#define LOGERR(...) ((void)0)
static const fs::path root="FIXTURE_ROOT";
static std::map<std::string,std::string> props,values;
static std::map<int,int> types;
static std::vector<std::pair<int,std::string>> requests;
static std::set<int> allowed;
static int post_decrypt=0;
bool fscrypt_lock_ce_storage(int){return true;}
namespace android::base {
std::string GetProperty(const std::string& k,const std::string& v){return props.count(k)?props.at(k):v;}
bool GetBoolProperty(const std::string& k,bool v){return props.count(k)?props.at(k)=="1" || props.at(k)=="true":v;}
bool SetProperty(const std::string& k,const std::string& v){props[k]=v;return true;}
template<class F> struct Guard{F f;~Guard(){f();}};
template<class F> Guard<F> make_scope_guard(F f){return {f};}
}
namespace android::keystore {
int Get_Password_Type(int id,std::string&){return types.contains(id)?types.at(id):0;}
bool Decrypt_User(int id,const std::string& password){requests.push_back({id,password});return allowed.contains(id)&&password=="fixture-secret";}
}
struct DataManager{static void SetValue(const std::string& k,const std::string& v){values[k]=v;}};
struct twrp_operation_executor {
 using guard=std::lock_guard<std::recursive_mutex>;
 static twrp_operation_executor& instance(){static twrp_operation_executor e;return e;}
 std::recursive_mutex& mutex(){return m;}std::recursive_mutex m;
};
namespace gui2_console {template<class...A> void info(A...){ }template<class...A> void log_error(A...){ }}
namespace TWFunc {
bool IsPathExists(const std::string& p){return fs::exists(p);}
bool CheckXmlFormat(const std::string& p){std::ifstream f(p,std::ios::binary);char h[4]{};f.read(h,4);return memcmp(h,"ABX\0",4)!=0;}
bool AbxToXml(const std::string& p,std::string& converted){
 converted=(root/"converted.xml").string();int r=abx2xml(p,converted,false);
 if(r){fs::remove(converted);converted.clear();}return r==0;
}
}
char* recovery_load_xml(const std::string& p){std::ifstream f(p);if(!f)return nullptr;std::string s{std::istreambuf_iterator<char>(f),{}};return strdup(s.c_str());}
void rapidxml::parse_error_handler(const char*,void*){std::abort();}
struct UsersStruct{int user_id=0;std::string user_name;int type=0;bool is_decrypted=false;};
struct TWPartition{bool mount_to_decrypt_=false,is_fbe_=true;bool Mount(bool){return true;}};
struct TWPartitionManager {
 std::vector<UsersStruct> users_list_;std::vector<TWPartition*> partitions_;TWPartition data;
 bool prepare=true;
 TWPartition* FindPartitionByPath(const std::string&){return &data;}
 bool PrepareDataForDe(bool){return prepare;}
 void SetCryptoState(){}
 void PostDecrypt(const std::string&){++post_decrypt;}
 void ParseUsers();void MarkUserDecrypted(int);void CheckUsersDecryptionStatus() const;
 int DecryptDevice(const std::string&,int);
};
// PRODUCTION_METHODS
void put(const fs::path& p,const std::string& s){fs::create_directories(p.parent_path());std::ofstream f(p,std::ios::binary);f<<s;assert(f);}
void user(int id,const std::string& status="0",bool profile=true){
 fs::create_directories(root/"keys"/std::to_string(id));props[std::format("twrp.user.{}.decrypt",id)]=status;
 if(profile)put(root/"users"/std::format("{}.xml",id),std::format("<user><name>User {}</name></user>",id));
}
std::vector<int> ids(const TWPartitionManager& m){std::vector<int> r;for(const auto& u:m.users_list_)r.push_back(u.user_id);return r;}
const UsersStruct& found(const TWPartitionManager& m,int id){for(const auto& u:m.users_list_)if(u.user_id==id)return u;assert(false);std::abort();}
int main(int argc,char** argv){
 assert(argc==2);std::string test=argv[1];fs::remove_all(root);fs::create_directories(root/"keys");fs::create_directories(root/"users");
 TWPartitionManager m;user(0);user(10);user(999);types={{0,3},{10,1},{999,0}};
 if(test=="missing-profile")fs::remove(root/"users/999.xml");
 if(test=="malformed-xml")put(root/"users/10.xml","<user><name>broken");
 if(test=="oversized-xml")put(root/"users/10.xml","<user><name>"+std::string(70000,'x')+"</name></user>");
 if(test=="abx")assert(xml2abx((root/"users/10.xml").string(),(root/"users/10.xml").string(),true)==0);
 if(test=="invalid-abx")put(root/"users/10.xml",std::string("ABX\0",4)+"broken");
 if(test=="identities"){
  user(17,"garbage");user(18,"-1");user(9999);user(10000);user(-1);
  put(root/"users/00010.xml","<user/>");fs::create_directories(root/"keys/00010");
  put(root/"users/strange.xml","<user/>");fs::create_directories(root/"keys/strange");
  fs::create_directory_symlink(root/"keys/10",root/"keys/11");props["twrp.user.11.decrypt"]="0";
 }
 m.ParseUsers();
 if(test=="discover" || test=="missing-profile"){
  assert(ids(m)==std::vector<int>({0,10,999}));assert(found(m,10).type==1);
  if(test=="missing-profile")assert(found(m,999).user_name=="999");
 }else if(test=="repeat"){
  m.ParseUsers();assert(ids(m)==std::vector<int>({0,10,999}));
 }else if(test=="stale-users"){
  fs::remove_all(root/"keys/10");fs::remove(root/"users/10.xml");m.ParseUsers();assert(ids(m)==std::vector<int>({0,999}));
 }else if(test=="bad-directory"){
  fs::remove_all(root/"keys");put(root/"keys","not a directory");m.ParseUsers();assert(m.users_list_.empty());assert(props["twrp.all.users.decrypted"]=="false");
 }else if(test=="malformed-xml" || test=="oversized-xml" || test=="invalid-abx"){
  assert(ids(m)==std::vector<int>({0,10,999}));assert(found(m,10).user_name=="10");
 }else if(test=="abx"){
  assert(found(m,10).user_name=="User 10 (10)");assert(!fs::exists(root/"converted.xml"));
 }else if(test=="identities"){
  assert(ids(m)==std::vector<int>({0,10,999,9999}));
 }else if(test=="wrong-credential"){
  allowed.insert(10);assert(m.DecryptDevice("wrong",10)!=0);assert(!found(m,10).is_decrypted);
  assert(props["twrp.user.10.decrypt"]=="0" && post_decrypt==0 && requests.size()==1);
 }else if(test=="secondary-isolation"){
  allowed.insert(999);assert(m.DecryptDevice("fixture-secret",999)==0);assert(found(m,999).is_decrypted);
  assert(!found(m,0).is_decrypted && !found(m,10).is_decrypted && post_decrypt==0);
  assert(props["twrp.all.users.decrypted"]=="false");
 }else if(test=="owner-unlock"){
  allowed.insert(0);assert(m.DecryptDevice("fixture-secret",0)==0 && post_decrypt==1);
  assert(!found(m,10).is_decrypted && !found(m,999).is_decrypted);
 }else if(test=="service-unavailable"){
  props["ro.twrp.device_profiles"]="true";props["twrp.crypto.ready"]="0";
  assert(m.DecryptDevice("fixture-secret",0)!=0 && requests.empty());
 }else if(test=="missing-user"){
  assert(m.DecryptDevice("fixture-secret",11)!=0 && requests.empty());
 }else if(test=="de-failure"){
  m.prepare=false;assert(m.DecryptDevice("fixture-secret",10)!=0 && requests.empty());
 }else if(test=="already-unlocked"){
  m.MarkUserDecrypted(10);assert(m.DecryptDevice("anything",10)==0 && requests.empty());
 }else if(test=="all-users"){
  m.MarkUserDecrypted(0);m.MarkUserDecrypted(999);assert(props["twrp.all.users.decrypted"]=="false");
  m.MarkUserDecrypted(10);assert(props["twrp.all.users.decrypted"]=="true");
 }
 puts("ok");
}
