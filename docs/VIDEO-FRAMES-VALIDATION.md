# 录屏帧与时间轴离线验证

## 2026-11-12：多Cluster和关键帧边界跳转

[时间轴执行程序](../tests/video_timeline_test.py)已执行此前未运行的长于单Cluster样片验证。实际生产recorder/converter/libwebm与主机libvpx生成160×96、带stride填充的12.5秒时间轴，分别为15/30/60 FPS、188/375/750帧；每帧10块灰度区域编码自己的编号。按真实encode返回逐帧提交，不是12.5秒实时采样或吞吐测试，ASan/UBSan开启。

[结果](../logs/video-timeline.json)中三文件各有3个Cluster、关键帧位于0/5/10秒，当前生产OutputCues(false)没有Cues。EBML按长度/边界解析，不按字节模式计数。独立FFmpeg原生VP8解码全部1313帧，逐帧编号和PTS匹配；每文件在0、4.95、5、5.05、9.95、10、10.05、12.4、12.49、12.6秒跳转，共30次。每次取得首个PTS不早于目标的帧，编号及完整YUV与线性解码一致；12.49/12.6秒在最后编码帧后，正确输出为空，容器时长仍为12.5秒。

这是限定12.5秒、低分辨率、主机解码的跨Cluster/关键帧正确性，不证明小时级录屏、Cues索引效率、目标ARM64 codec、GUI播放器、完整shadow采样或1440×3200性能。未改生产/镜像，当前settings-row候选来源中的recorder实现与本组一致；目标与震动仍保持未完成。详见[交付审计](../logs/video-timeline-delivery.json)。

## 2026-11-12：独立FFmpeg原生解码与输入跳转

[新执行程序](../tests/video_ffmpeg_test.py)读取已有18份实际recorder文件，使用FFmpeg 7.1.5的Matroska demuxer与显式`-c:v vp8`原生VP8解码器；日志确认`vp8 (native)`，不再复用首轮libwebm parser/libvpx decoder。[结果](../logs/video-ffmpeg.json)核对每份文件单视频轨、尺寸/yuv420p、帧数、全部PTS与1500ms时长；解码全部帧并采样三块彩条中心YUV。原始生产源码/样片/生产者报告指纹均先校验，避免拿旧文件代表当前代码。

每文件在0/0.15/0.5/1.2秒执行四次输入端`-ss`准确跳转，合计72次，保留`-copyts`与showinfo记录，再与线性解码中对应帧的完整YUV字节比较。拥塞恢复文件PTS为0/100/200/1000ms：跳转0.15s得到200ms、跳转0.5s得到1000ms；1.2s后无新帧则输出为空，不伪造新帧。容器结束时长仍为1.5s，最后画面显示保持与“存在新编码帧”不同。彩条本身各帧相同，因此具体帧位置以PTS断言为依据，字节比较只验证同一解码结果。

FFmpeg与libavdevice Debian包通过apt-get download获取，仅dpkg-deb解压到`tools/ffmpeg-host/root`，没有安装系统包。包SHA256与apt元数据匹配，两个可执行文件、动态链接库、版本与命令来源记录在`tools/ffmpeg-host/source.json`及结果中。工具使用现有主机库，并记录213个工具/库文件哈希；这些库不进入Recovery镜像。

这是短文件、单cluster、无cues的准确输入跳转，不证明长录屏多cluster/多keyframe索引效率、VLC图形播放或实时渲染/手机性能。目标ARM64 codec、完整shadow→present采样链、长文件/全分辨率及真实存储故障仍未完成。新证据覆盖下文“独立播放器/seek待验证”中的命令行解码与短文件跳转部分；保持整体进行中。当前2773dec6镜像不变，无生产修改。

## 2026-11-12：关闭文件错误不再误报保存成功

新增[故障检查](../tests/video_failure_test.py)执行实际recorder、libwebm和主机libvpx，在stdio/codec边界注入打开失败、短写ENOSPC、flush失败、close EIO、编码失败及编码+close双失败。每种故障后在同一recorder对象重新启动/提交/停止成功，实际FILE均被关闭；ASan/UBSan开启。close替身先真实关闭FILE再返回EIO，不模拟文件描述符泄漏或重试close。

[修改前](../logs/video-failure-before.json)只有close场景失败：Finalize和fflush成功后，原始stop忽略fclose返回值，仍返回success=true及空error，上层twrp_screen_backend因此会走screenrecord_saved。[修改后六项](../logs/video-failure.json)均通过；close失败返回`Unable to close WebM recording`，若先有编码/Finalize错误则保留第一项错误。输出部分文件保留，不能把失败结果视为可用视频。

