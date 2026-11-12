// Run the real recorder with bounded failures at codec/stdio boundaries.
#include <atomic>
#include <cassert>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>
#include <vector>
#include "webm_vp8.h"
#include "vpx/vpx_encoder.h"

static std::string target, mode;
static FILE* recording_file = nullptr;
static bool inject = true;
static std::atomic<int> encodes{0};
static std::atomic<int> injected{0};
static int opens = 0, closes = 0;
extern "C" FILE* __real_fopen(const char*, const char*);
extern "C" FILE* __wrap_fopen(const char* path, const char* flags) {
  if (target == path && inject && mode == "open") {
    ++injected; errno = EACCES; return nullptr;
  }
  FILE* file = __real_fopen(path, flags);
  if (target == path && file) { assert(!recording_file); recording_file = file; ++opens; }
  return file;
}
extern "C" size_t __real_fwrite(const void*, size_t, size_t, FILE*);
extern "C" size_t __wrap_fwrite(const void* bytes, size_t size, size_t count, FILE* file) {
  if (file == recording_file && inject && mode == "write") {
    ++injected; errno = ENOSPC; return 0;
  }
  return __real_fwrite(bytes, size, count, file);
}
extern "C" int __real_fflush(FILE*);
extern "C" int __wrap_fflush(FILE* file) {
  const int result = __real_fflush(file);
  if (file == recording_file && inject && mode == "flush") {
    ++injected; errno = ENOSPC; return EOF;
  }
  return result;
}
extern "C" int __real_fclose(FILE*);
extern "C" int __wrap_fclose(FILE* file) {
  const bool is_recording = file == recording_file;
  const int result = __real_fclose(file);
  if (is_recording) { ++closes; recording_file = nullptr; }
  // The real stream is closed even when its close result is injected as error.
  if (is_recording && inject && (mode == "close" || mode == "codec-close")) {
    ++injected; errno = EIO; return EOF;
  }
  return result;
}
extern "C" vpx_codec_err_t __real_vpx_codec_encode(vpx_codec_ctx_t*, const vpx_image_t*,
    vpx_codec_pts_t, unsigned long, vpx_enc_frame_flags_t, unsigned long);
extern "C" vpx_codec_err_t __wrap_vpx_codec_encode(vpx_codec_ctx_t* ctx, const vpx_image_t* img,
    vpx_codec_pts_t pts, unsigned long duration, vpx_enc_frame_flags_t flags, unsigned long deadline) {
  vpx_codec_err_t result;
  if (inject && (mode == "codec" || mode == "codec-close")) {
    ++injected; result = VPX_CODEC_ERROR;
  } else {
    result = __real_vpx_codec_encode(ctx, img, pts, duration, flags, deadline);
  }
  ++encodes;
  return result;
}

int main(int argc, char** argv) {
  assert(argc == 3);
  target = argv[1]; mode = argv[2];
  assert(mode == "open" || mode == "write" || mode == "flush" || mode == "close" ||
         mode == "codec" || mode == "codec-close");
  gui2_backend::webm_vp8_recorder recorder;
  auto start = recorder.start(target, 96, 64, 30, 1000);
  std::string error;
  bool correctly_failed;
  std::vector<uint8_t> pixels(96 * 64 * 4, 0x80);
  gui2_backend::frame_view frame{pixels.data(), 96, 64, 96 * 4,
                                gui2_backend::frame_pixel_format::BGRA8888};
  auto submit = [&] {
    const int before = encodes.load();
    recorder.submit_frame(frame, 1000);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (encodes.load() == before && std::chrono::steady_clock::now() < deadline)
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    assert(encodes.load() == before + 1);
  };
  if (mode == "open") {
    correctly_failed = !start.success && !recorder.is_recording();
    error = start.error;
  } else {
    assert(start.success);
    submit();
    auto stop = recorder.stop(1500);
    correctly_failed = !stop.success && !stop.error.empty() && !recorder.is_recording();
    error = stop.error;
    if (mode == "codec" || mode == "codec-close")
      assert(error == "Unable to encode WebM frame");
  }
  assert(injected > 0 && !recording_file && opens == closes);
  assert(!recorder.stop(1500).success);
  // Failure cleanup must allow a later complete recording on the same object.
  inject = false;
  assert(recorder.start(target, 96, 64, 30, 1000).success);
  submit();
  assert(recorder.stop(1500).success && !recorder.is_recording());
  assert(!recording_file && opens == closes);
  printf("%s case=%s failure_propagated=%d injected=%d streams_opened=%d streams_closed=%d restart=PASS error=%s\n",
         correctly_failed ? "PASS" : "FAIL", mode.c_str(), correctly_failed,
         injected.load(), opens, closes, error.c_str());
  return correctly_failed ? 0 : 1;
}
