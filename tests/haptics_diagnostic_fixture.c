#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static const char *mode(void) { return getenv("DIAGNOSTIC_CASE"); }
static int is(const char *value) { return strcmp(mode(), value) == 0; }
static int stock(void) { return strncmp(mode(), "stock-", 6) == 0; }
static int custom(void) { return stock() || strncmp(mode(), "custom-", 7) == 0; }
static int gain(void) { return stock() || strncmp(mode(), "sine-gain-", 10) == 0; }
static int uploaded = 0, played = 0, slept = 0, gained = 0;

int __wrap_open(const char *path, int flags, ...) {
    assert(strcmp(path, "/dev/input/event4") == 0);
    assert(flags == ((is("inspect") ? O_RDONLY : O_RDWR) | O_CLOEXEC));
    if (is("open-error")) { errno = EACCES; return -1; }
    return 9;
}
int __wrap_ioctl(int fd, unsigned long request, ...) {
    assert(fd == 9);
    va_list args;
    va_start(args, request);
    if (request == EVIOCRMFF) {
        assert(va_arg(args, int) == 7 && uploaded && played && slept);
        va_end(args);
        if (is("erase-error") || is("stock-erase-error")) { errno = ETIME; return -1; }
        return 0;
    }
    void *data = va_arg(args, void *);
    va_end(args);
    if (_IOC_NR(request) == _IOC_NR(EVIOCGNAME(1))) {
        if (is("name-error")) { errno = EIO; return -1; }
        strcpy(data, is("wrong-device") ? "other-haptic" : "cs40l26_input");
        return 15;
    }
    if (_IOC_NR(request) == _IOC_NR(EVIOCGBIT(EV_FF, 1))) {
        if (is("caps-error")) { errno = EIO; return -1; }
        memset(data, 0, _IOC_SIZE(request));
        unsigned long *bits = data;
        if (!is("unsupported")) {
            for (int bit = FF_PERIODIC; bit <= FF_SINE; bit += FF_SINE - FF_PERIODIC)
                bits[bit / 64] |= 1UL << (bit % 64);
            if (!is("stock-no-custom")) bits[FF_CUSTOM / 64] |= 1UL << (FF_CUSTOM % 64);
            if (!is("stock-no-gain") && !is("sine-gain-no-gain") && !is("custom-no-gain")) bits[FF_GAIN / 64] |= 1UL << (FF_GAIN % 64);
            if (is("custom-no-custom")) bits[FF_CUSTOM / 64] &= ~(1UL << (FF_CUSTOM % 64));
            if (is("sine-gain-no-sine")) bits[FF_SINE / 64] &= ~(1UL << (FF_SINE % 64));
        }
        return _IOC_SIZE(request);
    }
    assert(request == EVIOCSFF && !is("inspect"));
    struct ff_effect *effect = data;
    assert(effect->type == FF_PERIODIC && effect->id == -1);
    assert(gained == gain());
    if (custom()) {
        assert(effect->replay.length == 0);
        assert(effect->u.periodic.waveform == FF_CUSTOM && effect->u.periodic.custom_len == 2);
        assert(effect->u.periodic.period == 0 && effect->u.periodic.magnitude == 0);
        assert(effect->u.periodic.custom_data[0] == 0 && effect->u.periodic.custom_data[1] == 31);
        const unsigned char *raw = (const unsigned char *)effect->u.periodic.custom_data;
        printf("CUSTOM_HEX %02x%02x%02x%02x\n",raw[0],raw[1],raw[2],raw[3]);
    } else {
        assert(effect->u.periodic.waveform == FF_SINE && effect->u.periodic.period == 8);
        assert(effect->u.periodic.magnitude == 64 && effect->replay.length == 80);
    }
    if (is("upload-error") || is("stock-upload-error") || is("sine-gain-upload-error") || is("custom-upload-error")) { errno = EIO; return -1; }
    uploaded = 1;
    if (!is("invalid-id")) effect->id = 7;
    return 0;
}
ssize_t __wrap_write(int fd, const void *data, size_t length) {
    assert(fd == 9 && length == 24 && !is("inspect"));
    const struct input_event *event = data;
    if (gain() && event->code == FF_GAIN) {
        assert(!uploaded && !played && !gained);
        assert(event->type == EV_FF && event->value == 100);
        gained = 1;
        if(is("stock-gain-error") || is("sine-gain-write-error")){errno=EIO;return -1;}
        if(is("stock-gain-short") || is("sine-gain-write-short"))return 1;
        return 24;
    }
    assert(uploaded);
    assert(event->type == EV_FF && event->code == 7 && event->value == 1);
    played = 1;
    if (is("play-short")) return 1;
    if (is("play-error") || is("stock-play-error")) { errno = ENODEV; return -1; }
    return 24;
}
int __wrap_nanosleep(const struct timespec *request, struct timespec *remaining) {
    assert(uploaded && played && request->tv_sec == 0 && request->tv_nsec == 80000000);
    if (is("sleep-interrupted") && !slept) {
        *remaining = *request;
        slept = 1;
        errno = EINTR;
        return -1;
    }
    slept = 1;
    return 0;
}
int __wrap_close(int fd) {
    assert(fd == 9);
    if (is("inspect")) assert(!uploaded && !played && !slept);
    if (is("close-error")) { errno = EIO; return -1; }
    return 0;
}
