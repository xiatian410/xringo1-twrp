# 版本与功能状态

目标设备：Xiaomi 15S Pro（dijun / XRING O1）。当前交付见 [验证报告](simulation-report.md)，需求与验收见 [适配目标](ADAPTATION-GOALS.md)。本文不把历史模拟数量作为功能通过率。

## 固件档案

| Profile | 系统样本 | 范围 |
| --- | --- | --- |
| `os2-initial` | OS2.0.121.0.VODCNXM | Android 15，独立 ABI / 服务组合 |
| `os2-final` | OS2.0.209.0.VODCNXM | Android 15，独立 ABI / 服务组合 |
| `os3-initial` | OS3.0.4.0.WODCNXM | Android 16，优先适配 |
| `os3-final` | OS3.0.304.0.WODCNXM | Android 16，优先适配 |
| `os4-current` | OS4.0.0.19.XODCNXM | Android 17，旧样本 |
| `os4-stable` | OS4.0.4.0.XODCNXM | Android 17，首个正式版样本 |

六份档案已进入同一候选，按组件身份选择，不允许只凭内核主次版本混装。首尾样本不代表所有中间版本；样本来源和组件差异见 [固件映射](docs/FIRMWARE.md)。

## 功能范围

共享源码的离线检查不代表六个版本都获得实机验收。下表为当前项目状态，具体替身与输入范围以主题文档为准。

| 功能 | 已有实现 / 证据 | 仍未完成的边界 |
| --- | --- | --- |
| profile / 模块 / 启动 | 六份独立档案，最终镜像选择 / 激活回放 | 完整 kernel / init / LP 启动 |
| 触摸 / 按键 | 原始驱动与输入路径分析；手动 raw0 恢复有用户事件证据 | OS4 自动启动报告、GUI 与恢复 |
| OS4 震动 | **用户确认已正常，已解决** | 不例行重查；其他版本不自动继承实机结论 |
| 设置 | 持久化、导航与失败路径；用户确认 backup-manifest 基线正常 | 不外推所有镜像 / 页面均已实机通过 |
| 时间 / 电量 / 温度 | 状态读取与 RTC 回调；温度避让中央摄像头 | 冷启动 / hctosys、实际漂移、传感器精度 |
| metadata / FBE | 原厂服务重定位、namespace 检查、启动与 CE 失败清理 | 完整 TEE / Binder / 工作资料 / 合成卷集成 |
| 分区 / NV | 刷入目标与 NV GUI 策略；保留内部 fstab | 完整 GUI / mount / I/O 故障生命周期 |
| OTG | 修正内部 UFS 误枚举，列表 / 选择离线覆盖 | manager / USB、写入中移除 |
| MTP | 时间、原子上传、目录与会话 / 取消 / 重置修正 | 临时文件崩溃归属、完整端点 / Windows 集成 |
| ZIP / sideload | 原始安装链、真实 ARM64 无害 updater、协议与收尾 | 完整 ARM64 Recovery / USB / FUSE |
| OTA / A/B | 原始 OS4.0.4 整包在同次明确模型运行中接通 ZIP 验签 / 十份 COW 初始化 / 真实 ARM64 引擎全部 payload 操作与最终哈希 / postinstall / 完成状态 / 父安装成功；0090 修复初始化失败空指针崩溃 | 源 LP 为合成输入，内核映射 / 挂载 / HAL / 槽位有替身，真实启动与重启合并未验收；见[整包模型](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success)与[初始化范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-initialization) |
| 备份 / 恢复 | 编解码、摘要发布、完成清单、失败恢复路径 | GUI 全流程、稀疏空洞、断电与内容真实性 |
| 文件系统工具 | 普通文件上的 ARM64 工具及修复返回值；扩容尺寸修正 | 完整格式化 / 写入 / 修复接续 |
| 截图 / 录屏 | 像素、队列、VP8 / WebM 时间轴与故障检查 | 目标 ARM64 codec / 显示接续、全分辨率长期性能 |
| Wi-Fi | 当前未启用 | 不列为已支持 |

## 证据等级

- **S0**：提取且有来源 / 哈希的固件证据。
- **S1**：源码、配置、ABI、依赖等静态检查。
- **S2**：生产逻辑与明确替身结合的主机 / ARM64 离线执行。
- **S3**：构建、镜像内容与来源核对。
- **H**：限定版本和镜像的历史用户设备观察。
- **U**：硬件边界未验证，不等于失败，也不应标为已成功。

当前完整目标仍进行中。已有结果在相关输入不变时复用；尚未完成的事项集中维护在 [工作队列](docs/WORK-QUEUE.md)。
