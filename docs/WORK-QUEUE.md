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

1. **容量刷新页面停留**：已有现场日志显示后台约 5.15 秒完成，但界面没有结束，根因仍未定位。0070 / 0072 已修正日志窗口与页面生命周期，0077 已修正 CLI FIFO 阻塞；现场尚未证明这些路径参与故障，不据此认定已修复。已有结果保持，不要求重复触发采集。下一步仅针对能解释后台完成与界面停留之间差异的新证据推进。见 [调查记录](REFRESH-STUCK-INVESTIGATION.md)。
2. **OTA / A/B 快照生命周期**：两份完整原厂 OS4 payload 已由实际 ARM64 DeltaPerformer、静态 / VABC writer 与最终校验器执行；分区映射仍为普通文件替身。0069 已修正实际 SnapshotManager 状态文件同步失败误成功，后续接续原始 PostinstallRunnerAction、控制器重建与持久状态重试。原厂 otapreopt 的 Recovery 退出条件已有独立执行证据。下一边界是实际映射 / 取消 / 合并，以及 payload 到 SnapshotManager 收尾的完整接续；不重复完整 payload、解析、格式或退出条件检查。详见 [OTA 实现与证据](OTA-OPERATION-COW.md)。0078 已修正取消清理失败仍报告成功，实际 ARM64 取消十项及相关收尾 / postinstall 回归通过，清理构建794来源 / 六profile；下一步不重复取消状态文件检查，仍聚焦实际映射 / 删除 / 合并接续，见[取消错误传播](OTA-OPERATION-COW.md#snapshot-cancel)。0079 另修正解除映射错误汇总与校验器重映射 / 成功门控，校验器9 / 控制器8及共享控制器必要回归通过，清理构建796来源 / 六profile。该软件返回路径收尾，不重复等价夹具；实际 mapper / snapuserd / 删除 / 合并仍待接续，见[解除映射范围](OTA-OPERATION-COW.md#snapshot-unmap)。 后续实际 SnapshotManager 逐层清理和原控制器接续15场景已补齐，有状态 mapper / image 替身核对顺序、部分状态与重试；无生产修正或重编。实际 manager/client 的真实 socketpair 五项现已接续，对端仍为协议替身；服务端后续在真实 Unix socket 复现半关闭 EOF 导致空 vector 访问：原 ARM64 服务三项 SIGSEGV，0080修正后八项通过，清理构建798来源 / 六profile，仅 daemon 二进制改变。该 EOF 缺陷收尾，不重复同组检查。原始client Connect/query与实际server/handler删除、ReadWorker内容读取和replace/zero MergeWorker现已接续八场景，合并整文件读回及写入/fsync失败检查通过；容量/dm-user端点为替身，无生产修改或重编。不重复该层夹具，下一边界为有序COPY/XOR/read-ahead或持久续合并，以及SnapshotManager到实际服务端接续。stream分片及真实init/内核映射仍未解决，不任意加期限。见[handler与合并范围](OTA-OPERATION-COW.md#snapuserd-handler)。见[服务端修正](OTA-OPERATION-COW.md#snapuserd-eof)、[清理边界](OTA-OPERATION-COW.md#snapshot-device-cleanup)与[通信边界](OTA-OPERATION-COW.md#snapuserd-socket)。
3. **文件系统完整生命周期**：0073～0076 的清除失败传播、媒体排除语义、Dalvik / 内部存储与转换分派已维护。实际 ARM64 ext4 / F2FS 工具已接 manager / backend；F2FS 六份文件的独立内容读回及破坏对照已完成。下一边界是完整挂载 / GUI / 加密与 I/O 故障收尾，不重复已通过的命令和内容检查。见 [文件系统说明](FILESYSTEM-TOOLS-EXECUTION.md)。
4. **其他具体缺陷**：触摸自动启动、安全服务、多用户、备份恢复和 USB 集成按下表剩余边界及新证据排序。扩大范围不等于启动全量审计；每批明确实现决定和结束条件。

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

README 保持项目简介、支持状态、快速开始与统一导航。备份数据路径的三份说明合并为一个主题，ADB sideload 并入安装链，引用使用对应小节；删除三份无引用的早期固定路径查看脚本。保留实现细节、复现测试、固定补丁与构建资源清单。文档职责见[维护指南](../MAINTENANCE.md#文档维护)。仓库整理不改变生产功能，不重编镜像。

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
