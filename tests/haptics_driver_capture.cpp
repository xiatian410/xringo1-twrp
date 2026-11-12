// Capture production FF ABI bytes at the ioctl/write boundary; no input device.
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <fcntl.h>
#include <linux/input.h>
#include <unistd.h>
#include "force_feedback.h"

static std::string output;
extern "C" int32_t property_get_int32(const char*, int32_t) { return 130; }
extern "C" int __real_open(const char*, int, ...);
extern "C" int __wrap_open(const char* path, int flags, ...) {
    assert(std::string(path) == FIXTURE_INPUT "/event4");
    return __real_open(path, flags);
}
extern "C" int __wrap_ioctl(int, unsigned long request, ...) {
    va_list ap;
    va_start(ap, request);
    if (request == EVIOCRMFF) { va_end(ap); return 0; }
    void* data = va_arg(ap, void*);
    va_end(ap);
    if (_IOC_NR(request) == _IOC_NR(EVIOCGNAME(1))) {
        std::strcpy(static_cast<char*>(data), "cs40l26_input");
        return 15;
    }
    if (_IOC_NR(request) == _IOC_NR(EVIOCGBIT(EV_FF, 1))) {
        std::memset(data, 0, _IOC_SIZE(request));
        auto bits = static_cast<unsigned long*>(data);
        for (int bit : {FF_PERIODIC, FF_SINE})
            bits[bit / (8 * sizeof(long))] |= 1UL << (bit % (8 * sizeof(long)));
        return _IOC_SIZE(request);
    }
    assert(request == EVIOCSFF);
    auto effect = static_cast<ff_effect*>(data);
    assert(sizeof(*effect) == 48 && effect->id == -1);
    // Linux input core allocates an id before invoking the driver callback.
    effect->id = 7;
    FILE* f = std::fopen((output + ".effect").c_str(), "wb");
    assert(f && std::fwrite(effect, sizeof(*effect), 1, f) == 1);
    assert(std::fclose(f) == 0);
    return 0;
}
extern "C" ssize_t __wrap_write(int, const void* data, size_t size) {
    assert(size == sizeof(input_event));
    FILE* f = std::fopen((output + ".event").c_str(), "wb");
    assert(f && std::fwrite(data, size, 1, f) == 1);
    assert(std::fclose(f) == 0);
    return size;
}
int main(int argc, char** argv) {
    assert(argc == 3);
    output = argv[1];
    return twrpminui::play_force_feedback(std::stoi(argv[2]));
}
