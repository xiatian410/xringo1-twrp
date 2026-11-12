> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](../../WORK-QUEUE.md)。

# 原始 codec/PCM widget 与 FF 播放接续

2026-11-12：两份 OS4 原始 A1 驱动共 12 场景通过；生产代码与镜像未变。接续减少了上一轮手填 codec 参数的边界，同时确认原厂 `asp_params` 的返回成功不能证明寄存器配置成功。实际无震动仍未修复。

## 原始执行与输入

在同一 Unicorn 上下文内执行 stock A1 probe/固件/参数/自检，然后执行 `codec_driver_probe`、`codec_probe`、真实 `ASP Mode=1` 与 `PCM Slot=1` 的 put 回调、原始 `set_tdm_slot`、`pcm_hw_params`、`component_set_sysclk`。依次调度原始 `asp_params`、`clk_en`、`asp_rx`，再提交当前生产代码捕获的 80ms SINE 请求，执行原始 FF upload/play/start 与读取合成 IRQ ring 的真实处理函数。

两份 OS4 模块 SHA256 同为 `969a17203bf56c3d5b46e3a3ee1827cb3579aaa423c2fc21508e73d2548650f6`。stock `cs40l26*` 文件、DT 档案、生产 FF 源码与先前服务执行报告均绑定哈希。前轮服务前端 PCM config 确认 mono/48kHz/tinyalsa format3；本轮为 kernel hw_params 明确提供 SNDRV S24_LE mask bit6，format-width=24 是外部函数边界，位6与当前 UAPI 头核对。

真实 backend 参数协商未执行。因此单声道场景称“按前端形状构造的夹具”，双声道场景是显式替代夹具，不能断言其中一个就是手机 DAI 的运行参数。DAI、component、codec 等对象保存在新映射的 `0x4400000` 起独立区域，与 firmware 文件、描述符及内核分配 arena 分离。codec 的原始 96 字节 GFP_ZERO 请求使用清零分配夹具。

## 结果

- 原始 codec probe 默认 BCLK=1536000Hz；mode/slot 回调生成格式缓存 0、TDM width 0、slots 2、接收槽位 2/3。hw_params 写入 rate=48000、word length=24、slot width=32；一声道计算时钟 1536000Hz，双声道为 3072000Hz。它们来自原始代码，而非手填最终缓存。
- 原始 ASP 参数回调请求四次 masked update：`0x4008/0x10000/0`、`0x4840/0x3f/24`、`0x4808/0xff000744/0x20000000`、`0x4820/0x3f3f/0x302`（地址/掩码/值）。把四次全部注入 -5 后仍继续执行，最终返回 0。
- 原始 A1 PCM 接收端请求 `0x4c00/0x7f/50`、`0x4c20/0x7f/50`、`0x4800/0x30003/0x30003`。第一写失败时立即退出；第三写失败时保留前两次成功请求，返回 -5。没有运行硬件回滚，也不宣称寄存器恢复。
- 未运行 widget、运行正常 widget、四次参数写失败、第一/第三次 PCM 接收写失败等上下文中，后续原始 FF 路径均发送相同五次参数写入与 mailbox `0x01800081`。这是控制流一致性，不能据此判断实际输出相同。显式提供开始/完成消息后，count=0、waveform completion 饱和；有 ASP 标志时 state=2，无 widget 时 state=0。

每版本六场景：no-widgets、mono-front-end-shaped-fixture、two-channel-backend-fixture、params-all-writes-error、rx-first-write-error、rx-last-write-error。

## 边界与下一步

MFD/ALSA 指针关系、组件注册、内存分配、DAI 名字符串比较、格式宽度函数、hw_params 数据布局、regmap/PM/mailbox、STOP 超时、widget 顺序、内核队列及 IRQ 消息均有显式夹具。widget 顺序仅依照已解码依赖手工调度，不是完整 DAPM dispatcher；没有音频数据、真实时钟、DSP 指令、电气回路或电机执行。未知调用与预算耗尽仍失败。

本轮不能把返回 0 的原厂 PCM 初始化当作硬件就绪，也不能把后续 FF 成功请求当作电机正常。没有依据向 Recovery 盲加 PCM 路由，未改增益、校准或保护。此处已检查的共享软件路径，仍无法选定物理无输出原因；后续重点应为每设备校准/实际寄存器状态及输出通路，而不是重复更多合成成功场景。现有只读状态采集工具尚无用户结果，不重复要求相同采集。

复现：`python3 tests/haptics_pcm_ff_join_review.py`。交付绑定审核：`python3 scripts/audit_haptics_pcm_ff_join_review.py`。证据位于 `logs/haptics-pcm-ff-join-review.json` 与按 OS4 sample 分开的原始反汇编。当前镜像以 `simulation-report.json` 为准；设置现场、自动触摸、物理震动及完整 12 组保持未完成。
