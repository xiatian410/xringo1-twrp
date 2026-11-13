# 当前交付与验证范围

状态：**适配进行中**。本文只汇总当前交付，不重复历史测试流水账。详细机器索引为 [simulation-report.json](simulation-report.json)，公开结果摘要为 [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。本地 `logs/` 与 `imgs/` 不在公开仓库中。

## 当前候选

| 项目 | 值 |
| --- | --- |
| 文件 | `recovery-dijun-unified-mtp-send-errors.img` |
| SHA-256 | `124ce76d0a7fd51b7b12f63fb974c40fdefc80e226518811a1ec7f7d5eebc755` |
| 生产来源绑定 | 801 份 |
| 固件档案 | 六份 OS2 / OS3 / OS4 profile |
| 构建 | `installclean` 后 `make -j$(nproc)`，30 并发 |
| 发布方式 | 仅本地保存镜像，GitHub 发布维护源码 |

## 后续执行证据

容量刷新新增原 `gui2_loop_tick` / app 主循环接续证据：正常结束、建页前结束与人为提交等待三场景通过。等待期间 worker DONE 不会使阻塞中的 GUI 继续轮询，解除后下一轮更新完成；不证明现场 DRM 长期等待。扫描、提交及设备服务有明确替身，现场根因仍未解决。无生产修改或重编，不重复同类夹具，见[范围](docs/REFRESH-STUCK-INVESTIGATION.md#gui-loop)。

scratch保存后，在目标写入前/一块后/ordered块全写后及header提交两项后退出整个服务，再创建新client/server/handler的四项恢复通过：前三项走真实scratch重建，第四项沿进度2继续，重启后快照读取、最终全文件及进度4均核对。受影响ordered六项回归通过。没有生产修正或重编；进程退出恢复不等于手机断电，见[恢复范围](docs/OTA-OPERATION-COW.md#snapuserd-resume)。

有序COPY/XOR与实际ReadAhead已补六场景，覆盖双块依赖、XOR偏移21、混合操作、scratch区和写入/同步失败；整文件与重新打开COW进度核对通过，共享handler八项回归通过。无生产修改或重编，此检查点未验证进程死亡续合并（后续见上文），多窗口与内核接续仍未验证，见[有序合并范围](docs/OTA-OPERATION-COW.md#snapuserd-ordered)。

实际 client Connect/query、server、SnapshotHandlerManager、ReadWorker 与 replace/zero MergeWorker 已接续八场景。真实COW压缩数据/零块读取、64 KiB合并内容与未改尾部逐字节核对，写入/同步故障均保持失败；容量查询和dm-user端点为明确替身。没有发现新增生产缺陷，不重编0080镜像。该检查点未包含COPY/XOR/RA；后续有序合并见上文，进程退出后的局部续合并见上文，硬件断电、内核映射和完整OTA仍待完成，见[范围](docs/OTA-OPERATION-COW.md#snapuserd-handler)。

## 0083 交付时的定向验证

修正原生负磁盘读取遗漏，以及原生 / 兼容尾批 USB 写入失败误报成功。八项定向检查通过，旧源码六项失败（含一个十秒超时）；正常传输往返与完成队列三项相关回归通过。磁盘取消保留原错误、短写明确返回 EIO；不承诺已送达数据回滚。清理构建仅改变 MTP 库、构建属性及 ramdisk 摘要，801 来源、六份 profile 不变，交付审计 `logs/mtp-send-delivery.json` 通过。只覆盖单批 body 与明确故障边界，不表示完整 USB / Reset 验收，见[发送失败范围](docs/MTP-ADAPTATION.md#send-errors)。

## 0082 交付时的定向验证（历史）

原生 bulk `waitEvents` 在完成队列报错时不再将 `-1` 转成数组循环上限。旧 EIO / EAGAIN 两项由 ASan 复现栈越界，修正后三项通过，含 EINTR 真实重试和内容检查；原生 / 兼容模式传输往返与故障回归通过。实际主机 AIO / 管道 / 普通文件配合单次完成错误注入，不是物理 FunctionFS / UDC 或完整取消复位验收。交付审计 `logs/mtp-aio-error-delivery.json` 通过；清理构建仅 MTP 库、构建属性和 ramdisk 摘要变化，未变证据复用。见[范围](docs/MTP-CONTROL-ADAPTATION.md#bulk-completion-error)。

## 0081 交付时的定向验证（历史）

上传失败且临时文件无法删除时，当前 handle 不再被遗留路径占用。覆盖 / 新建各连续两次失败后可成功上传，旧目标保持、两份遗留内容及用户同前缀文件均核对；116 项对象与 48 项移动 / 复制通过，旧覆盖对照失败、新建对照通过。清理构建相对 0080 仅改变 `libtwrpmtp-ffs.so`、构建属性和 ramdisk 摘要，六份 profile 保留；未变结果按原范围复用。交付审计 `logs/mtp-staging-retry-delivery.json` 通过。不是跨重启清理或 USB / Windows 验收，详见[范围](docs/MTP-ATOMIC-UPLOAD.md#staging-retry)。

## 0080 交付时的定向验证（历史）

实际 ARM64 snapuserd 服务端通过公开 Start / Run 与私有 Unix socket 执行八项检查。旧源码在三种客户端半关闭情形下 SIGSEGV，0080修正后八项通过；第二客户端仍可查询并停止服务。替换的只有 daemon main，没有 snapshot handlers、内核映射或完整 OTA。见[故障与范围](docs/OTA-OPERATION-COW.md#snapuserd-eof)。

最终镜像相比0079仅 snapuserd 二进制、构建属性及文件摘要变化。既有更新器、manager/client socket与设备清理结果按原范围复用，不把独立套件视为完整接续，也不重跑未变功能。

## 本次候选包含的修正

- **0083**：负磁盘读取先检查，原生 / 兼容尾批 USB 写入错误传回调用者，取消不覆盖原错误。
- **0082**：bulk 完成队列报错立即保留 errno 返回，避免负计数导致栈数组越界。
- **0081**：分离当前传输 handle 与遗留临时路径，修正删除失败后无法再次覆盖同对象；保留精确路径隐藏，不按前缀删除文件。
- **0080**：recv EOF 不再依赖 POLLHUP，解析器拒绝空命令，避免半关闭连接使服务端访问空 vector 崩溃。实际 ARM64 server八项 / 旧三项 SIGSEGV；清理构建798来源 / 六profile，交付核对通过。

- **0079**：解除映射结果汇总到控制器与校验器，失败阻止重映射及成功上报；空集合成功，metadata 不可用不调用 snapshot，原哈希错误保留。校验器9 / 控制器8通过，旧2 / 6失败；取消10 / postinstall6必要回归通过。清理构建796来源 / 六profile；仅更新器二进制变化，实际映射及完整安装仍未覆盖。见[范围](docs/OTA-OPERATION-COW.md#snapshot-unmap)。

- **0078**：快照必要清理失败向 CancelUpdate / 原始 ResetUpdate 返回失败，防止取消误成功。实际 ARM64 十场景通过、旧六场景误成功；共享代码收尾十六项 / postinstall 六项回归通过，清理构建794来源 / 六profile。实际映射、快照删除与合并仍未覆盖，不表示完整 OTA。见[范围](docs/OTA-OPERATION-COW.md#snapshot-cancel)。

- **0077**：CLI 输出 FIFO 握手与写入不再阻塞 GUI；读取端缺失时保留请求最多五秒，超时不执行并重建监听；按实际输入长度终止命令，重启监听清除旧请求。12 场景通过、旧七场景失败，清理构建 793 来源 / 六 profile。只有 Recovery 主程序、构建属性与 ramdisk 摘要相对0076改变；GUI库、工具worker、容量计算及profile字节不变。现场刷新根因未证明，见[边界](docs/REFRESH-STUCK-INVESTIGATION.md#cli-fifo)。

- **0076**：格式转换不受 rm-rf 设置覆盖；缺工具拒绝转换而非删除旧文件假成功；按请求别名分派，格式化成功及时更新类型。25 场景通过、旧 10 失败；命令/设备是替身，真实转换接续仍待覆盖。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#文件系统转换分派与状态0076)。

- **0075**：Dalvik 挂载/路径查询/删除失败传播；内部存储只清除媒体根目录内容，保留根 inode/元数据，恢复 MTP 登记后仍保留删除失败状态。16 场景通过、旧 9 失败；普通 user xattr 不是 fscrypt 验收。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#dalvik-与内部存储清除0075)。

- **0074**：保留媒体的数据清除传播类型读取、unlink / rmdir 与目录迭代错误；递归跟踪实际排除内容，只在预期保留时接受目录非空。13 场景通过、旧 3 失败，0073 与备份目录相关方法未变，复用原 11 / 12 项结果。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#保留媒体的数据清除0074)。

- **0073**：目录删除首个失败不再被后续成功覆盖；三个清除入口传播结果到 manager / backend FAILED。真实权限错误等 11 场景通过、旧 5 失败，备份目录管理必要回归 12 项通过。后续 0074 补齐保留媒体递归，其他调用方与完整生命周期仍待维护，见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#目录清除失败传播0073)。

- **0072**：备份、恢复、清除、侧载与 fastbootd 日志页补齐有界读取和页面首帧/删除门控；五入口 30 场景、共享工具页六项通过。backend 执行逻辑未改，不表示完整业务链或现场刷新验收。见[生命周期范围](docs/OPERATION-FEEDBACK-ADAPTATION.md#进度页日志生命周期补齐0072)。

- **0071**：MTP 文件格式在对象信息、属性、路径、枚举与筛选间统一；按常见扩展名分类，重命名刷新属性。对象链路 114 项 / 转移 48 项通过，旧实现四个格式场景失败。只识别文件名，不解析媒体标签或证明 USB 集成。见[格式一致性](docs/MTP-OBJECTS-ADAPTATION.md#文件格式与筛选一致性0071)。

- **0070**：工具进度页复用有界日志窗口，首帧匹配后读取，终态更新先于日志；六场景通过，旧实现六个入口均触发同一无界读取缺陷。修复软件响应路径，现场停留根因尚未证明。见[刷新调查](docs/REFRESH-STUCK-INVESTIGATION.md#工具日志分批渲染0070)。

- **0069**：SnapshotManager 的临时文件同步失败不再继续发布并误报成功；重试 `EINTR`。实际 ARM64 状态文件生命周期 16 场景通过，旧 helper 两项 I/O 错误误报成功、两项缺少实际 EINTR 重试。共享 libsnapshot 使 init / fastbootd / Recovery / OTA 更新器均重新链接；未变的界面与 profile 证据复用。见 [状态发布](docs/OTA-OPERATION-COW.md#快照状态文件同步失败0069)。这不是完整 OTA 或断电验收。

- **0068**：复制日志检查存储挂载、文件复制、内核 / logcat 获取和写入结果；任一已勾选导出失败会标为 FAILED，保留其他成功文件。13 场景通过、旧实现 11 失败，详见 [日志导出](docs/OPERATION-FEEDBACK-ADAPTATION.md#日志导出的失败状态0068)。

- **0067**：备份重命名 / 删除不再解释 shell 文本，校验当前父目录并拒绝覆盖已有目标。12 场景通过，旧版 8 场景失败；共用 worker 的三种刷新页面调度回归通过。详见 [备份会话与目录管理](docs/BACKUP-SESSION-ADAPTATION.md#备份目录重命名与删除0067)。

- **0066**：快照首次映射或重映射失败时立即拒绝最终校验，并尝试释放部分映射，避免读取可用旧文件后误报成功。完整 ARM64 校验器六场景通过，旧实现两处失败；映射接口仍是明确替身，不表示 SnapshotManager 已执行。

- **0065**：最后分区完成失败及分区关闭失败统一返回写入错误；最后一次关闭失败不再被忽略。实际 ARM64 `DeltaPerformer::Write` 八场景通过，旧实现三处失败。已清理构建并核对打包更新器；其他 ramdisk 变化仅构建属性和文件摘要清单。

- **0063**：温度紧接时间 / 录屏标记，限定在左半区，避开中央摄像头；ext 扩容预留长度和容量计算防溢出、下溢及无效尺寸。
- **0064**：A/B 更新器使用有效 Error 对象；同步拒绝立即返回错误，不进入无完成回调的循环。
- 继承此前 XRING O1 加载页、刷入目标、NV 普通界面限制、OTG 发现及安装 / MTP 收尾等修正。

完整范围见 [有限维护交付记录](docs/archive/BOUNDED-MAINTENANCE.md)。0077 重新编译 Recovery 主程序；相对 format-transition 候选只改变主程序、构建属性与 ramdisk 摘要，GUI / MTP / 更新器 / profile 字节不变。

## 本批与继承证据

后续独立F2FS内容读回补齐六个文件（含内联、多节点、嵌套和零数据），副本单字节破坏可检出，读取不改变镜像哈希。仅修正主机Debian读取器的extra_attr偏移；当前cli-fifo候选与793生产来源不变，没有生产修改或构建。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#f2fs-readback)。

| 范围 | 结果 | 限制 |
| --- | --- | --- |
| 格式转换分派 | 25 场景 / 旧 10 失败 | 原 Wipe/helper/manager/backend；命令/卸载/容量/设备/metadata 替身 |
| Dalvik / 内部媒体 | 16 场景 / 旧 9 失败 | 真正文件删除、inode/user xattr；挂载/MTP/展示替身，非 fscrypt 或完整 GUI |
| 保留媒体递归 | 13 场景 / 旧 3 失败 | 原排除匹配与真实权限错误；Wipe 分派 / 挂载 / 设备 / 展示替身，非完整 GUI |
| 目录清除失败 | 11 场景 / 旧 5 失败，备份目录回归 12 项 | 普通文件真实权限错误；挂载 / 设备 / 展示替身，未覆盖保留媒体路径 |
| 五页日志生命周期 | 30 场景 / 旧 30 入口失败，工具页回归 6 项 | 原 poller / 呈现 / 清理语句；非目标 backend 或完整 GUI / DRM |
| MTP 格式 | 对象 114 项 / 转移 48 项；旧格式 4 项失败 | 文件名分类，非媒体解析或 USB / Windows 验收 |
| 工具进度日志 | 6 场景；旧实现 6 个入口失败 | 原 worker、日志轮询及 LVGL；生产端 / flush / 调度替身，非现场根因证明 |
| 日志导出 | 13 场景；修正前 11 失败 | 实际文件 / worker；采集、挂载与展示替身，无断电证明 |
| 备份目录管理 | 12 场景；修正前 8 失败 | 实际 worker / 文件操作，展示与配置替身；无断电或完整恢复 |
| 快照映射错误 | 6 场景；修正前 2 失败 | 完整 ARM64 verifier / ActionProcessor；设备映射为替身 |
| DeltaPerformer 收尾 | 8 场景；修正前 3 失败 | 原 ARM64 Write；已解析 manifest / writer I/O 为替身 |
| 温度布局 | 11 场景；修正前 10 失败 | LVGL 真实执行，字体 / 读数 / flush 有替身 |
| ext 扩容 | 16 场景；修正前 7 失败 | 命令参数边界，不执行真实 resize 工具 |
| OTA 同步拒绝 | 7 场景；修正前 4 失败 | 原解析 / 错误路径；服务与调度替身，无 payload 写入 |
| 刷新页面生命周期 | 3 种调度，含 8 次重入 | worker、PUSH / POP、动作与删除；未复现现场故障 |
| 状态读取 / 修复返回值 | 28 场景 / 146 断言 | 对应软件路径，不能替代实际传感器或挂载 |
| init / profile | 5 份 init、9 组 / 102 次阶段调用 | host verifier 与脚本回放，不是完整系统启动 |
| RTC / 视频 | 相关来源未变，复用既有结果 | 不为刷新日期重跑，不外推硬件和性能 |

格式转换分派为本批修复；Dalvik / 内部媒体、保留媒体递归、目录清除失败、五页日志生命周期、MTP 格式、工具进度日志、日志导出、备份目录、快照映射等行保留此前交付范围，未将旧报告重新绑定为新镜像执行结果。以上不是总功能通过率；历史全量审计仍有证据来源漂移，不能用定向通过代替全量通过。

## 此前新增证据（对应旧候选，范围保留）

当前构建 ARM64 快照库的 COW v3 / LZ4 / 64 KiB 真实文件往返及四类拒绝通过，六份原厂参数一致。使用交付 linker / 共享库；archive 在测试时绑定，未被旧镜像来源清单历史绑定。不是 update_engine / SnapshotManager / 合并或完整 OTA 验收，详见 [范围](docs/OTA-OPERATION-COW.md)。无生产修正或重新构建。

实际 ARM64 `InstallOperationExecutor → SnapshotExtentWriter → COW` 已接续 REPLACE / BZ / XZ，含分散目标与部分写入失败，共八场景。短输入可能返回true但目标不完整，该八场景当时未执行最终哈希；后续十场景已接通原异步校验器，短输入返回错误15，设备映射仍为普通文件替身，不等于OTA成功。见 [操作接续范围](docs/OTA-OPERATION-COW.md)。该证据批次当时没有改变生产镜像。当前新候选继承 0065，并新增 0066；VABC 的后续会话验证见同一主题文档。

同一 payload 测试入口已进一步接到原 PostinstallRunnerAction，五场景确认哈希失败不进入完成阶段、FinishUpdate 失败不切槽、切槽失败返回错误及明确不切槽的状态。完成 / 槽位 / 硬件接口仍为观察替身，实际 postinstall 脚本跳过；无新增生产修正或镜像。详见同一 [OTA 主题](docs/OTA-OPERATION-COW.md)。

两份 OS4 的真实 RAW / BZ / XZ 操作各一个，共六项已执行原 ARM64 操作到 COW / 读回，逐字节匹配独立校验的原分区切片。共用入口原八项回归通过，无生产修正或重编。后续已执行 OS4 旧样本完整原始 payload（7,821,653,872 B），4,903 操作、42 分区最终哈希通过。使用同镜像证书，保留 Recovery 签名编译边界；正式版完整 payload（7,883,589,123 B）亦已执行，4,933 操作与 42 目标哈希通过。设备映射和 Prepare 仍为替身，无实际 SnapshotManager / postinstall 或整包 OTA 验收。无生产修正或新镜像，见同一 OTA 主题。

实际工具证据补充：当前同镜像原 Wipe/helper/manager/changefilesystem/Repair/ExecCmd 已在私有 chroot 接到真实 ARM64 格式化/检查工具，六场景通过，ext4 独立 payload 读回一致，F2FS 填充后结构检查通过；设备解析/卸载/容量/属性与 metadata 是明确替身，父调用者为主机程序。无生产修改或重新构建，见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#实际格式化工具与调用链接续)。

## 用户确认与未完成项

- **OS4 震动已修好，用户确认正常**；退出例行检查。
- backup-manifest 基线设置用户确认正常；结论仅限对应观察。
- 容量刷新日志约 5.15 秒已结束，但现场画面未结束原因未定位；不宣称修复。
- 自动触摸启动、完整 OTA / 快照写入与合并、真实 TEE / CE、完整 USB / MTP、全流程备份恢复等边界仍在 [工作队列](docs/WORK-QUEUE.md) 中。

代理没有执行手机或物理块设备操作。离线工具执行、主机替身、原始 ARM64 代码执行与历史用户设备结果分别记录，不互相替代。

## 本轮实现决定

Recovery metadata 不可用的直接回退执行了六个原 ARM64 控制器场景。调用方先检查 compression 模式，孤立映射失败不足以证明安装失败，因此撤回试验补丁，生产来源恢复为上述 log-export 候选。此处只有新增证据，无生产修复或新交付镜像；详见 [回退判断](docs/OTA-OPERATION-COW.md#recovery-缺失-metadata-时的回退判断)。实际 SnapshotManager 仍未执行，完整目标不据此关闭。

## 收尾失败后的实际重试接续

原始 ARM64 PostinstallRunnerAction 经原控制器调用实际 SnapshotManager，六场景确认同步 / 状态发布失败阻止切槽，重新创建控制器后沿用已有文件重试完成；切槽失败后的 Unverified 状态不会重复发布。详见 [接续范围](docs/OTA-OPERATION-COW.md#实际收尾调用链与失败后重试)。本批无生产修改或新构建，当前 snapshot-sync 候选与 784 来源保持不变；挂载 token、HAL / slot / hardware 仍为边界，真实 payload 到映射 / merge / postinstall 脚本全链仍未完成。

## postinstall 子进程接续

原始 ARM64 PostinstallRunnerAction / Subprocess / 进程回收器接实际无害 ARM64 程序，9 场景覆盖必选 / 可选退出、特殊错误、信号、缺程序、挂载拒绝和取消；验证失败阻止切槽及取消后无未回收子进程。六份原厂 manifest 确认两份 OS4 的 otapreopt 为可选，其余四份无该配置。见 [范围](docs/OTA-OPERATION-COW.md#postinstall-程序退出与取消接续)。无生产修改或新构建；实际挂载、原厂 otapreopt / namespace、payload 和 SnapshotManager 全链仍未完成。

## 原厂 OS4 postinstall 的 Recovery 出口

两份原厂 otapreopt 脚本字节一致，经当前候选的实际 ARM64 shell/getprop 执行，八个场景确认 `dev.bootcomplete` 非 1 时返回 0、没有 ART 调用。实际属性区缺失时原 getprop 返回空值；其他属性输入为显式夹具。无需因缺 ART 就补服务或改脚本。见 [范围](docs/OTA-OPERATION-COW.md#os4-原厂脚本的-recovery-退出条件)。本批无生产修改或构建；真实属性区、挂载、namespace 及原安装器到原厂脚本全链仍未完成。
