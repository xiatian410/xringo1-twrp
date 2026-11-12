// Exercise the production recorder with changing, independently decodable IDs.
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <string>
#include <thread>
#include <vector>
#include "webm_vp8.h"
#include "vpx/vpx_encoder.h"

static std::atomic<int> encoded{0};
extern "C" vpx_codec_err_t __real_vpx_codec_encode(vpx_codec_ctx_t*, const vpx_image_t*,
    vpx_codec_pts_t, unsigned long, vpx_enc_frame_flags_t, unsigned long);
extern "C" vpx_codec_err_t __wrap_vpx_codec_encode(vpx_codec_ctx_t* ctx, const vpx_image_t* image,
    vpx_codec_pts_t pts, unsigned long duration, vpx_enc_frame_flags_t flags, unsigned long deadline) {
  auto result = __real_vpx_codec_encode(ctx, image, pts, duration, flags, deadline);
  assert(result == VPX_CODEC_OK);
  ++encoded;
  return result;
}

int main(int argc, char** argv) {
  assert(argc == 3);
  const int fps = std::stoi(argv[2]);
  assert(fps == 15 || fps == 30 || fps == 60);
  constexpr int width = 160, height = 96, stride = width * 4 + 16;
  constexpr int duration_ms = 12500;
  const int count = (duration_ms * fps + 999) / 1000;
  assert(count < 1024);
  gui2_backend::webm_vp8_recorder recorder;
  assert(recorder.start(argv[1], width, height, fps, 1000).success);
  std::vector<uint8_t> pixels(stride * height, 0xcd);
  for (int index = 0; index < count; ++index) {
    for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
      auto* pixel = pixels.data() + stride * y + x * 4;
      // Ten large grayscale tiles encode frame index; lower area changes once
      // per second to give visual content beyond a static color-bar sample.
      const int value = y < 64 ? ((index >> (x / 16)) & 1 ? 224 : 32)
                                : ((index / fps) % 2 ? 192 : 64);
      pixel[0] = pixel[1] = pixel[2] = value;
      pixel[3] = 255;
    }
    gui2_backend::frame_view frame{pixels.data(), width, height, stride,
                                  gui2_backend::frame_pixel_format::BGRA8888};
    recorder.submit_frame(frame, 1000 + index * 1000 / fps);
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (encoded.load() < index + 1 && std::chrono::steady_clock::now() < deadline)
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    assert(encoded.load() == index + 1);
  }
  assert(recorder.stop(1000 + duration_ms).success && !recorder.is_recording());
  printf("PASS fps=%d frames=%d timeline_ms=%d size=%dx%d padded_stride=%d\n",
         fps, count, duration_ms, width, height, stride);
}
