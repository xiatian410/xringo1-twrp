/* Executes the production libtar sources; fixtures never accept disk paths. */
#include <internal.h>
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/xattr.h>
#include <linux/xattr.h>
#include <unistd.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s (errno=%d)\n", __LINE__, #x, errno); exit(1); } } while (0)
#ifndef TAR_STORE_USER_XATTR
#define TAR_STORE_USER_XATTR 4096
#endif
#define FLAGS (TAR_STORE_USER_XATTR | TAR_GNU | TAR_STORE_SELINUX | TAR_STORE_POSIX_CAP | TAR_STORE_ANDROID_USER_XATTR | TAR_STORE_FSCRYPT_POL)

/* Host volumes are not encrypted. Only this kernel/vold boundary is replaced;
 * policy serialization code is compiled, but real fscrypt is not validated. */
static int policy_fixture, policy_calls, policy_dir_empty;
bool fscrypt_policy_get_struct(const char *path, struct fscrypt_policy_v2 *p) {
    if(!policy_fixture || strcmp(path,"input/app")) return false;
    memset(p,0,sizeof *p); p->version=2; p->contents_encryption_mode=1; p->filenames_encryption_mode=4;
    memset(p->master_key_identifier,0x42,16); return true;
}
bool fscrypt_policy_set_struct(const char *path, const struct fscrypt_policy_v2 *p) {
    CHECK(policy_fixture && p->version==2); ++policy_calls;
    DIR *d=opendir(path); CHECK(d!=NULL); struct dirent *e; policy_dir_empty=1;
    while((e=readdir(d))) if(strcmp(e->d_name,".") && strcmp(e->d_name,"..")) policy_dir_empty=0;
    CHECK(closedir(d)==0); return policy_dir_empty;
}
bool lookup_ref_key(struct fscrypt_policy_v2 *p, uint8_t *r) { (void)p; CHECK(policy_fixture); memcpy(r,"2DE0",5); return true; }
bool lookup_ref_tar(const uint8_t *p, uint8_t *r) { CHECK(policy_fixture && !strcmp((const char*)p,"2DE0")); memset(r,0x42,16); return true; }
void bytes_to_hex(const uint8_t *p, size_t n, char *r) {
    for (size_t i=0; i<n; ++i) sprintf(r+2*i, "%02x", p[i]);
}

