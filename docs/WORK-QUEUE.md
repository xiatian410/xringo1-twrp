# 工作队列

本文只记录当前优先级和未完成边界；历史测试流水账不再作为执行队列。目标见 [ADAPTATION-GOALS.md](../ADAPTATION-GOALS.md)，候选与交付见 [simulation-report.md](../simulation-report.md)。

## 执行规则

- 工作范围不限于此前六组，按具体故障与实现决定排序，不因此开始全量重复检查。
- **OS4 震动已修好、用户确认正常，退出例行检查。** 仅新报故障或直接回归证据可重新打开。
- backup-manifest 基线设置正常的用户确认保留，没有新故障不重复诊断。
- 相同源码、输入和范围直接复用结果。必要检查通过就结束本批；不反复增加等价夹具或重编未改镜像。
- 只在离线环境操作普通临时文件；不连接手机或操作物理块设备。
- 每个连贯修改批次完成后同步 GitHub，镜像、原厂 blob、私钥和原始日志不公开。

## 优先事项

| 优先事项 | 已知情况 | 下一步与边界 |
| --- | --- | --- |
| 容量刷新页面停留 | 现场日志显示后台约 5.15 秒完成，界面仍停留；根因未定位 | 追踪后台完成到页面呈现的状态传递。已有日志窗口、页面生命周期和 CLI FIFO 修正尚未证明与现场有关；不要求重复触发采集。见[调查记录](REFRESH-STUCK-INVESTIGATION.md) |
| OTA / A/B 快照生命周期 | 两份完整 OS4 payload 已离线执行；快照错误传播、snapuserd EOF 崩溃已修正，读取、合并及指定进程退出点恢复已有证据 | 接续多窗口或 SnapshotManager 到实际服务端的流程。真实 init / 内核映射、硬件断电与任意撕裂未验证；不重跑已覆盖退出点。见[OTA 实现与证据](OTA-OPERATION-COW.md) |
| 文件系统完整生命周期 | 清除错误传播、媒体保留、格式转换和 ARM64 工具接续已维护 | 处理完整挂载 / GUI / 加密与 I/O 故障收尾，不重复已通过的命令和内容检查。见[文件系统说明](FILESYSTEM-TOOLS-EXECUTION.md) |
| 其他具体缺陷 | 触摸自动启动、安全服务、多用户、备份恢复和 USB 集成仍有缺口 | 按下表剩余边界及新证据排序，每批明确实现决定和结束条件，不启动全量重复审计 |

## 已维护事项的入口

这些事项不重新立项。生产修正、各阶段证据和剩余限制在所属主题维护；当前镜像以[交付报告](../simulation-report.md)为准。

| 事项 | 文档 |
| --- | --- |
| 刷入目标、NV 界面限制 | [分区操作](PARTITION-ACTIONS.md) |
| OTG / UFS 误识别、存储选择 | [挂载与存储](MOUNT-LIST-EXPLANATION.md) |
| 温度避让摄像头、状态显示 | [状态与 RTC](STATUS-ADAPTATION.md) |
| 加载页 XRING O1 名称 | [阶段交付记录](archive/BOUNDED-MAINTENANCE.md) |
| 备份目录重命名 / 删除、摘要发布 | [备份会话](BACKUP-SESSION-ADAPTATION.md) |
| 日志导出错误传播、页面日志生命周期 | [操作反馈](OPERATION-FEEDBACK-ADAPTATION.md) |
| MTP 日期、原子上传、格式与会话 | [上传](MTP-ATOMIC-UPLOAD.md) · [对象](MTP-OBJECTS-ADAPTATION.md) · [控制与事件](MTP-CONTROL-ADAPTATION.md) |

## 仓库维护

README 只保留项目简介、状态、构建入口与导航；历史流水账在所属主题查询。重复说明合并后删除旧入口，无引用的一次性脚本删除，既有版本由 Git 历史追溯。保留固定补丁、构建依赖和独立技术记录；格式与同步规则见[维护指南](../MAINTENANCE.md#文档维护)。仓库整理不改变生产功能，不重编镜像。

## 完整目标的十二组剩余边界

这些是范围分类，不是重新启动十二轮检查。硬件 U 单独记录；不要为了关闭 U 无限制增加模拟。

| 组 | 剩余边界 |
| --- | --- |
| 1 触摸 | 自动冷启动报告、GUI / 唤醒；手动 raw0 恢复不代替自动启动证据 |
| 2 安全服务 / 解密 | 原厂服务初始化、真实 init / namespace / Binder / TEE、合成加密卷接续 |
| 3 多用户 | 父绑定工作资料协议、同步调用安全取消、真实 CE 驱逐 / 重挂载 |
| 4 MTP | 临时文件崩溃归属、媒体元数据、完整端点 / Reset / USB / Windows 集成 |
| 5 备份恢复 | codec / GUI 全流程、稀疏空洞、内容真实性与断电持久性 |
| 6 文件系统 | 完整格式化 / 写入 / 修复接续，GUI / manager / I/O 故障收尾 |
| 7 RTC | 完整 probe / hctosys、冷启动读失败、实际漂移；无证据不增加偏移 |
| 8 视频 | ARM64 codec / 显示影子帧接续、全分辨率与长期性能 |
| 9 OTG | 完整 manager / USB 接续、写入中移除；不重复 UFS 排除夹具 |
| 10 启动 / LP | 完整 ramdisk 合并、kernel / init / LP 启动；脚本回放不等同完整启动 |
| 11 温度 | 传感器精度 / Android 注册；摄像头避让已交付，不再重复同类布局检查 |
| 12 安装 / GUI / OTA | 原厂 payload / update_engine / 快照、完整页面与实际 USB / FUSE 侧载 |

精确输入与历史结果保留在 `simulation-report.json`；当前简表见 [兼容状态](../compatibility-matrix.md)。
