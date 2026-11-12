# OS4 原厂服务线程、XML 与首次 PCM 启动

2026-11-12：原厂 PCM 构造本身没有控制写入，但它创建的动态效果线程首次运行会配置音频路径，即使当前没有动态效果。此前“普通 on 函数自身不调用 mixer”的证据不能排除这项后台初始化依赖；本轮将它列为下一步需要核对的差异，没有将它认定为现场无震动根因。

证据为[执行程序](../tests/haptics_service_tail_review.py)、[14 场景结果](../logs/haptics-service-tail-review.json)和[来源核对](../scripts/audit_haptics_service_tail_review.py)。两份 OS4 服务及 AAC 库沿用[此前固定摘要](HAPTICS-PCM-INITIALIZATION.md)；原厂 `libtinyalsa.so` 两份同为 `c5008f3a3e1257e0f4042331ebc6279ca04347d2027ac5be4d8b0ddee2350c7b`，本组只执行其中的帧数转换叶函数。服务外部符号槽位来自 `llvm-readelf` 对原始 Android 压缩重定位的解码，输出也绑定摘要。

## 执行范围

- 先执行原始 hash 容器静态初始化 `0x11820..0x118b0`，不手工填入算法名单或波形映射。
- 继承输入发现、PCM/数据构造和 AAC init 的部分构造上下文；替代设备/config-map 范围 `0x13084..0x1324c`、校准恢复本体仍未执行。
- 连续接上 `0x1349c..0x13bb8`，执行原始动态效果线程构造、run 请求、XML 消费者及低功耗/保护时间属性读取。外层省略过 prologue，因此显式提供对象寄存器和足够大的栈工作区，停在 epilogue 之前；不称完整 constructor/main。
- Android Thread/RefBase、pthread 与 libxml 是边界。XML 节点布局由真实 XML 建立，保留 text/tail 空白节点；内容/字符串接口为夹具，实际分支、整数转换调用、hash 插入/rehash 和映射消费者为原始指令。未执行 libxml parser 二进制或真实分配器。
- run 请求成功时，在显式串行调度边界进入原始 `threadLoop(0x272f0)`。首次执行到 `pthread_cond_timedwait` 即停止，不伪造等待完成。真实线程可能先于 XML 完成而运行，本组在 XML 消费之后调度它，不验证并发顺序。
- socket/ALSA/mixer 返回值是夹具。`pcm_open` 本体没有执行；同一合成 PCM 对象保存原始请求的 config，`pcm_frames_to_bytes` 使用映射后的原厂叶函数执行，1024 帧得到 4096 字节。没有 ALSA dispatcher、DAPM、驱动、DSP 或电机。
- 最后在同一对象上执行普通 on，使用 XML 消费者写入的 long-id，不再手工填该全局；恢复完成标志和空 callback 仍显式提供，不运行计时线程或 Binder。

执行预算：PCM/AAC/constructor 区间各有限 100 万指令/10 秒，原始 worker 最多 10 万指令/2 秒并必须停在首个 timed wait。未知调用与预算耗尽均失败，没有设备或主机硬件访问。

## 发现

正常启动分支的请求顺序为：

1. 打开 `/dev/socket/vibrator_audio_socket_0`，发送 72 字节报文，前三个 32 位字为 `[42,1,1]`，其余为零。回复 `{1,0}` 是显式 ACK 夹具，不能当成真实音频服务响应；本组没有擅自解释报文的电源语义。
2. 设置 `XR_TDM7_RX` 数组 `[48000,24,4]`。
3. 依次请求 `Haptics Source=1`、`ASP Mode=1`、`ASP PCM Slot=1`、`audio_tdm_fmtchs=8`、`XR_TDM7_RX Mixer XR_media7=1`。Source=1 的 PCM 含义见[原厂 DAPM 核查](HAPTICS-ADAPTATION.md)。
4. 请求 `pcm_open(card=0, device=9, flags=0)`，config 前八字为 `[1,48000,480,4,3,120,2147483647,120]`。读到合成 ready/buffer 后，原始转换得 4096 字节，再进入首次等待；没有提交 PCM 音频样本。

因此原厂后台线程确实有额外音频初始化，不能把“构造/on 范围未写控制”扩大为整个服务未写控制。相应硬件是否就绪、这些请求是否影响独立 FF 输出仍未证明；没有向 Recovery 直接复制这组写入。

| 场景 | 原始执行结果 |
| --- | --- |
| 正常 XML | long-id=31，16 项波形映射与 no_dvl/no_svc 集合逐项和文件一致 |
| XML 缺失 | 原始 long-id 默认值为 35，映射/集合为空；线程仍可请求 PCM |
| XML 无 long_vib_id | long-id 保留 35，其他映射/集合正常建立 |
| XML long-id 合成改为 42 | 原始消费者写入 42，随后普通 on 提交 CUSTOM42，证明不再靠预填全局绕过消费 |
| Thread run 返回 -11 | 构造仍消费 XML/属性；本组不调度未启动的 worker，普通 on 仍提交 CUSTOM31 |
| XR_TDM7_RX 数组写返回 -5 | 跳过后续五项 mixer value 写入，但仍请求 pcm_open 并进入等待；PCM 请求成功不能证明此前路由配置成功 |
| 音频 socket poll 超时 | 原始发送重试两次后继续配置 mixer/请求 PCM，不把等待结束当成音频服务应答 |

两份 OS4 各 7 场景，共 14。普通 on 在所有场景仍提交 gain100、文件/默认值对应的 CUSTOM 编号和 play；这是软件调用证据，不证明回调计时、驱动接受或物理输出。恢复标志为边界，不能说本组完成校准恢复。

## 交付与下一步

本轮没有改生产路径或重新构建。当前仍是 `recovery-dijun-unified-mtp-reset.img`（SHA256 `046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27`），定向审计绑定当前镜像及 735 份生产来源；历史总审计不作为本轮通过依据。

下一步核对原厂 ASP/PCM 配置回调与独立 SINE/CUSTOM 播放之间的状态关系，及音频 socket 对端具体处理。仍缺完整服务生命周期、实时线程并发、实际 ALSA/DAPM/寄存器、设备校准/供电/保护状态；震动、设置现场、触摸自动恢复及完整 12 组目标保持进行中。现有设备日志请求保留，不新增同类重复采集要求。

复现：

```bash
python3 tests/haptics_service_tail_review.py > logs/haptics-service-tail-review.log 2>&1
python3 scripts/audit_haptics_service_tail_review.py > logs/haptics-service-tail-review-audit.log 2>&1
```