static const char *fault;
static unsigned fault_calls;
static int record_progress;
static int security_fixture, label_calls, cap_calls;
static const char security_context[]="u:object_r:system_file:s0";
static struct vfs_cap_data fixture_cap;
int __real_lgetfilecon(const char *, char **);
int __real_lsetfilecon(const char *, const char *);
ssize_t __real_getxattr(const char *, const char *, void *, size_t);
int __wrap_lgetfilecon(const char *path, char **context) {
    if(!security_fixture)return __real_lgetfilecon(path,context);
    if(!strncmp(path,"input/",6)) {*context=strdup(security_context); CHECK(*context); return strlen(*context)+1;}
    errno=ENODATA;return -1;
}
int __wrap_lsetfilecon(const char *path, const char *context) {
    if(!security_fixture)return __real_lsetfilecon(path,context);
    ++label_calls; CHECK(!strncmp(path,"restore/",8)&&!strcmp(context,security_context));
    if(fault && strstr(fault,"selinux-denied")){errno=EPERM;return -1;}
    if(fault && strstr(fault,"selinux-unsupported")){errno=EOPNOTSUPP;return -1;}
    struct stat st; CHECK(lstat(path,&st)==0);
    if(S_ISLNK(st.st_mode))return 0; /* call semantics only, host symlink xattrs unavailable */
    return setxattr(path,"user.fixture_selinux",context,strlen(context)+1,0);
}
ssize_t __wrap_getxattr(const char *path,const char *name,void *value,size_t size) {
    if(security_fixture&&!strcmp(name,XATTR_NAME_CAPS))name="user.fixture_capability";
    return __real_getxattr(path,name,value,size);
}
ssize_t __real_write(int, const void *, size_t);
int __real_close(int);
int __real_setxattr(const char *, const char *, const void *, size_t, int);
int __wrap_setxattr(const char *path, const char *name, const void *value, size_t size, int flags) {
    if(security_fixture&&!strcmp(name,XATTR_NAME_CAPS)) {
        ++cap_calls; CHECK(!strncmp(path,"restore/",8)&&size==sizeof fixture_cap&&!memcmp(value,&fixture_cap,size));
        if(fault&&strstr(fault,"capability-denied")){errno=EPERM;return -1;}
        if(fault&&strstr(fault,"capability-io")){errno=EIO;return -1;}
        name="user.fixture_capability";
    }
    if(fault && !strcmp(fault,"android-xattr-write-error") && !strncmp(path,"restore/",8)) {
        ++fault_calls; errno=EIO; return -1;
    }
    return __real_setxattr(path,name,value,size,flags);
}
ssize_t __real_llistxattr(const char*,char*,size_t);
ssize_t __real_lgetxattr(const char*,const char*,void*,size_t);
int __real_lsetxattr(const char*,const char*,const void*,size_t,int);
ssize_t __wrap_llistxattr(const char* path,char* names,size_t size){
 if(fault&&!strncmp(path,"input/",6)){
  if(!strcmp(fault,"xattr-list-error")){++fault_calls;errno=EACCES;return -1;}
  if(!strcmp(fault,"xattr-no-support")){++fault_calls;errno=ENOTSUP;return -1;}
  if(!strcmp(fault,"xattr-list-race")&&names&&fault_calls++==0){errno=ERANGE;return -1;}
 }
 return __real_llistxattr(path,names,size);
}
ssize_t __wrap_lgetxattr(const char* path,const char* name,void* value,size_t size){
 if(fault&&!strncmp(path,"input/",6)&&!strcmp(name,"user.note")){
  if(!strcmp(fault,"xattr-read-error")){++fault_calls;errno=EIO;return -1;}
  if(!strcmp(fault,"xattr-read-race")&&value){++fault_calls;errno=ERANGE;return -1;}
 }
 return __real_lgetxattr(path,name,value,size);
}
int __wrap_lsetxattr(const char* path,const char* name,const void* value,size_t size,int flags){
 if(fault&&!strncmp(path,"restore/",8)&&!strcmp(name,"user.note")&&!strcmp(fault,"xattr-write-error")){
  ++fault_calls;errno=ENOSPC;return -1;
 }
 return __real_lsetxattr(path,name,value,size,flags);
}
static int restore_fd(int fd) {
    char name[64], path[4096];
    snprintf(name,sizeof name,"/proc/self/fd/%d",fd);
    ssize_t n=readlink(name,path,sizeof(path)-1);
    if(n<0) return 0;
    path[n]=0;
    return strstr(path,"/restore/") != NULL;
}
off64_t __real_lseek64(int, off64_t, int);
int __real_ftruncate64(int, off64_t);
off64_t __wrap_lseek64(int fd, off64_t offset, int whence) {
    if(fault && !strcmp(fault,"sparse-seek-interrupted") && restore_fd(fd) && fault_calls++==0) {
        errno=EINTR; return -1;
    }
    if(fault && !strcmp(fault,"sparse-seek-error") && restore_fd(fd)) {
        ++fault_calls; errno=EIO; return -1;
    }
    return __real_lseek64(fd,offset,whence);
}
int __wrap_ftruncate64(int fd, off64_t size) {
    if(fault && !strcmp(fault,"sparse-truncate-interrupted") && restore_fd(fd) && fault_calls++==0) {
        errno=EINTR; return -1;
    }
    if(fault && !strcmp(fault,"sparse-truncate-error") && restore_fd(fd)) {
        ++fault_calls; errno=ENOSPC; return -1;
    }
    return __real_ftruncate64(fd,size);
}
ssize_t __wrap_write(int fd, const void *p, size_t n) {
    if (fault && restore_fd(fd)) {
        ++fault_calls;
        if (!strcmp(fault,"short-write")) return __real_write(fd,p,n>17?17:n);
        if (!strcmp(fault,"interrupted-write") && fault_calls==1) { errno=EINTR; return -1; }
        if (!strcmp(fault,"zero-write")) return 0;
        if (!strcmp(fault,"full-disk")) {
            if(fault_calls==1) return __real_write(fd,p,17);
            errno=ENOSPC; return -1;
        }
    }
    return __real_write(fd,p,n);
}
int __wrap_close(int fd) {
    int fail=fault && !strcmp(fault,"close-error") && restore_fd(fd);
    int rc=__real_close(fd);
    if(fail) { ++fault_calls; errno=EIO; return -1; }
    return rc;
}
static void putfile(const char *name, size_t size) {
    CHECK(mkdirhier(dirname(name))>=0);
    int fd=open(name,O_CREAT|O_TRUNC|O_WRONLY,0640); CHECK(fd>=0);
    unsigned char data[8192];
    for(size_t i=0;i<sizeof data;++i) data[i]=(unsigned char)((i*97+31)%251);
    for(size_t off=0;off<size;) {
        size_t n=size-off; if(n>sizeof data)n=sizeof data;
        CHECK(write(fd,data,n)==(ssize_t)n); off+=n;
    }
    CHECK(close(fd)==0);
    struct timespec ts[2]={{1700000000,0},{1700000000,0}};
    CHECK(utimensat(AT_FDCWD,name,ts,0)==0);
}
static void compare(const char *a,const char *b) {
    struct stat sa,sb; CHECK(lstat(a,&sa)==0); CHECK(lstat(b,&sb)==0);
    CHECK(sa.st_size==sb.st_size); CHECK(sa.st_mode==sb.st_mode);
    CHECK(sa.st_uid==sb.st_uid && sa.st_gid==sb.st_gid);
    CHECK(sa.st_mtime==sb.st_mtime);
    int fa=open(a,O_RDONLY),fb=open(b,O_RDONLY); CHECK(fa>=0 && fb>=0);
    char ba[4096],bb[4096]; ssize_t n;
    while((n=read(fa,ba,sizeof ba))>0) { CHECK(read(fb,bb,n)==n); CHECK(!memcmp(ba,bb,n)); }
    CHECK(n==0); CHECK(read(fb,bb,1)==0); CHECK(close(fa)==0); CHECK(close(fb)==0);
}
static TAR *writer(void) {
    TAR *t=NULL; CHECK(tar_open(&t,"backup.tar",NULL,O_WRONLY|O_CREAT|O_TRUNC,0600,FLAGS)==0); return t;
}
static void finish(TAR *t) { CHECK(tar_append_eof(t)==0); CHECK(tar_close(t)==0); }
static int restore(char *prefix) {
    TAR *t=NULL; int progress=0;
    if(record_progress){progress=open("progress.bin",O_CREAT|O_TRUNC|O_WRONLY,0600); CHECK(progress>0);}
    CHECK(tar_open(&t,"backup.tar",NULL,O_RDONLY,0,FLAGS)==0);
    int rc=tar_extract_all(t,prefix,&progress),saved=errno;
    CHECK(tar_close(t)==0); if(record_progress)CHECK(close(progress)==0); errno=saved; return rc;
}
static void make_one(void) {
    putfile("input/payload",8193); TAR *t=writer();
    CHECK(tar_append_file(t,"input/payload","payload")==0); finish(t);
}
static size_t pax_record(char *out, const char *value, size_t length) {
    size_t size=length+3, previous;
    do { previous=size; char number[32]; int digits=snprintf(number,sizeof number,"%zu",size); size=length+digits+2; } while(size!=previous);
    int n=sprintf(out,"%zu ",size); memcpy(out+n,value,length); out[size-1]='\n'; return size;
}
static void metadata_case(const char *which) {
    char block[512]={0}; size_t length;
    if(!strcmp(which,"metadata-length")) { memcpy(block,"999 ANDROID.user.default\n",25); length=25; }
    else if(!strcmp(which,"metadata-short-cap")) length=pax_record(block,"SCHILY.xattr.security.capability=x",33);
    else if(!strcmp(which,"metadata-short-policy")) length=pax_record(block,"TWRP.security.fscrypt=0x",23);
    else if(!strcmp(which,"metadata-no-newline")) { length=pax_record(block,"ANDROID.user.default",20); block[length-1]='x'; }
    else length=pax_record(block,"TEST.note=ANDROID.user.default",30);
    TAR *t=writer(); th_set_path(t,"payload"); t->th_buf.typeflag=TH_EXT_TYPE; th_set_size(t,length);
    CHECK(th_write(t)==0); CHECK(write(t->fd,block,sizeof block)==sizeof block);
    t->th_buf.typeflag=REGTYPE; th_set_size(t,0); CHECK(th_write(t)==0); finish(t);
    CHECK(tar_open(&t,"backup.tar",NULL,O_RDONLY,0,FLAGS)==0);
    if(!strcmp(which,"metadata-unknown-tag")) { CHECK(th_read(t)==0); CHECK(!t->th_buf.has_user_default); }
    else CHECK(th_read(t)==-1);
    CHECK(tar_close(t)==0);
}
static void hardlink_case(const char *which) {
    char name[1700]="payload",dest[4096];
    char prefix[2200]="restore";
    if(!strcmp(which,"hardlink-long")) {
        for(int i=0;i<4;++i) { strcat(prefix,"/"); size_t pos=strlen(prefix); memset(prefix+pos,'a'+i,180); prefix[pos+180]=0; }
        for(int i=0;i<3;++i) { strcat(name,"/"); size_t pos=strlen(name); memset(name+pos,'k'+i,180); name[pos+180]=0; }
        strcat(name,"/file");
    }
    CHECK(mkdirhier(prefix)>=0);
    snprintf(dest,sizeof dest,"input/%s",name); putfile(dest,513);
    CHECK(link(dest,"input/alias")==0);
    TAR *t=writer(); CHECK(tar_append_file(t,dest,name)==0);
    CHECK(tar_append_file(t,"input/alias","alias")==0); finish(t);
    char *used=prefix;
    if(!strcmp(which,"hardlink-null-prefix")) { CHECK(chdir("restore")==0); CHECK(link("../backup.tar","backup.tar")==0); used=NULL; }
    CHECK(restore(used)==0);
    struct stat a,b;
    snprintf(dest,sizeof dest,"%s/%s",used?used:".",name); CHECK(stat(dest,&a)==0);
    snprintf(dest,sizeof dest,"%s/alias",used?used:"."); CHECK(stat(dest,&b)==0);
    CHECK(a.st_ino==b.st_ino && a.st_dev==b.st_dev && a.st_nlink==2);
}
int main(int argc,char **argv) {
    CHECK(argc==2);
    char cwd[4096]; CHECK(getcwd(cwd,sizeof cwd)!=NULL);
    CHECK(!strncmp(cwd,"/tmp/dijun-archive-",19));
    CHECK(access(".fixture",F_OK)==0);
    CHECK(mkdir("input",0700)==0); CHECK(mkdir("restore",0700)==0);
    const char *c=argv[1];
    if(!strncmp(c,"xattr-pax-",10)) {
        char payload[5000]={0},record[5100]={0};size_t length=0;
        if(!strcmp(c,"xattr-pax-duplicate")){
            length=pax_record(record,"SCHILY.xattr.user.note=first",28);
            length+=pax_record(record+length,"SCHILY.xattr.user.note=last",27);
        }else if(!strcmp(c,"xattr-pax-null-key")){
            memcpy(payload,"SCHILY.xattr.user.n",18);payload[18]=0;memcpy(payload+19,"=value",6);
            length=pax_record(record,payload,25);
        }else if(!strcmp(c,"xattr-pax-missing-equal"))length=pax_record(record,"SCHILY.xattr.user.note",22);
        else {
            memcpy(payload,"SCHILY.xattr.user.note=",23);memset(payload+23,'X',3000);
            length=pax_record(record,payload,3023);
        }
        TAR*t=writer();th_set_path(t,"payload");t->th_buf.typeflag=TH_EXT_TYPE;
        th_set_size(t,!strcmp(c,"xattr-pax-oversize")?1024*1024+1:length);CHECK(th_write(t)==0);
        size_t padded=(length+511)/512*512;char *blocks=calloc(1,padded);CHECK(blocks);memcpy(blocks,record,length);
        CHECK(write(t->fd,blocks,padded)==padded);free(blocks);
        t->th_buf.typeflag=REGTYPE;th_set_size(t,0);CHECK(th_write(t)==0);finish(t);
        if(!strcmp(c,"xattr-pax-truncated"))CHECK(truncate("backup.tar",512+600)==0);
        CHECK(tar_open(&t,"backup.tar",NULL,O_RDONLY,0,FLAGS)==0);
        int progress=0,result=tar_extract_all(t,"restore",&progress);CHECK(tar_close(t)==0);
        if(!strcmp(c,"xattr-pax-duplicate")){
            char got[16];CHECK(result==0);CHECK(lgetxattr("restore/payload","user.note",got,sizeof got)==4&&!memcmp(got,"last",4));
        }else CHECK(result==-1);
        puts("PASS bounded binary PAX validation");
    } else if(!strncmp(c,"xattr-",6)) {
        int directory=!strcmp(c,"xattr-directory");
        if(directory)CHECK(mkdir("input/item",0750)==0);else putfile("input/item",513);
        unsigned char value[3000];for(size_t i=0;i<sizeof value;++i)value[i]=i%251;
        value[1]=0;value[2]='\n';value[3]='=';
        CHECK(setxattr("input/item","user.note",value,sizeof value,0)==0);
        CHECK(setxattr("input/item","user.empty","",0,0)==0);
        CHECK(setxattr("input/item","user.inode_future","123",3,0)==0);
        TAR *t=writer();
        if(!strcmp(c,"xattr-disabled"))t->options&=~TAR_STORE_USER_XATTR;
        fault=c;int append=tar_append_file(t,"input/item","item"),saved=errno;fault=NULL;
        int failed_read=!strcmp(c,"xattr-list-error")||!strcmp(c,"xattr-read-error")||!strcmp(c,"xattr-read-race");
        if(failed_read){CHECK(append==-1&&fault_calls>0);CHECK(saved==(!strcmp(c,"xattr-list-error")?EACCES:(!strcmp(c,"xattr-read-error")?EIO:ERANGE)));CHECK(tar_close(t)==0);puts("PASS xattr collection failure");return 0;}
        CHECK(append==0);
        putfile("input/plain",1);CHECK(tar_append_file(t,"input/plain","plain")==0);finish(t);
        fault=c;int result=restore("restore");saved=errno;fault=NULL;
        if(!strcmp(c,"xattr-write-error")){CHECK(result==-1&&saved==ENOSPC&&fault_calls>0);puts("PASS xattr write failure");return 0;}
        CHECK(result==0);
        int omitted=!strcmp(c,"xattr-disabled")||!strcmp(c,"xattr-no-support");
        unsigned char got[3000];ssize_t size=lgetxattr("restore/item","user.note",got,sizeof got);
        if(omitted)CHECK(size==-1&&errno==ENODATA);
        else {CHECK(size==sizeof value&&!memcmp(value,got,sizeof value));CHECK(lgetxattr("restore/item","user.empty",NULL,0)==0);}
        CHECK(lgetxattr("restore/item","user.inode_future",NULL,0)==-1&&errno==ENODATA);
        CHECK(lgetxattr("restore/plain","user.note",NULL,0)==-1&&errno==ENODATA);
        if(!directory)compare("input/item","restore/item");
        puts("PASS application xattr binary/empty/isolation roundtrip");
    } else if(!strncmp(c,"security-",9)) {
        security_fixture=strcmp(c,"security-metadata-absent")!=0;
        const int directory=strstr(c,"directory")!=NULL, symlink=strstr(c,"symlink")!=NULL;
        if(directory) CHECK(mkdir("input/secure",0750)==0);
        else if(symlink) CHECK(symlinkat("missing",AT_FDCWD,"input/secure")==0);
        else putfile("input/secure",513);
        memset(&fixture_cap,0,sizeof fixture_cap);fixture_cap.magic_etc=VFS_CAP_REVISION_2|VFS_CAP_FLAGS_EFFECTIVE;
        fixture_cap.data[0].permitted=1U<<10;
        if(security_fixture&&!directory&&!symlink)
            CHECK(setxattr("input/secure","user.fixture_capability",&fixture_cap,sizeof fixture_cap,0)==0);
        TAR *t=writer(); CHECK(tar_append_file(t,"input/secure","secure")==0);finish(t);
        int progress=0;CHECK(tar_open(&t,"backup.tar",NULL,O_RDONLY,0,FLAGS)==0);
        const int disabled=!strcmp(c,"security-options-disabled");
        if(disabled)t->options&=~(TAR_STORE_SELINUX|TAR_STORE_POSIX_CAP);
        fault=c;int result=tar_extract_all(t,"restore",&progress),saved=errno;fault=NULL;CHECK(tar_close(t)==0);
        const int failure=strstr(c,"denied")||strstr(c,"unsupported")||strstr(c,"-io");
        if(failure){CHECK(result==-1);CHECK(saved==(strstr(c,"denied")?EPERM:(strstr(c,"unsupported")?EOPNOTSUPP:EIO)));}
        else CHECK(result==0);
        CHECK(label_calls==(!disabled&&security_fixture?1:0));
        CHECK(cap_calls==(!disabled&&security_fixture&&!directory&&!symlink&&!strstr(c,"selinux-denied")&&!strstr(c,"selinux-unsupported")?1:0));
        if(!failure&&!disabled&&security_fixture&&!symlink){
            char context[128];CHECK(getxattr("restore/secure","user.fixture_selinux",context,sizeof context)==sizeof security_context);
            CHECK(!strcmp(context,security_context));
            if(!directory){struct vfs_cap_data got;CHECK(getxattr("restore/secure","user.fixture_capability",&got,sizeof got)==sizeof got);CHECK(!memcmp(&got,&fixture_cap,sizeof got));}
        }
        if(!directory&&!symlink)compare("input/secure","restore/secure");
        printf("PASS security metadata result=%d labels=%d capabilities=%d saved_errno=%d\n",result,label_calls,cap_calls,saved);
    } else if(!strcmp(c,"roundtrip-metadata")) {
        size_t sizes[]={0,1,511,512,513,8193}; TAR *t=writer();
        for(unsigned i=0;i<6;++i) {
            char path[80],name[32]; snprintf(name,sizeof name,"file%u",i); snprintf(path,sizeof path,"input/%s",name);
            putfile(path,sizes[i]); if(geteuid()==0)CHECK(chown(path,1000+i,1000+i)==0);
            CHECK(tar_append_file(t,path,name)==0);
        }
        finish(t); CHECK(restore("restore")==0);
        for(unsigned i=0;i<6;++i) { char a[80],b[80]; snprintf(a,sizeof a,"input/file%u",i); snprintf(b,sizeof b,"restore/file%u",i); compare(a,b); }
    } else if(!strcmp(c,"symlink")) {
        CHECK(symlink("does-not-exist","input/link")==0);
        TAR *t=writer(); CHECK(tar_append_file(t,"input/link","link")==0); finish(t);
        CHECK(restore("restore")==0); char buf[128]={0}; CHECK(readlink("restore/link",buf,sizeof buf)==14); CHECK(!strcmp(buf,"does-not-exist"));
    } else if(!strncmp(c,"hardlink-",9) && strcmp(c,"hardlink-missing")) {
        hardlink_case(c);
    } else if(!strcmp(c,"hardlink-missing")) {
        TAR *t=writer(); th_set_path(t,"alias"); th_set_link(t,"missing"); t->th_buf.typeflag=LNKTYPE;
        CHECK(th_write(t)==0); finish(t);
        CHECK(tar_open(&t,"backup.tar",NULL,O_RDONLY,0,FLAGS)==0); CHECK(th_read(t)==0);
        CHECK(tar_extract_hardlink(t,"restore/alias","restore")==-1); CHECK(errno==ENOENT); CHECK(tar_close(t)==0);
    } else if(!strcmp(c,"short-write") || !strcmp(c,"interrupted-write") || !strcmp(c,"zero-write") || !strcmp(c,"full-disk") || !strcmp(c,"close-error")) {
        make_one(); fault=c; int rc=restore("restore"); fault=NULL; CHECK(fault_calls>0);
        if(!strcmp(c,"short-write") || !strcmp(c,"interrupted-write")) { CHECK(rc==0); compare("input/payload","restore/payload"); }
        else CHECK(rc==-1);
    } else if(!strcmp(c,"truncated-header") || !strcmp(c,"truncated-data") || !strcmp(c,"missing-eot") || !strcmp(c,"single-eot") || !strcmp(c,"bad-checksum")) {
        make_one(); struct stat s; CHECK(stat("backup.tar",&s)==0);
        if(!strcmp(c,"truncated-header")) CHECK(truncate("backup.tar",200)==0);
        else if(!strcmp(c,"truncated-data")) CHECK(truncate("backup.tar",512+100)==0);
        else if(!strcmp(c,"missing-eot")) CHECK(truncate("backup.tar",s.st_size-1024)==0);
        else if(!strcmp(c,"single-eot")) CHECK(truncate("backup.tar",s.st_size-512)==0);
        else { int fd=open("backup.tar",O_WRONLY); CHECK(fd>=0); CHECK(write(fd,"X",1)==1); CHECK(close(fd)==0); }
        CHECK(restore("restore")==-1);
    } else if(!strncmp(c,"metadata-",9)) {
        metadata_case(c);
    } else if(!strcmp(c,"gnu-name-block-boundary")) {
        char name[513],in[530],out[530]; memset(name,'a',512); name[200]='/'; name[401]='/'; name[512]=0;
        snprintf(in,sizeof in,"input/%s",name); snprintf(out,sizeof out,"restore/%s",name);
        putfile(in,513); TAR *t=writer(); CHECK(tar_append_file(t,in,name)==0); finish(t); CHECK(restore("restore")==0); compare(in,out);
    } else if(!strcmp(c,"eot-corrupt")) {
        TAR *t=writer(); finish(t); int fd=open("backup.tar",O_WRONLY); CHECK(fd>=0);
        CHECK(pwrite(fd,"broken",6,10)==6); CHECK(close(fd)==0); CHECK(restore("restore")==-1);
    } else if(!strcmp(c,"ignore-eot")) {
        TAR *t=writer(); finish(t); int progress=0;
        CHECK(tar_open(&t,"backup.tar",NULL,O_RDONLY,0,FLAGS|TAR_IGNORE_EOT)==0);
        CHECK(tar_extract_all(t,"restore",&progress)==0); CHECK(tar_close(t)==0);
    } else if(!strcmp(c,"empty-archive")) {
        TAR *t=writer(); finish(t); CHECK(restore("restore")==0);
    } else if(!strcmp(c,"android-xattrs") || !strcmp(c,"existing-dir-xattrs") || !strcmp(c,"android-xattr-write-error") || !strcmp(c,"encrypted-dir-order")) {
        policy_fixture=!strcmp(c,"encrypted-dir-order");
        CHECK(mkdir("input/app",0750)==0); CHECK(mkdir("input/app/cache",0700)==0); CHECK(mkdir("input/app/code_cache",0700)==0);
        CHECK(setxattr("input/app","user.default",NULL,0,0)==0);
        struct stat s; CHECK(stat("input/app/cache",&s)==0); uint64_t ino=s.st_ino;
        CHECK(setxattr("input/app","user.inode_cache",&ino,sizeof ino,0)==0);
        CHECK(stat("input/app/code_cache",&s)==0); ino=s.st_ino;
        CHECK(setxattr("input/app","user.inode_code_cache",&ino,sizeof ino,0)==0);
        TAR *t=writer(); CHECK(tar_append_tree(t,"input/app","app")==0); finish(t);
        if(!strcmp(c,"existing-dir-xattrs"))CHECK(mkdir("restore/app",0700)==0);
        if(!strcmp(c,"android-xattr-write-error")) {
            fault=c; CHECK(restore("restore")==-1); CHECK(fault_calls>0); fault=NULL; puts("PASS"); return 0;
        }
        CHECK(restore("restore")==0);
        if(policy_fixture)CHECK(policy_calls==1 && policy_dir_empty);
        CHECK(getxattr("restore/app","user.default",NULL,0)==0);
        CHECK(getxattr("restore/app","user.inode_cache",&ino,sizeof ino)==sizeof ino); CHECK(stat("restore/app/cache",&s)==0); CHECK(ino==s.st_ino);
        CHECK(getxattr("restore/app","user.inode_code_cache",&ino,sizeof ino)==sizeof ino); CHECK(stat("restore/app/code_cache",&s)==0); CHECK(ino==s.st_ino);
    } else if(!strncmp(c,"sparse-",7) && strcmp(c,"sparse-content")) {
        const int error_case=strstr(c,"error")!=NULL;
        const off_t length=!strcmp(c,"sparse-empty")?0:1048576+13;
        int fd=open("input/sparse",O_CREAT|O_WRONLY,0600); CHECK(fd>=0);
        CHECK(ftruncate(fd,length)==0);
        if(!strcmp(c,"sparse-leading") || !strcmp(c,"sparse-seek-error") || !strcmp(c,"sparse-seek-interrupted"))
            CHECK(pwrite(fd,"end",3,length-3)==3);
        else if(!strcmp(c,"sparse-trailing")) CHECK(pwrite(fd,"start",5,0)==5);
        else if(!strcmp(c,"sparse-mixed")) {
            CHECK(pwrite(fd,"A",1,0)==1); CHECK(pwrite(fd,"B",1,524288)==1);
            CHECK(pwrite(fd,"C",1,length-1)==1);
        } else if(!strcmp(c,"sparse-partial-zero")) {
            CHECK(pwrite(fd,"A",1,0)==1); CHECK(pwrite(fd,"B",1,1048575)==1);
        }
        CHECK(close(fd)==0);
        TAR *t=writer(); CHECK(tar_append_file(t,"input/sparse","sparse")==0); finish(t);
        /* O_TRUNC must remove old content even when all restored data is zero. */
        putfile("restore/sparse",2*1048576);
        record_progress=1; fault=c;
        int result=restore("restore"), saved=errno; fault=NULL;
        if(error_case) {
            CHECK(result==-1 && fault_calls>0);
            CHECK(saved==(!strcmp(c,"sparse-seek-error")?EIO:ENOSPC));
            puts("PASS sparse I/O failure propagated"); return 0;
        }
        CHECK(result==0); compare("input/sparse","restore/sparse");
        if(strstr(c,"interrupted"))CHECK(fault_calls>=2);
        struct stat a,b; CHECK(stat("input/sparse",&a)==0); CHECK(stat("restore/sparse",&b)==0);
        CHECK(b.st_blocks*512 < 65536);
        fd=open("progress.bin",O_RDONLY);CHECK(fd>=0);
        uint64_t progress=0,total=0;ssize_t count;
        while((count=read(fd,&progress,sizeof progress))>0){CHECK(count==sizeof progress&&progress==512);total+=progress;}
        CHECK(count==0&&close(fd)==0&&total==((length+511)/512)*512);
        printf("PASS sparse logical progress=%lu\n",total);
        printf("PASS sparse bytes/mode/mtime preserved size=%ld source_blocks=%ld restored_blocks=%ld\n",b.st_size,a.st_blocks,b.st_blocks);
    } else if(!strcmp(c,"sparse-content")) {
        int fd=open("input/sparse",O_CREAT|O_WRONLY,0600); CHECK(fd>=0);
        CHECK(write(fd,"start",5)==5); CHECK(lseek(fd,1048576,SEEK_SET)==1048576); CHECK(write(fd,"end",3)==3); CHECK(close(fd)==0);
        TAR *t=writer(); CHECK(tar_append_file(t,"input/sparse","sparse")==0); finish(t); CHECK(restore("restore")==0); compare("input/sparse","restore/sparse");
        struct stat a,b; CHECK(stat("input/sparse",&a)==0); CHECK(stat("restore/sparse",&b)==0);
        printf("OBSERVATION sparse bytes preserved; source blocks=%ld restored blocks=%ld (hole layout is not asserted)\n",a.st_blocks,b.st_blocks);
    } else { fprintf(stderr,"unknown case\n"); return 2; }
    puts("PASS"); return 0;
}
