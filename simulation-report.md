# 当前交付与验证范围

状态：**适配进行中**。本文只汇总当前交付，不重复历史测试流水账。详细机器索引为 [simulation-report.json](simulation-report.json)，公开结果摘要为 [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。本地 `logs/` 与 `imgs/` 不在公开仓库中。

## 当前候选

| 项目 | 值 |
| --- | --- |
| 文件 | `recovery-dijun-unified-snapshot-map.img` |
| SHA-256 | `54d2210ef4b3213d4703ca2278b5ed49591ab2d61cac314ed0b737814f202a03` |
| 生产来源绑定 | 779 份 |
| 固件档案 | 六份 OS2 / OS3 / OS4 profile |
| 构建 | `installclean` 后 `make -j$(nproc)`，30 并发 |
| 发布方式 | 仅本地保存镜像，GitHub 发布维护源码 |

## 本次候选包含的修正

- **0066**：快照首次映射或重映射失败时立即拒绝最终校验，并尝试释放部分映射，避免读取可用旧文件后误报成功。完整 ARM64 校验器六场景通过，旧实现两处失败；映射接口仍是明确替身，不表示 SnapshotManager 已执行。

- **0065**：最后分区完成失败及分区关闭失败统一返回写入错误；最后一次关闭失败不再被忽略。实际 ARM64 `DeltaPerformer::Write` 八场景通过，旧实现三处失败。已清理构建并核对打包更新器；其他 ramdisk 变化仅构建属性和文件摘要清单。

- **0063**：温度紧接时间 / 录屏标记，限定在左半区，避开中央摄像头；ext 扩容预留长度和容量计算防溢出、下溢及无效尺寸。
- **0064**：A/B 更新器使用有效 Error 对象；同步拒绝立即返回错误，不进入无完成回调的循环。
- 继承此前 XRING O1 加载页、刷入目标、NV 普通界面限制、OTG 发现及安装 / MTP 收尾等修正。

完整范围见 [有限维护交付记录](docs/BOUNDED-MAINTENANCE.md)。原始 `update_engine_sideload` 和 `libgui2` 已重新编译并核对打包内容。

## 本批与继承证据

| 范围 | 结果 | 限制 |
| --- | --- | --- |
| 快照映射错误 | 6 场景；修正前 2 失败 | 完整 ARM64 verifier / ActionProcessor；设备映射为替身 |
| DeltaPerformer 收尾 | 8 场景；修正前 3 失败 | 原 ARM64 Write；已解析 manifest / writer I/O 为替身 |
| 温度布局 | 11 场景；修正前 10 失败 | LVGL 真实执行，字体 / 读数 / flush 有替身 |
| ext 扩容 | 16 场景；修正前 7 失败 | 命令参数边界，不执行真实 resize 工具 |
| OTA 同步拒绝 | 7 场景；修正前 4 失败 | 原解析 / 错误路径；服务与调度替身，无 payload 写入 |
| 刷新页面生命周期 | 3 种调度，含 8 次重入 | worker、PUSH / POP、动作与删除；未复现现场故障 |
| 状态读取 / 修复返回值 | 28 场景 / 146 断言 | 对应软件路径，不能替代实际传感器或挂载 |
| init / profile | 5 份 init、9 组 / 102 次阶段调用 | host verifier 与脚本回放，不是完整系统启动 |
| RTC / 视频 | 相关来源未变，复用既有结果 | 不为刷新日期重跑，不外推硬件和性能 |

快照映射错误行属于本次候选；其他行保留此前交付范围，未将旧报告重新绑定为新镜像执行结果。以上不是总功能通过率；历史全量审计仍有证据来源漂移，不能用定向通过代替全量通过。

## 此前新增证据（对应旧候选，范围保留）

当前构建 ARM64 快照库的 COW v3 / LZ4 / 64 KiB 真实文件往返及四类拒绝通过，六份原厂参数一致。使用交付 linker / 共享库；archive 在测试时绑定，未被旧镜像来源清单历史绑定。不是 update_engine / SnapshotManager / 合并或完整 OTA 验收，详见 [范围](docs/OTA-OPERATION-COW.md)。无生产修正或重新构建。

实际 ARM64 `InstallOperationExecutor → SnapshotExtentWriter → COW` 已接续 REPLACE / BZ / XZ，含分散目标与部分写入失败，共八场景。短输入可能返回true但目标不完整，该八场景当时未执行最终哈希；后续十场景已接通原异步校验器，短输入返回错误15，设备映射仍为普通文件替身，不等于OTA成功。见 [操作接续范围](docs/OTA-OPERATION-COW.md)。该证据批次当时没有改变生产镜像。当前新候选继承 0065，并新增 0066；VABC 的后续会话验证见同一主题文档。

同一 payload 测试入口已进一步接到原 PostinstallRunnerAction，五场景确认哈希失败不进入完成阶段、FinishUpdate 失败不切槽、切槽失败返回错误及明确不切槽的状态。完成 / 槽位 / 硬件接口仍为观察替身，实际 postinstall 脚本跳过；无新增生产修正或镜像。详见同一 [OTA 主题](docs/OTA-OPERATION-COW.md)。

两份 OS4 的真实 RAW / BZ / XZ 操作各一个，共六项已执行原 ARM64 操作到 COW / 读回，逐字节匹配独立校验的原分区切片。共用入口原八项回归通过，无生产修正或重编。后续已执行 OS4 旧样本完整原始 payload（7,821,653,872 B），4,903 操作、42 分区最终哈希通过。使用同镜像证书，保留 Recovery 签名编译边界；正式版完整 payload（7,883,589,123 B）亦已执行，4,933 操作与 42 目标哈希通过。设备映射和 Prepare 仍为替身，无实际 SnapshotManager / postinstall 或整包 OTA 验收。无生产修正或新镜像，见同一 OTA 主题。

## 用户确认与未完成项

- **OS4 震动已修好，用户确认正常**；退出例行检查。
- backup-manifest 基线设置用户确认正常；结论仅限对应观察。
- 容量刷新日志约 5.15 秒已结束，但现场画面未结束原因未定位；不宣称修复。
- 自动触摸启动、完整 OTA / 快照写入与合并、真实 TEE / CE、完整 USB / MTP、全流程备份恢复等边界仍在 [工作队列](docs/WORK-QUEUE.md) 中。

代理没有执行手机或物理块设备操作。离线工具执行、主机替身、原始 ARM64 代码执行与历史用户设备结果分别记录，不互相替代。
