// Native minadbd stand-in: private symlink publication and real COMD/STAT socket.
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <unistd.h>
static bool transfer(int fd,void* buffer,size_t size,bool write){
 char* p=static_cast<char*>(buffer);while(size){auto n=write?::write(fd,p,size) : ::read(fd,p,size);if(n<0&&errno==EINTR)continue;if(n<=0)return false;p+=n;size-=n;}return true;
}
int main(int argc,char**argv){
 assert(argc==3&&!strcmp(argv[1],"--socket_fd"));int fd=atoi(argv[2]);int count=atoi(getenv("SIDELOAD_PACKAGES"));
 for(int index=0;index<count;++index){
  unlink("/sideload/package.zip");std::string source="/packages/"+std::to_string(index)+".zip";
  assert(symlink(source.c_str(),"/sideload/package.zip")==0);
  // Digest sidecar is part of the fixture's exposed package path.
  unlink("/sideload/package.zip.sha256");std::string sidecar=source+".sha256";
  if(access(sidecar.c_str(),F_OK)==0)assert(symlink(sidecar.c_str(),"/sideload/package.zip.sha256")==0);
  char command[8]={'C','O','M','D',0,0,0,0},reply[8];assert(transfer(fd,command,8,true));
  if(!transfer(fd,reply,8,false))return 2;
  assert(!memcmp(reply,"STAT",4));unsigned status;memcpy(&status,reply+4,4);assert(status<=1);
  unsigned attempts=0;FILE* record=fopen("/packages/cache-events","r");
  if(record){char line[32];while(fgets(line,sizeof(line),record))++attempts;fclose(record);}
  record=fopen("/packages/cache-at-ack","a");assert(record);fprintf(record,"%u\n",attempts);fclose(record);
  FILE* f=fopen("/packages/statuses","a");assert(f);fprintf(f,"%u\n",status);fclose(f);
  if(status)return 8;
 }
 return 0;
}
