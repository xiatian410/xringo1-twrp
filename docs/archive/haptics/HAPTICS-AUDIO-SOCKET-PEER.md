> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](../../WORK-QUEUE.md)。

# 原厂震动音频 socket 对端核查

2026-11-12：两份 OS4 的原始音频服务代码共 34 场景通过。新增证据厘清了 socket 回复的含义，未修复或证明物理震动。生产镜像不变，当前交付仍以 `simulation-report.json` 为准。

## 证据与结果

原厂 `vendor/etc/init/android.hardware.audio.service-aidl.rc` 将 `vibrator_audio_socket_0` 定义为音频 AIDL 服务的 seqpacket socket。处理函数位于 `vendor/lib64/libaudioserviceimpl.so`。旧版与正式版库不同，分别绑定 SHA256 `b6387068491553e46600984c889cac1f4fc76ba4f6de1fd8125b164e183d18f8`、`eec232a6a96a6b38cca3834e740047be33adc05fc9019087826da5aaeb4a261b`；函数入口和 GOT 从各自 ELF 动态符号与实际重定位解码，不共用地址假设。

输入取自上一轮真实原厂代码执行捕获的启动请求：72 字节，前三个小端 uint32 为 `[42,1,1]`，其余为零。这里只是在不同 Unicorn 上下文之间传递原始消息，没有运行两个 Android 进程或真实 socket。

原始 `audio_handle_client_sock`、`ResourceManager::noteHapticStreamStatusChange`、`MiModulePrimary::noteHapticStreamStatusChange`、`MiStreamOutPrimary::updateA2HMode` 实际执行，得到：

- 编号 42 消费消息偏移 8 的一个字节作为震动流是否活动；偏移 9 单独置 1 仍被当作不活动。
- 正常编号、未知编号、短读、EOF 和 read=-1 路径均请求发送相同的两字节 `01 00`。原始处理在记录读错误之后仍解析预清零缓冲区。短读仅有编号时可错误通知“不活动”，短读 9 字节已能通知“活动”。这是原厂行为观察，不是本项目新增或移植的实现。
- feature 关闭时跳过 ModulePrimary；空输出列表或弱引用过期时没有 A2H 更新。
- 合成的活动音频流 usecase 匹配后，原始代码更新 `vibratorStreamStatus` 并进入 `updateA2HMode(false)`。使用显式流状态/app 许可边界时，震动流活动不请求 `setA2HParameter`；震动流不活动且许可时请求 `Haptics Source=2`，app 不许可时请求 `Haptics Source=0`。usecase 不匹配不更新。这支持“协调已有流的音频转震动模式”的解释，不支持把回复当成震动供电就绪。
- EPOLLHUP 删除客户端，不回复；没有输入事件时不读写；write=-1 不撤销前面已经发出的状态通知。

每份 OS4 的 17 场景：startup、off、unknown-command、short-command、short-state、read-eof、read-error、hangup、no-input、write-error、feature-disabled、expired-stream、state-high-byte-only、active-on、active-off、active-off-app-denied、active-unmatched。

## 明确边界

singleton 已初始化、Cirrus A2H 支持标志、输出流/许可 usecase、空 app 名列表、流状态和 app 许可均为显式内存或调用夹具。socket read/write、日志、mutex、weak lock、getUsecase、setA2HParameter 是边界；没有启动服务或执行真实 ALSA 控制。shared count 的原始原子减法执行，但只在串行模拟中运行，不验证竞争与对象释放。未知调用、未审查函数地址和 100000 指令/2 秒预算耗尽均使检查失败。

本轮没有执行 `setA2HParameter` 的内部路由和媒体策略，也未执行 DAPM、音频 DSP、震动 DSP 或电机。此前背景 worker 的 PCM 初始化差异仍需继续分析，不能以 socket 不直接供电来排除所有音频依赖，也不能据此给 Recovery 增加 PCM 控制写入。

下一重点：原厂 ASP 模式、DAPM 回调改变的状态如何影响独立 FF SINE/CUSTOM；同时保留按设备校准恢复/实际读回与 IRQ 完成的未知边界。设置现场结果尚未到达，自动触摸恢复、物理震动及完整 12 组目标均未完成。

## 复现

```bash
python3 tests/haptics_audio_peer_review.py
python3 scripts/audit_haptics_audio_peer_review.py
```

结果见 `logs/haptics-audio-peer-review.json`，原始函数/PLT 反汇编及重定位清单按 OS4 sample 分别保存于 `logs/*-haptics-audio-peer*`。交付绑定审计为 `logs/haptics-audio-peer-review-audit.json`。
