#!/usr/bin/env python3
"""Compile the production Binder readiness helper; replace Binder and clock only."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'dtsrc/O1_asic_dual/profiles/runtime/wait_services.cpp'
HARNESS=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <cstdio>
#include <android/binder_ibinder.h>
static int64_t now_ns=0;
static int mode=0, checks=0, acquired=0, released=0;
static AIBinder object;
int64_t fixture_now_ns() { return now_ns; }
extern "C" int __wrap_clock_gettime(clockid_t, timespec* t) {
    t->tv_sec=now_ns/1000000000; t->tv_nsec=now_ns%1000000000; return 0;
}
extern "C" int __wrap_nanosleep(const timespec* t, timespec*) {
    now_ns+=t->tv_sec*1000000000LL+t->tv_nsec; return 0;
}
AIBinder* AServiceManager_checkService(const char* name) {
    ++checks;
    if (mode==1 || (mode==2 && std::strstr(name,"gatekeeper")) ||
        (mode==3 && now_ns<3000000000LL)) return nullptr;
    ++acquired; return &object;
}
int AIBinder_ping(AIBinder*) { return mode==4 ? -1 : 0; }
void AIBinder_decStrong(AIBinder*) { ++released; }
int production_main();
int main() {
    for (mode=0;mode<5;++mode) {
        checks=acquired=released=0;now_ns=0;
        const int result=production_main();
        assert(result==((mode==0 || mode==3)?0:1));
        assert(acquired==released);
        if (result) assert(now_ns==15000000000LL && checks==750);
        if (mode==0) assert(checks==5 && now_ns==0);
        if (mode==3) assert(now_ns==3000000000LL && acquired==5);
    }
    std::puts("PASS: all five services, delayed registration, missing service, dead Binder, bounded deadline, reference release");
}
'''
with tempfile.TemporaryDirectory(prefix='dijun-binder-test-') as temp:
    temp=Path(temp); (temp/'android').mkdir()
    (temp/'android/binder_ibinder.h').write_text('#pragma once\nstruct AIBinder {};\nconstexpr int STATUS_OK=0;\nint AIBinder_ping(AIBinder*);\nvoid AIBinder_decStrong(AIBinder*);\n')
    (temp/'android/binder_manager.h').write_text('#pragma once\n#include <android/binder_ibinder.h>\nAIBinder* AServiceManager_checkService(const char*);\n')
    (temp/'test.cpp').write_text(HARNESS)
    (temp/'clock.h').write_text('''#include <chrono>
extern int64_t fixture_now_ns();
namespace std::chrono {
struct fixture_clock {
    using duration = nanoseconds;
    using time_point = std::chrono::time_point<fixture_clock, duration>;
    static time_point now() { return time_point(duration(fixture_now_ns())); }
};
}
#define steady_clock fixture_clock
''')
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(temp),'-include',str(temp/'clock.h'),'-Dmain=production_main','-c',str(SOURCE),'-o',str(temp/'production.o')],check=True)
    subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(temp),str(temp/'test.cpp'),str(temp/'production.o'),'-Wl,--wrap=clock_gettime','-Wl,--wrap=nanosleep','-o',str(temp/'test')],check=True)
    subprocess.run([str(temp/'test')],check=True,timeout=10)
