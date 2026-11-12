// Actual recorder -> WebM parser -> VP8 decoder. No framebuffer/device access.
#include <cassert>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <condition_variable>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "webm_vp8.h"
#include "mkvparser/mkvparser.h"
#include "mkvparser/mkvreader.h"
#include "vpx/vp8dx.h"
#include "vpx/vpx_decoder.h"
#include "vpx/vpx_encoder.h"

static std::atomic<int> encodes{0};
static std::mutex gate_mutex;
static std::condition_variable gate_condition;
static bool gate_enabled = false, gate_entered = false, gate_released = false;
extern "C" vpx_codec_err_t __real_vpx_codec_encode(vpx_codec_ctx_t*, const vpx_image_t*,
    vpx_codec_pts_t, unsigned long, vpx_enc_frame_flags_t, unsigned long);
extern "C" vpx_codec_err_t __wrap_vpx_codec_encode(vpx_codec_ctx_t* ctx, const vpx_image_t* img,
    vpx_codec_pts_t pts, unsigned long duration, vpx_enc_frame_flags_t flags, unsigned long deadline) {
  if (gate_enabled && encodes.load() == 0) {
    std::unique_lock<std::mutex> lock(gate_mutex);
    gate_entered = true;
    gate_condition.notify_all();
    assert(gate_condition.wait_for(lock, std::chrono::seconds(5), [] { return gate_released; }));
  }
  auto result = __real_vpx_codec_encode(ctx, img, pts, duration, flags, deadline);
  ++encodes;
  return result;
}