维护补丁`dtsrc/O1_asic_dual/patches/0032-recording-close-result.patch`仅修改关闭结果传播，未增加fsync或断电持久性承诺。18项彩条/时间轴/队列回归在新源码通过。新镜像`recovery-dijun-unified-recording-close.img`为installclean后make -j30构建，SHA256 `2773dec6298035e66dcb0b24deb78636207a6bbf24fab6f9490a5ad3151d83c7`，714来源和封装/新编译二进制核对通过；同镜像profile回归9组/102次阶段调用通过，见[交付报告](../logs/recording-close-delivery.json)。没有手机执行、真实磁盘满/断电或目标codec错误验证。本节生产修改使下文“无生产修改”成为对应历史批次的描述。

## 2026-11-12：新增确定性拥塞、丢帧与停止排空

当前[报告](../logs/video-frames.json)扩为18项：原有六种尺寸/FPS组合分别执行sequential、queue-drain、queue-resume三种模式。测试在首次真实VP8编码前用condition variable暂停worker，此时首帧已出队，再提交1100/1200ms两帧填满队列；1300..1900ms七帧被拒绝。没有替换编码器返回值、私有queue字段或muxer，解除门控后继续真实编码。

queue-drain在worker暂停时异步调用stop，future在50ms观察窗口未完成；解除门控后stop在5秒限额内成功，文件中恰好三帧，时间为0/100/200ms。queue-resume排空后再提交2000ms帧，得到0/100/200/1000ms四帧，跳过的时间没有被编码帧数压缩。两种模式Segment总时长均为1500ms。

填满队列后把原输入缓冲区改为白色，再提交应丢弃的七帧；解码所得每帧仍检查彩条中心YUV，因此同时检查已入队像素复制及白色溢出帧没有混入。queue-resume随后恢复同一缓冲区内容。异步stop的50ms窗口只说明future未完成，不能单独证明线程已获得调度；真正排空证据来自停止成功后的三帧文件。ASan/UBSan开启，18项全部通过，文件哈希与源码绑定见[交付检查](../logs/video-frames-delivery.json)。

这是人为编码门控下的主机行为验证，不是手机吞吐量或1440×3200性能结果。完整shadow/present采样、目标ARM64 codec、I/O/codec错误、独立播放器/seek仍待验证。未修改生产代码或构建镜像，震动/触摸及完整12组目标不作完成声明。以下六项记录描述最初sequential批次，其“未验证队列”范围现由上述检查补充。

2026-11-12，针对目标文档中未完成的 video frame checks，新增[测试入口](../tests/video_frames_test.py)和[C++ 执行程序](../tests/video_frames_test.cpp)。编译当前生产 `webm_vp8.cpp`、`rgb_to_i420.cpp`，使用仓库 libwebm 原始 muxer/parser 和主机 libvpx.so.9 执行编码与解码，不访问 framebuffer、DRM 或手机。

[结果](../logs/video-frames.json)涵盖六个组合：96×64 的 15/24/30/45/60 FPS，以及 97×65 的 30 FPS。每项提交12帧带行填充的 BGRA 红绿蓝彩条，输入为合成单调时间戳；停止时间为开始后1500ms。实际工作线程、颜色转换、VP8 编码、WebM 文件写入及 Finalize 均执行。测试包装 encoder 只记录实际 encode 返回次数，不替换编码器或返回成功。每帧等待该次数后才提交下一帧，因此本批不声称验证队列饱和/丢帧。

生成的 WebM 经 libwebm parser 验证：恰好一个 `V_VP8` 视频轨、尺寸一致、12个可读压缩帧、逐帧时间与输入相符（容许容器1ms时间尺度）、总时长1500ms。再用真实 VP8 decoder 解码每帧，核对解码尺寸和三块彩条中心 Y/U/V 值；没有以非空文件或编码返回码替代像素检查。ASan/UBSan 开启。原始 VP8/WebM 产物在 `logs/video-frames/`，报告记录各自哈希及生产源码、测试、编解码依赖指纹。

同时验证重复 start 被拒绝、正常 stop 后 recording=false、再次 stop 被拒绝。未改动生产代码，不生成新 Recovery 镜像。

范围限制：主机 libvpx 编码器/解码器与 Android 目标库不是同一构建；没有执行目标 ARM64 codec、真实1440×3200采样/性能、完整 display shadow→present→screen backend 链、队列丢帧、存储/编码故障、seek 或独立播放器。奇数尺寸解码通过不证明每个边缘色度像素正确，本批只采样三块中心。视频功能仍有未覆盖工作，机器报告把笼统的“video frame checks”收窄为这些明确剩余项，保持该组未完成；触摸 P0、震动及全部12组目标状态不变。

复现：

```sh
python3 tests/video_frames_test.py > logs/video-frames-test.log 2>&1
```
