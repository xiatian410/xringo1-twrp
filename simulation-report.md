# 当前交付与验证范围

状态：**适配进行中**。本文只汇总当前交付，不重复历史测试流水账。详细机器索引为 [simulation-report.json](simulation-report.json)，公开结果摘要为 [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。本地 `logs/` 与 `imgs/` 不在公开仓库中。

## 当前候选

| 项目 | 值 |
| --- | --- |
| 文件 | `recovery-dijun-unified-ordinary-reports.img` |
| SHA-256 | `aee7856e90ba4f5861bdc918d4da0b585b7de4fd337a64138204c9f526d3b300` |
| 生产来源绑定 | 809 份 |
| 固件档案 | 六份 OS2 / OS3 / OS4 profile |
| 构建 | `installclean` 后 `make -j$(nproc)`，30 并发 |
| 发布方式 | 仅本地保存镜像，GitHub 发布维护源码 |

## 当前候选：OS4 普通触摸报告启动策略

当前候选在 Synaptics 模块进入 live、Xiaomi input 注册后等待2秒，再请求 `enable_touch_raw=0` 并核对软件缓存读回。9项私有文件策略用例和镜像打包审计通过；候选绑定809项生产来源与六个 profile。等待2秒是有限启动策略，不代表目标设备时序已测量，也不代表控制器确认切换。

用户此前手动写 raw0 后观察到215条 Linux input 事件。当前自动启动候选没有新的硬件运行证据，不能据缓存读回或策略测试宣称触摸已修复。OS4震动由用户确认正常，退出例行检查；设置在 backup-manifest 基线正常，也不重复诊断。

## 页面生命周期补充：镜像刷入目标

补齐刷入目标测试的交接范围：既有25项覆盖真实 `page_router/page_host` 目标点击、确认页 `REPLACE`、返回安装入口 `POP` 和再次 `PUSH`。新增确认链25项中，20项通过真实 LVGL 滑块手势调用生产 `install_confirmed`，逐项核对 `start_image` 收到的镜像路径、所选目标与双槽标志，并路由到进度页；另5项拖出取消。没有发现生产缺陷，因此没有源码补丁或新镜像。安装 manager 和块设备写入继续由独立40项 worker 链覆盖，但本次没有重复运行该链。详细边界见[分区操作](docs/PARTITION-ACTIONS.md)。

## 本批证据：分区工具页面与后台接续

分区选项、确认 / 文件系统选择、原工具 worker、进度页与返回详情在同次主机回放中接通，十项通过。涵盖修复 / 扩容 / 格式转换成功失败、未选择、启动被拒后重试、确认前返回与重复进入。manager、详情和显示提交有明确替身，未执行真实分区操作或完整 GUI 主循环；没有发现生产缺陷，没有新补丁或构建。镜像与 809 份生产来源不变，范围见[分区工具页面接续](docs/PARTITION-ACTIONS.md#tool-page-worker-lifecycle)。

## 已有证据：ext4 标签初始化

扩展既有工具接续，实际执行当前镜像 ARM64 e2fsdroid：`/data` 与 System 根标签经独立 debugfs 读回确认，Android 分离规则选择及缺失 / 无效规则的失败返回五项通过；共用测试工具的原六项场景回归通过。首次夹具漏复制镜像已有的分离规则，失败保留，没有据此修改生产代码。镜像及 809 来源不变，无新增构建；真实挂载 / 加密 / 完整 GUI 生命周期仍未完成。范围与结果见[文件系统标签初始化](docs/FILESYSTEM-TOOLS-EXECUTION.md#postformat-selinux)。

## 历史交付：0090 COW 初始化失败不再崩溃

真实 ARM64 快照初始化测试发现：COW 头部 `fsync` 返回 I/O 错误后，`CreateCowWriter` 返回空指针，旧 SnapshotManager 仍调用 `Finalize` 并触发 SIGSEGV。0090 补齐空判断，返回原有错误路径并执行清理。新候选已按要求清理构建，809 来源与六 profile 封装核对通过。

正常、路径查询失败、头部同步失败三项定向检查通过；使用同一夹具和镜像库、替换为旧 SnapshotManager 的负向检查仅同步失败项崩溃。正常项真实初始化并解析十份空 COW，发布目标 LP，重建 manager 后持久化 Unverified 状态；两种失败均清除临时映射 / 状态、保持 Initiated，不误报完成。内核映射由独立稀疏普通文件代替，源 LP 为合成 32 GiB，HAL / kernel / ImageManager 为明确边界；测试模式关闭 scratch 和 daemon 启动。**没有重跑整包，不代表真实映射 / 挂载 / 槽位 / 重启合并验收。** 见[初始化与故障范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-initialization)，本地交付核对 `logs/snapshot-cow-init-delivery.json`。

## 整包接入真实分配：模型内成功，设备边界仍未验收

修正测试模型在Cleanup阶段释放controller后，原始OS4.0.4整包单次运行完成真实控制器/十份COW分配、全部4933操作、payload哈希、42最终分区哈希、原厂Recovery脚本、真实Unverified发布、模型槽位与卸载清理；引擎退出0/wait0、父安装器INSTALL_SUCCESS=0。24项断言通过，约881秒，详见[成功运行范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success)。

这是模型生命周期修正和接续证据，无生产修改或新镜像。源LP/DM视图/readonly/挂载/HAL/槽位/proc等仍为明确模型，scratch/daemon关闭；未证明实机启动合并。已完成的整包不再例行重复。

## 历史：整包接入真实分配后的模型退出失败

同次原始 4.0.4 完整 ZIP 运行已移除预置分配状态与独立 COW 创建，执行真实控制器 PreparePartitionsForUpdate / SnapshotManager 初始化十份 COW，再由原 controller writer 执行全部4933操作、payload哈希与42最终分区哈希；原厂脚本 Recovery 分支、真实完成状态及模型槽位接续。约876秒后，在成功回调 / 完成标记后进程SIGSEGV，实际退出1，父安装器INSTALL_ERROR，**本次安装为FAILED**。

精确保存的同一适配器另做两项分配后退出探针：进程静态 controller 在main返回后复现SIGSEGV，main结束前释放则退出0，定位为模型生命周期问题，尚无生产缺陷证据。后续已修正模型所有权并取得上文成功结果；固定路径 runner 当时覆盖了旧失败原始报告，只保留旧摘要、适配器与文字结论，不能声称旧原始报告完整留存。此后 runner 已拒绝覆盖既有运行输出。真实内核映射 / 挂载 / HAL / 槽位 / scratch / daemon / 启动合并仍有替身，见[历史失败与保存限制](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-failure)。

## 分配到 payload 片段的交接证据

同一执行中，真实 SnapshotManager 创建的 COW 已交给原 `DynamicPartitionControlAndroid::OpenCowWriter → OpenSnapshotWriter → VABCPartitionWriter`，执行原始 4.0.4 `mi_ext` 前两条操作（REPLACE_XZ / REPLACE），4 MiB 读回与独立原厂分区切片一致。重新创建 manager / controller / writer 后从 label1 续写通过；损坏头部时 Init 拒绝，显式卸载映射后保持 Initiated，不发布完成。共三项通过，见[交接边界](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-payload-handoff)。

这是新接续证据，无生产修改或新构建。DM 基础分区 / COW 由持久普通文件视图替代，基础映射和 procfs realpath 有明确边界，测试模式关闭 scratch / daemon。只执行两条操作，没有整分区 / 全量 payload / 完成状态，不把它与历史整包运行合并为完整 OTA 验收；镜像仍为上表 0090 候选。

## 历史阶段证据

以下条目保留各轮执行时的镜像与边界；“无新构建”仅指该轮，当前候选以上表为准。

原控制器分配失败到回退接续新增五项：真实 `PreparePartitionsForUpdate → SnapshotManager → CancelUpdate → 直接 LP 准备` 在原始 manifest / 普通文件布局中执行；映射失败或空间不足会在取消成功后发布目标 LP，取消 fsync 失败则停止，卸载 / 保存失败也返回 false。两项成功准备的源目标范围重叠，不能据源 metadata 保留宣称中断可回滚。共享布局夹具相关七项回归通过；无生产修改或新构建，见[回退与取消门控](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-preparation)。

分配入口新增有限证据：原始 4.0.4 manifest 接到真实 ARM64 `BeginUpdate / CreateUpdateSnapshots`、LP 更新器与 COW 规划器；合成普通文件 LP 中核对十个分区的快照尺寸 / COW 估算、拒绝映射后的清理，及空间不足、缺少内核能力 / 估算、版本越界、overlayfs、错误状态，共七项通过。检查失败不发布目标 LP、metadata 字节不变、临时状态清理。布局与空间为明确合成输入，不能用于判断设备实际容量；映射 / COW 初始化和控制器回退仍未贯通。无生产修正或新镜像，见[分配入口范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-allocation)。

最新原始 4.0.4 整包模拟在模型内成功：一次运行完成整包验签、真实 ARM64 引擎 4933 操作 / payload 哈希 / 42 分区哈希，接到精确原厂 postinstall 的 Recovery 保护分支及真实 SnapshotManager 的 Unverified 状态发布，再记录模型目标槽。引擎退出 0，原父安装器返回 INSTALL_SUCCESS=0，21 项断言通过，约 861 秒。**结果为 MODEL_SUCCESS，完整设备 OTA 仍未验收**：块只读、挂载、快照分配、HAL / 槽位仍有模型，没有真实启动或合并。无生产修改或新构建；保留此前 FAILED63 记录。见[当前模型范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-model-finish)。以下为各阶段历史证据，不能把阶段边界当作最新队列。

原 ZIP 父进程到真实 ARM64 引擎已在一次运行中接续：当前固定信任库验证原始 4.0.4 整包签名后，原 A/B 命令 / fork / pipe 经显式 QEMU 桥接启动原主程序与下载队列，完成 4933 操作及 42 最终哈希。引擎在普通文件块只读设置处返回 63，父进程消费真实两阶段进度，观察 wait status16128，正确返回 INSTALL_ERROR=1 并清理 / 回收；没有误报成功。**安装仍为 FAILED**，postinstall 挂载 / 程序、SnapshotManager、槽位和合并未执行。父为主机编译，HAL / 文件映射等替身保留；无生产修正或新镜像。见[一次父子接续范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-engine-joined)。

原 ARM64 `update_engine_sideload` 主程序 / `ApplyPayload` / `DownloadAction` / `FileFetcher` 已在当前镜像 linker / libc 环境处理原始 OS4.0.4 ZIP，完成 4933 操作与 payload 哈希，并通过 42 个最终分区哈希校验。其后 postinstall 对普通文件设置块只读失败，**安装返回 63，不是安装成功**。10 个真实 COW 视图由文件映射模型物化；BootControl / Hardware / 清理动作 / proc 状态为明确夹具，没有 SnapshotManager 或实际挂载。ZIP 安装器父进程仍未与此运行接成同一链。本批是接续证据，无生产修改或重编；首版夹具判据错误的 FAIL 原样保留，复核报告只证明实际停止位置与哈希，不覆盖安装失败。见[引擎结果](docs/INSTALL-CHAIN-VALIDATION.md#stock-engine-entry)。

原始 `OS4.0.4.0.XODCNXM` 完整 ZIP 在旧 media-recreate 候选开启验证时被拒绝。本批生产修正为补齐固定小米 OTA 公钥：从六份哈希固定的原厂 recovery 提取，六份证书完全一致；保留原有三张证书，不修改运行时验证逻辑。清理构建后，原始完整 ZIP 开启签名验证通过，移除仅该公钥后拒绝，设备不匹配也拒绝；五项入口检查及普通 ZIP 36 项回归通过。808 来源、六 profile 和封装核对通过，与旧镜像相比仅构建属性、ramdisk 摘要与 otacerts.zip 改变。生产二进制未变。交付核对见本地 `logs/stock-ota-trust-delivery.json`。

这修正了原厂签名支持，**不表示完整卡刷通过**：入口子进程只核对原包 offset / headers / CrAU，不安装 payload。历史完整 payload 执行属于较早 snapshot-map 镜像，不能与当前入口测试拼成完整 OTA 验收，见[范围与结果](docs/INSTALL-CHAIN-VALIDATION.md#stock-os4-zip)。

容量刷新新增原 `gui2_loop_tick` / app 主循环接续证据：正常结束、建页前结束与人为提交等待三场景通过。等待期间 worker DONE 不会使阻塞中的 GUI 继续轮询，解除后下一轮更新完成；不证明现场 DRM 长期等待。扫描、提交及设备服务有明确替身，现场根因仍未解决。无生产修改或重编，不重复同类夹具，见[范围](docs/REFRESH-STUCK-INVESTIGATION.md#gui-loop)。

scratch保存后，在目标写入前/一块后/ordered块全写后及header提交两项后退出整个服务，再创建新client/server/handler的四项恢复通过：前三项走真实scratch重建，第四项沿进度2继续，重启后快照读取、最终全文件及进度4均核对。受影响ordered六项回归通过。没有生产修正或重编；进程退出恢复不等于手机断电，见[恢复范围](docs/OTA-OPERATION-COW.md#snapuserd-resume)。

有序COPY/XOR与实际ReadAhead已补六场景，覆盖双块依赖、XOR偏移21、混合操作、scratch区和写入/同步失败；整文件与重新打开COW进度核对通过，共享handler八项回归通过。无生产修改或重编，此检查点未验证进程死亡续合并（后续见上文），多窗口与内核接续仍未验证，见[有序合并范围](docs/OTA-OPERATION-COW.md#snapuserd-ordered)。

实际 client Connect/query、server、SnapshotHandlerManager、ReadWorker 与 replace/zero MergeWorker 已接续八场景。真实COW压缩数据/零块读取、64 KiB合并内容与未改尾部逐字节核对，写入/同步故障均保持失败；容量查询和dm-user端点为明确替身。没有发现新增生产缺陷，不重编0080镜像。该检查点未包含COPY/XOR/RA；后续有序合并见上文，进程退出后的局部续合并见上文，硬件断电、内核映射和完整OTA仍待完成，见[范围](docs/OTA-OPERATION-COW.md#snapuserd-handler)。

## 0089 交付时的定向验证

启动时的非 FBE 媒体目录恢复不再忽略目录查询 / 创建失败，media 根已存在时也补查用户目录；拒绝普通文件及符号链接，目录就绪后只恢复缺失绑定，不卸载整个 data 分区。FBE 跳过及缓存元数据 best-effort 策略保留，元数据失败记录日志。13 个原方法私有 chroot 场景通过，旧实现同组 10 项失败；16 项 manager 清除回归通过。真实普通目录 / uid65534 权限失败配合挂载、bind、元数据和呈现替身，不代表完整启动 / GUI / fscrypt 或设备验证。807 来源清理构建、六 profile 不变，`logs/media-recreate-delivery.json` 核对通过。见[启动媒体目录范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#media-recreation)。

## 0088 交付时的定向验证（历史）

Android Secure 目录重建改为返回结果，七种格式选择与 rm-rf 将创建 / 挂载 / bind 失败传回 manager/backend。目录在父分区挂载后创建，拒绝普通文件及符号链接，已有绑定不重复叠加；原调用不再创建后随意卸载父存储。37 项原 helper/manager/backend 场景通过，旧实现 34 项失败；25 项格式转换、11 项清除错误传播、六项同镜像 ARM64 工具回归通过。实际目录操作只涉及临时普通文件，挂载 / bind / 设备 / 命令有明确替身，不是物理设备或完整 GUI 验收。806 来源清理构建及六 profile 核对通过，证据 `logs/andsec-recreate-delivery.json`。见[目录重建范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#andsec-recreation)。

## 0087 交付时的定向验证（历史）

ext 格式化成功后立即记录新文件系统类型，避免后续临时挂载沿用旧类型；persist 后处理明确检查挂载、目录删除及卸载结果，仍挂载时拒绝执行离线 e2fsdroid。清理失败仍尝试卸载，失败不能伪装为格式化回滚。18 项原 helper / manager / backend 定向场景通过，旧实现 15 项失败；25 项格式转换及同镜像 ARM64 格式化 / 修复六项回归通过。挂载、设备、SELinux 与删除为明确替身，工具仅操作普通临时文件，不是设备 persist / 实际挂载或完整 GUI 验收。清理构建 805 来源、六 profile 不变，交付核对 `logs/format-persist-delivery.json` 通过。见[后处理范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#persist-postformat)。

## 0086 交付时的定向验证（历史）

六个离线格式化 helper 补齐卸载后仍挂载拒绝，避免保留 System 的成功返回导致 mkfs 误执行。十五个选择 / 挂载场景及可选 USE_EXT4 保留挂载分支通过，旧七个格式选择加内建分支一个场景失败；既有二十五项格式转换、同镜像 ARM64 格式化修复六项、原 Unmount / 修复九项回归通过。同格式 rm-rf 保持原分派。挂载观测与命令为明确替身，非实机或完整生命周期验收。804 来源清理构建、六份 profile 不变，仅 Recovery 主程序、构建属性和摘要变化，`logs/format-mounted-delivery.json` 审计通过。见[格式化前置条件](docs/FILESYSTEM-TOOLS-EXECUTION.md#format-mounted-guards)。

## 0085 交付时的定向验证（历史）

离线修复在 Unmount 成功请求后确认目标确实未挂载，拒绝保留 System 挂载时的 fsck 和 Resize 前置修复，不强制取消用户设置。九个挂载路径场景通过，旧两项误执行；146 返回码断言、同镜像 ARM64 修复七项和格式化 / 修复六项回归通过。挂载与设备是明确替身，工具仅运行于私有普通文件；并非实机 / 完整 GUI 验收。803 来源清理构建、六份 profile 不变，仅 Recovery 主程序、构建属性和摘要变化，`logs/repair-mounted-delivery.json` 审计通过。见[前置条件与限制](docs/FILESYSTEM-TOOLS-EXECUTION.md#repair-mounted-guard)。

## 0084 交付时的定向验证（历史）

兼容发送在前一批 USB 已失败、下一批排队磁盘读取再失败时保留先前 USB 错误；等待磁盘收尾的顺序不变。原生 / 兼容六个多批场景通过（含 7 MiB + 37 字节内容往返），旧兼容双故障一个场景失败，单批错误八项回归通过。802 来源清理构建，六份 profile 字节不变，仅 MTP 库、构建属性和摘要改变，审计 `logs/mtp-pipeline-delivery.json` 通过。指定重叠调度不证明完整 USB / Reset 取消，见[多批范围](docs/MTP-ADAPTATION.md#pipeline-first-error)。

## 0083 交付时的定向验证（历史）

修正原生负磁盘读取遗漏，以及原生 / 兼容尾批 USB 写入失败误报成功。八项定向检查通过，旧源码六项失败（含一个十秒超时）；正常传输往返与完成队列三项相关回归通过。磁盘取消保留原错误、短写明确返回 EIO；不承诺已送达数据回滚。清理构建仅改变 MTP 库、构建属性及 ramdisk 摘要，801 来源、六份 profile 不变，交付审计 `logs/mtp-send-delivery.json` 通过。只覆盖单批 body 与明确故障边界，不表示完整 USB / Reset 验收，见[发送失败范围](docs/MTP-ADAPTATION.md#send-errors)。

## 0082 交付时的定向验证（历史）

原生 bulk `waitEvents` 在完成队列报错时不再将 `-1` 转成数组循环上限。旧 EIO / EAGAIN 两项由 ASan 复现栈越界，修正后三项通过，含 EINTR 真实重试和内容检查；原生 / 兼容模式传输往返与故障回归通过。实际主机 AIO / 管道 / 普通文件配合单次完成错误注入，不是物理 FunctionFS / UDC 或完整取消复位验收。交付审计 `logs/mtp-aio-error-delivery.json` 通过；清理构建仅 MTP 库、构建属性和 ramdisk 摘要变化，未变证据复用。见[范围](docs/MTP-CONTROL-ADAPTATION.md#bulk-completion-error)。

## 0081 交付时的定向验证（历史）

上传失败且临时文件无法删除时，当前 handle 不再被遗留路径占用。覆盖 / 新建各连续两次失败后可成功上传，旧目标保持、两份遗留内容及用户同前缀文件均核对；116 项对象与 48 项移动 / 复制通过，旧覆盖对照失败、新建对照通过。清理构建相对 0080 仅改变 `libtwrpmtp-ffs.so`、构建属性和 ramdisk 摘要，六份 profile 保留；未变结果按原范围复用。交付审计 `logs/mtp-staging-retry-delivery.json` 通过。不是跨重启清理或 USB / Windows 验收，详见[范围](docs/MTP-ATOMIC-UPLOAD.md#staging-retry)。

## 0080 交付时的定向验证（历史）

实际 ARM64 snapuserd 服务端通过公开 Start / Run 与私有 Unix socket 执行八项检查。旧源码在三种客户端半关闭情形下 SIGSEGV，0080修正后八项通过；第二客户端仍可查询并停止服务。替换的只有 daemon main，没有 snapshot handlers、内核映射或完整 OTA。见[故障与范围](docs/OTA-OPERATION-COW.md#snapuserd-eof)。

最终镜像相比0079仅 snapuserd 二进制、构建属性及文件摘要变化。既有更新器、manager/client socket与设备清理结果按原范围复用，不把独立套件视为完整接续，也不重跑未变功能。

## 本次候选包含的修正

- **0089**：非 FBE 启动媒体目录创建失败立即停止，根存在时也恢复缺失用户目录，仅恢复缺失 bind，不卸载整个 data。
- **0088**：Android Secure 目录重建返回失败，格式化 / rm-rf 不再忽略创建和绑定错误，已存在绑定不叠加。
- **0087**：ext 格式化成功立即保留真实新类型；persist 临时挂载 / 删除 / 卸载失败传回调用者，仍挂载时不运行 e2fsdroid。
- **0086**：离线格式化 helpers 拒绝卸载请求后仍保持挂载的目标，同格式 rm-rf 分派保留。
- **0085**：离线 Repair 确认卸载后的实际状态，阻止保留 System 挂载时继续运行 fsck / Resize。
- **0084**：兼容多批发送先等待读取收尾，再返回先前 USB 错误，避免后续磁盘错误覆盖。
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