int main(int argc, char** argv) {
  assert(argc == 5 || argc == 6);
  const std::string mode = argc == 6 ? argv[5] : "sequential";
  assert(mode == "sequential" || mode == "queue-drain" || mode == "queue-resume");
  gate_enabled = mode != "sequential";
  const int width = std::stoi(argv[2]), height = std::stoi(argv[3]), fps = std::stoi(argv[4]);
  const int stride = width * 4 + 16;
  std::vector<uint8_t> pixels(stride * height, 0xcd);
  for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
    auto* p = pixels.data() + y * stride + x * 4;
    p[0] = x >= width * 2 / 3 ? 255 : 0;
    p[1] = x >= width / 3 && x < width * 2 / 3 ? 255 : 0;
    p[2] = x < width / 3 ? 255 : 0;
    p[3] = 255;
  }
  gui2_backend::webm_vp8_recorder recorder;
  assert(recorder.start(argv[1], width, height, fps, 1000).success);
  assert(!recorder.start(argv[1], width, height, fps, 1000).success);
  std::vector<int> expected_times;
  gui2_backend::frame_view frame{pixels.data(), width, height, stride,
                                gui2_backend::frame_pixel_format::BGRA8888};
  const auto wait_encodes = [](int number) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (encodes.load() < number && std::chrono::steady_clock::now() < deadline)
      std::this_thread::sleep_for(std::chrono::milliseconds(1));
    assert(encodes.load() == number);
  };
  if (!gate_enabled) {
    for (int i = 0; i < 12; ++i) {
      expected_times.push_back(i * 1000 / fps);
      recorder.submit_frame(frame, 1000 + expected_times.back());
      wait_encodes(i + 1);
    }
  } else {
    // Block before the real first encode. Its packet is already popped,
    // leaving exactly two queue slots, independent of host scheduling speed.
    recorder.submit_frame(frame, 1000);
    {
      std::unique_lock<std::mutex> lock(gate_mutex);
      assert(gate_condition.wait_for(lock, std::chrono::seconds(5), [] { return gate_entered; }));
    }
    recorder.submit_frame(frame, 1100);
    recorder.submit_frame(frame, 1200);
    const auto original_pixels = pixels;
    std::fill(pixels.begin(), pixels.end(), 255);
    // Full queue: these white frames must not appear. Accepted queued frames
    // must retain their copied color bars despite mutation of the input.
    for (int time : {1300, 1400, 1500, 1600, 1700, 1800, 1900})
      recorder.submit_frame(frame, time);
    expected_times = {0, 100, 200};
    std::future<gui2_backend::capture_result> stopping;
    if (mode == "queue-drain") {
      stopping = std::async(std::launch::async, [&] { return recorder.stop(2500); });
      assert(stopping.wait_for(std::chrono::milliseconds(50)) == std::future_status::timeout);
    }
    {
      std::lock_guard<std::mutex> lock(gate_mutex);
      gate_released = true;
    }
    gate_condition.notify_all();
    if (mode == "queue-drain") {
      assert(stopping.wait_for(std::chrono::seconds(5)) == std::future_status::ready);
      assert(stopping.get().success && !recorder.is_recording());
    } else {
      wait_encodes(3);
      std::copy(original_pixels.begin(), original_pixels.end(), pixels.begin());
      recorder.submit_frame(frame, 2000);
      wait_encodes(4);
      expected_times.push_back(1000);
    }
  }
  if (mode != "queue-drain")
    assert(recorder.stop(2500).success && !recorder.is_recording());
  assert(!recorder.stop(2500).success);
  mkvparser::MkvReader reader;
  assert(reader.Open(argv[1]) == 0);
  mkvparser::EBMLHeader header;
  long long pos = 0;
  assert(header.Parse(&reader, pos) == 0);
  mkvparser::Segment* raw = nullptr;
  assert(mkvparser::Segment::CreateInstance(&reader, pos, raw) == 0 && raw);
  std::unique_ptr<mkvparser::Segment> segment(raw);
  assert(segment->Load() >= 0);
  auto* tracks = segment->GetTracks();
  assert(tracks && tracks->GetTracksCount() == 1);
  auto* track = tracks->GetTrackByIndex(0);
  assert(track && track->GetType() == 1 && std::string(track->GetCodecId()) == "V_VP8");
  auto* video = static_cast<const mkvparser::VideoTrack*>(track);
  assert(video->GetWidth() == width && video->GetHeight() == height);
  assert(std::abs(segment->GetDuration() - 1500000000LL) <= 1000000);
  vpx_codec_ctx_t decoder{};
  assert(vpx_codec_dec_init(&decoder, vpx_codec_vp8_dx(), nullptr, 0) == VPX_CODEC_OK);
  int count = 0;
  for (auto* cluster = segment->GetFirst(); cluster && !cluster->EOS(); cluster = segment->GetNext(cluster)) {
    const mkvparser::BlockEntry* entry;
    assert(cluster->GetFirst(entry) == 0);
    while (entry && !entry->EOS()) {
      auto* block = entry->GetBlock();
      assert(block->GetTrackNumber() == track->GetNumber() && block->GetFrameCount() == 1);
      assert(count < (int)expected_times.size());
      assert(std::abs(block->GetTime(cluster) - (long long)expected_times[count] * 1000000) <= 1000000);
      const auto& frame = block->GetFrame(0);
      std::vector<uint8_t> compressed(frame.len);
      assert(frame.Read(&reader, compressed.data()) == 0);
      assert(vpx_codec_decode(&decoder, compressed.data(), compressed.size(), nullptr, 0) == VPX_CODEC_OK);
      vpx_codec_iter_t iterator = nullptr;
      auto* image = vpx_codec_get_frame(&decoder, &iterator);
      assert(image && image->d_w == (unsigned)width && image->d_h == (unsigned)height);
      for (int col = 0; col < 3; ++col) {
        const int x = width * (2 * col + 1) / 6;
        const int expected_y[] = {82, 144, 41};
        const int expected_u[] = {90, 54, 240};
        const int expected_v[] = {240, 34, 110};
        const int actual = image->planes[0][(height / 2) * image->stride[0] + x];
        assert(std::abs(actual - expected_y[col]) <= 8);
        assert(std::abs(image->planes[1][(height / 4) * image->stride[1] + x / 2] - expected_u[col]) <= 8);
        assert(std::abs(image->planes[2][(height / 4) * image->stride[2] + x / 2] - expected_v[col]) <= 8);
      }
      assert(!vpx_codec_get_frame(&decoder, &iterator));
      ++count;
      const mkvparser::BlockEntry* next;
      assert(cluster->GetNext(entry, next) == 0);
      entry = next;
    }
  }
  assert(count == (int)expected_times.size());
  assert(vpx_codec_destroy(&decoder) == VPX_CODEC_OK);
  printf("PASS mode=%s width=%d height=%d fps=%d decoded_frames=%d duration_ns=%lld padded_stride=%d center_YUV_checked=1\n",
         mode.c_str(), width, height, fps, count, segment->GetDuration(), stride);
}
