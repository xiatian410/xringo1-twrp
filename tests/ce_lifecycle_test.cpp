// Original Recovery control joined to original vold CE cache/eviction methods.
// Key derivation/TEE, install/evict ioctls, filesystem prepare and mounts are fixtures.
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <format>
#include <map>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <vector>
#include <unistd.h>
#define TW_INCLUDE_FBE
#define TW_INCLUDE_CRYPTO
#define TW_IS_FBE "fbe"
#define TW_IS_ENCRYPTED "encrypted"
#define TW_IS_DECRYPTED "decrypted"
#define DATA_MNT_POINT "/data"
#define LOG(x) std::cerr
#include <iostream>
#define LOGINFO(...) ((void)0)
static std::string errors;
template<class...A>void log_error(const char*f,A...a){char b[1024];std::snprintf(b,sizeof(b),f,a...);errors+=b;}
#define LOGERR(...) log_error(__VA_ARGS__)
using userid_t=unsigned;
struct EncryptionPolicy{int user=-1;};
struct UserPolicies{EncryptionPolicy internal;std::map<std::string,EncryptionPolicy> adoptable;};
using KeyBuffer=std::string;
static std::map<userid_t,UserPolicies> s_ce_policies;
static int s_data_options=0;
static bool enabled=true,prepare_ok=true,install_ok=true,evict_ok=true;
static int provider_calls=0,reads=0,installs=0,prepares=0,post=0;
static std::vector<std::pair<std::string,int>> evictions;
static std::map<std::string,std::string> props,values;
namespace android::vold {
struct KeyAuthentication{std::string secret;};
bool evictKey(const std::string&p,const EncryptionPolicy&policy){evictions.push_back({p,policy.user});return evict_ok;}
}
namespace android::os {struct IVold{static constexpr int STORAGE_FLAG_CE=2;};}
namespace android::base {
bool GetBoolProperty(const std::string&n,bool fallback){if(!props.contains(n))return fallback;return props[n]=="1"||props[n]=="true";}
bool SetProperty(const std::string&n,const std::string&v){props[n]=v;return true;}
}
std::string BuildDataPath(const std::string&uuid){return uuid.empty()?"/data":"/mnt/expand/"+uuid;}
bool IsFbeEnabled(){return enabled;}
// Authentication/CE unwrap boundary. No real secret or kernel key is used.
std::optional<android::vold::KeyAuthentication> authentication_from_hex(const std::string&s){return android::vold::KeyAuthentication{s};}
bool read_user_ce_key(userid_t id,const android::vold::KeyAuthentication&a,KeyBuffer*k){++reads;if(a.secret!="synthetic-secret-"+std::to_string(id))return false;*k=std::to_string(id);return true;}
bool install_storage_key(const char*,int,const KeyBuffer&key,EncryptionPolicy*p){++installs;if(!install_ok)return false;p->user=std::stoi(key);return true;}
bool fscrypt_prepare_user_storage(const std::string&,userid_t,int flags){assert(flags==2);++prepares;return prepare_ok;}
// VOLD_METHODS
namespace android::keystore {
// DECRYPT_CE_METHOD
bool Decrypt_User(int id,const std::string&password){++provider_calls;return Decrypt_CE_storage(id,password);}
}
struct DataManager {
 static int GetIntValue(const std::string&n){return values[n]=="1";}
 static void SetValue(const std::string&n,const std::string&v){values[n]=v;}
 static void SetValue(const std::string&n,int v){values[n]=std::to_string(v);}
};
struct UsersStruct{int user_id;bool is_decrypted=false;};
struct TWPartition{bool mount_to_decrypt_=false,is_fbe_=true,is_decrypted_=false;bool Mount(bool){return true;}};
namespace twrp_operation_executor {
struct executor{std::recursive_mutex m;std::recursive_mutex&mutex(){return m;}};
executor&instance(){static executor e;return e;}
using guard=std::lock_guard<std::recursive_mutex>;
}
namespace gui2_console {template<class...A>void info(A...){} template<class...A>void log_error(A...){}}
namespace TWFunc{bool IsPathExists(const std::string&){return true;}}
struct TWPartitionManager {
 std::vector<UsersStruct>users_list_{{0,false},{10,false}};
 TWPartition data;std::vector<TWPartition*>partitions_{&data};bool de_ok=true;
 TWPartition*FindPartitionByPath(const std::string&){return &data;}
 bool PrepareDataForDe(bool){return de_ok;}
 void SetCryptoState(){}
 void PostDecrypt(const std::string&){++post;data.is_decrypted_=true;}
 void MarkUserDecrypted(int);void CheckUsersDecryptionStatus()const;void MarkDataLocked();
 int DecryptDevice(const std::string&,int);
} manager;
// RECOVERY_METHODS
UsersStruct&user(int id){for(auto&u:manager.users_list_)if(u.user_id==id)return u;std::abort();}
std::string secret(int id){return "synthetic-secret-"+std::to_string(id);}
int main(int argc,char**argv){
 assert(argc==2);std::string test=argv[1];values[TW_IS_FBE]="1";
 const int id=test.ends_with("owner")?0:10;
 if(test=="service-not-ready"){props["ro.twrp.device_profiles"]="1";props["twrp.crypto.ready"]="0";assert(manager.DecryptDevice(secret(id),id)<0&&provider_calls==0);}
 else if(test=="missing-user"){assert(manager.DecryptDevice(secret(11),11)<0&&provider_calls==0);}
 else if(test=="DE-failed"){manager.de_ok=false;assert(manager.DecryptDevice(secret(id),id)<0&&provider_calls==0);}
 else if(test=="wrong-secret"){assert(manager.DecryptDevice("wrong",id)<0&&!user(id).is_decrypted&&s_ce_policies.empty()&&installs==0);}
 else if(test=="install-failed"){install_ok=false;assert(manager.DecryptDevice(secret(id),id)<0&&!user(id).is_decrypted&&s_ce_policies.empty()&&installs==1);}
 else if(test.starts_with("prepare-failed-")){
  // Preserve an unrelated, already-unlocked user's key and status throughout.
  const int other=id==0?10:0;
  assert(manager.DecryptDevice(secret(other),other)==0);const int prior_post=post;
  prepare_ok=false;
  assert(manager.DecryptDevice(secret(id),id)<0);
  assert(!user(id).is_decrypted&&s_ce_policies.contains(other)&&user(other).is_decrypted&&post==prior_post);
  assert(!s_ce_policies.contains(id));
  assert(evictions.size()==1&&evictions[0].second==id);
  const int prior_reads=reads,prior_installs=installs;
  prepare_ok=true;assert(manager.DecryptDevice("wrong",id)<0&&!s_ce_policies.contains(id));
  assert(reads==prior_reads+1&&installs==prior_installs&&!user(id).is_decrypted);
  assert(manager.DecryptDevice(secret(id),id)==0);
  assert(reads==prior_reads+2&&installs==prior_installs+1&&user(id).is_decrypted);
 }else if(test=="eviction-failure"){
  prepare_ok=false;evict_ok=false;assert(manager.DecryptDevice(secret(id),id)<0);
  // Original vold removes the cached policy even when its kernel eviction
  // callback fails. A diagnostic is required; no physical relock is claimed.
  assert(!user(id).is_decrypted&&!s_ce_policies.contains(id)&&evictions.size()==1);
  assert(errors.find("Failed to evict CE keys after unsuccessful decrypt")!=std::string::npos);
 }else if(test=="cached-policy"){
  assert(fscrypt_unlock_ce_storage(id,secret(id)));const auto before=reads;
  assert(fscrypt_unlock_ce_storage(id,"wrong")&&reads==before); // original cache early return
 }else if(test=="unmount-reunlock"||test=="adoptable-eviction"||test=="unmount-eviction-failure"){
  assert(manager.DecryptDevice(secret(0),0)==0&&manager.DecryptDevice(secret(10),10)==0);
  if(test=="adoptable-eviction")s_ce_policies[10].adoptable["fixture-volume"]={10};
  if(test=="unmount-eviction-failure")evict_ok=false;
  manager.MarkDataLocked();assert(s_ce_policies.empty()&&!user(0).is_decrypted&&!user(10).is_decrypted);
  assert(props["twrp.all.users.decrypted"]=="false"&&props["twrp.user.10.decrypt"]=="0");
  assert(evictions.size()==(test=="adoptable-eviction"?3u:2u));
  if(test=="adoptable-eviction")assert(evictions.back().first=="/mnt/expand/fixture-volume");
  evict_ok=true;const int before=installs;assert(manager.DecryptDevice(secret(10),10)==0&&installs==before+1);
  assert(!user(0).is_decrypted);
 }else if(test=="already-unlocked"){
  assert(manager.DecryptDevice(secret(id),id)==0);const auto before=provider_calls;
  assert(manager.DecryptDevice("wrong",id)==0&&provider_calls==before);
 }else if(test=="success-owner"||test=="success-secondary"){
  assert(manager.DecryptDevice(secret(id),id)==0&&user(id).is_decrypted&&s_ce_policies.contains(id));
  assert(post==(id==0?1:0)&&!user(id==0?10:0).is_decrypted);
 }else assert(false);
 printf("PASS %s provider=%d read=%d install=%d prepare=%d evict=%zu post=%d\n",test.c_str(),provider_calls,reads,installs,prepares,evictions.size(),post);
}
