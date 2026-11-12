# 震动适配记录

**状态：OS4 震动已修好，用户确认正常。** 不属于当前待办或例行检查；仅出现新故障或直接回归证据时重新打开。当前候选见 [交付报告](../simulation-report.md)。

本页合并原震动总览与早期 OS4 单版本说明，删除重复候选、逐轮检查数字及已过期的“下一步”。原始记录可从 Git 历史追溯；独立技术说明和验证源码保留。

## 保留的实现要点

- 原厂驱动使用 FF 能力发现、效果上传、播放及擦除流程；不能仅凭模块加载、input 注册或播放回执判断物理输出。
- OS4 的 Cirrus 驱动位于 `xring_audio_hw_third.ko`；OS2 / OS3 位于 `xring_smartpa.ko`。按精确 profile 选择组件，不跨版本混装。
- OS4 原厂属性及 DT 的默认共振频率为 130 Hz。生产 FF 的频率、幅度和波形以维护源码为准；不得根据旧调查推测重新调参或改写 persist 校准。
- 原厂 ODM 与 vendor 的部分同名 Cirrus 参数不同。固件按档案选取并发布到 RAM 路径，避免 vendor / ODM 临时挂载遮蔽资源。
- 早期修正补齐 recovery-only 的 `firmware_load` 权限定义及相应读取规则。旧拒绝日志来自触摸固件请求，不能据此认定它是当时无震动的唯一原因。
- FF 后台 owner 管理请求和描述符生命周期；能力查询被中断时保留已有效果，上传、播放错误仍按各自路径处理。

生产补丁、顺序与摘要由 [series.json](../dtsrc/O1_asic_dual/patches/series.json) 管理。上文说明实现约束，不是重新运行检查的要求。

## 技术参考

以下文档保留各自独立的调用链、失败路径和模拟边界；其中旧候选和未完成状态均属于历史。

| 主题 | 文档 |
| --- | --- |
| 原厂驱动、DSP 固件与地址解析 | [驱动模拟](HAPTICS-DRIVER-EMULATION.md) · [固件解析](HAPTICS-FIRMWARE-EMULATION.md) |
| 注册、效果与后台生命周期 | [生命周期](HAPTICS-LIFECYCLE-EMULATION.md) · [播放 worker](HAPTICS-PLAYBACK-EMULATION.md) |
| GUI 请求、后台执行与能力查询 | [后台 owner](HAPTICS-WORKER-ADAPTATION.md) · [FF 查询中断](HAPTICS-PROBE-ADAPTATION.md) |
| 参数和诊断 | [请求追踪](HAPTICS-REQUEST-TRACE.md) · [状态采集](HAPTICS-STATE-COLLECTION.md) · [工具源码](../tools/haptics-diagnostic/README.md) |
| PCM 初始化与播放接续 | [初始化](HAPTICS-PCM-INITIALIZATION.md) · [PCM / FF](HAPTICS-PCM-FF-STATE.md) · [ASP / FF](HAPTICS-ASP-FF-STATE.md) |
| 原厂服务与音频对端 | [线程与 XML](HAPTICS-SERVICE-THREAD-XML.md) · [socket 对端](HAPTICS-AUDIO-SOCKET-PEER.md) |

## 证据边界

用户确认是对应设备现场结果，不自动扩展为所有固件逐项验收。离线报告中的寄存器、PM、DSP、input core、ALSA、线程或 IRQ 替身只能证明其声明的软件范围；合成成功不代替物理观察。

历史报告和输入绑定保存在 `simulation-report.json`。原始设备日志、镜像及专有固件不公开上传，也不为刷新日期重复执行旧检查。
