# 历史技术记录

这里保存已解决问题的调查细节与旧阶段交付。它们用于追溯实现决定，不是当前待办，也不要求重复运行历史检查。当前状态见[交付报告](../../simulation-report.md)与[工作队列](../WORK-QUEUE.md)。

## 已解决：OS4 震动

用户已确认 OS4 震动正常。实现摘要见[震动适配记录](../HAPTICS-ADAPTATION.md)，独立驱动、DSP、PCM 和服务调查保存在 `haptics/` 中。历史文中的“未解决”“下一步”和旧镜像只对应当时阶段，不覆盖用户后续确认。

- 驱动与固件：[驱动](haptics/HAPTICS-DRIVER-EMULATION.md) · [固件 / DSP](haptics/HAPTICS-FIRMWARE-EMULATION.md)
- 请求与生命周期：[后台 owner](haptics/HAPTICS-WORKER-ADAPTATION.md) · [注册生命周期](haptics/HAPTICS-LIFECYCLE-EMULATION.md) · [播放 worker](haptics/HAPTICS-PLAYBACK-EMULATION.md) · [能力查询](haptics/HAPTICS-PROBE-ADAPTATION.md)
- 参数与采集：[请求追踪](haptics/HAPTICS-REQUEST-TRACE.md) · [状态采集](haptics/HAPTICS-STATE-COLLECTION.md)
- PCM 与服务：[初始化](haptics/HAPTICS-PCM-INITIALIZATION.md) · [PCM / FF](haptics/HAPTICS-PCM-FF-STATE.md) · [ASP / FF](haptics/HAPTICS-ASP-FF-STATE.md) · [线程与 XML](haptics/HAPTICS-SERVICE-THREAD-XML.md) · [音频对端](haptics/HAPTICS-AUDIO-SOCKET-PEER.md)

## 历史阶段

[0063 / 0064 六组有限维护](BOUNDED-MAINTENANCE.md)保留温度避让、扩容边界和 OTA 同步拒绝的阶段交付。此前的六组限制已解除，不作为当前执行范围。

## 归档规则

保留有独立技术内容的记录；重复入口合并到所属主题。移动时更新文档和工具引用，不重写历史报告的来源哈希。原始日志、固件、镜像和本地缓存不随归档公开；构建依赖、固定补丁和复现脚本继续保留。
