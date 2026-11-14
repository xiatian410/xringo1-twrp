# 分区界面修正：镜像目标与 NV 操作

<a id="ors-command-results"></a>
## ORS脚本操作失败传播（0128）

原ORS解释器忽略了清除Cache/System/Dalvik、恢复出厂、格式化Data、挂载/卸载及`cmd`的失败结果。因`ret_val`保持0，失败后会继续执行下一条脚本；由启动action执行时，还可能据此进入自动重启。

[0128补丁](../dtsrc/O1_asic_dual/patches/0128-ors-command-error-propagation.patch)将上述分区操作的bool语义返回值转换为ORS的0成功/1失败，将`ExecCmd`非0返回转为失败，缺少参数的`cmd`也失败。失败后复用原解析循环停止；System清除失败不再进入后续详情刷新。成功路径和缺省命令别名保留。本补丁不更改NV界面策略或底层分区权限，也不回滚已经完成的操作。

新增定向检查执行完整原`run_script_file`与`Run_OpenRecoveryScript_Action`，用私有脚本文件验证58个成功/失败与直接/启动入口组合。每条被测命令后放置`set sentinel reached`，断言失败不执行后续命令、不进入自动重启，并返回1；成功仍执行后续命令并保留启动action的自动重启路径。当前全部通过，相同夹具旧版30项失败，含`tail=1 reboots=1`的实际替身调用记录。

分区操作、shell执行、DataManager、消息、sleep及最终reboot是显式替身；没有执行真实清除/格式化/挂载、Android shell或重启。已存在的底层文件系统工具证据沿用，不将此次结果称为完整GUI/FIFO状态、ORS准入或完整OTA验收。原`done_ors`表示解析结束，失败结果由返回码及启动页面状态区分，本批没有增加新的CLI退出码协议。

```bash
python3 tests/ors_results_test.py --report logs/ors-results-current.json
python3 scripts/audit_ors_results.py
```

本地报告为`logs/ors-results-current.json`、`logs/ors-results-old.json`及`logs/ors-results-delivery-audit.json`。当前镜像见[交付报告](../simulation-report.md)。以下保留此前分区界面维护记录。

用户报告确认刷入页“目标分区点不动”，并发现高级清除仍有 NV。此次检查发现两个具体缺陷：原厂文件系统 fstab 不含 raw 镜像目标，候选镜像也未带 `twrp.flags`，因而没有 Boot 等可选项；先前 0054 只限制普通挂载，没有覆盖清除与分区工具。此前检查范围不足。

维护的 `profiles/common/root/system/etc/twrp.flags` 现补入 Boot、Init Boot、Vendor Boot、Recovery、DTBO，交由核心检查分区是否存在及选择当前槽位。六份 OTA 的分区清单均含这五项；不写死 `_a`/`_b`。选择目标、滑动确认、真正写入仍是不同步骤。普通 `.img` 的目标选择应由这五种已存在分区提供，标题本身不承担选择功能。

补丁 0060 与配置共同覆盖以下普通 GUI 入口：

| 入口 | NV 行为 | 正常目标 |
|---|---|---|
| 挂载/卸载 | 沿用 0054：隐藏并拒绝直接或解析别名请求 | 保留 |
| 高级清除 | 隐藏；提交和执行前检查全部列表，含 NV 则在第一次清除前拒绝 | 保留 Data/Cache 等 |
| 修复/调整大小/更改文件系统 | 不提供详情；启动和执行前拒绝 | 保留 |
| 镜像刷入 | 不列出；启动和执行前拒绝，空目标/分号多目标亦拒绝 | 补齐五个 raw 目标 |

NV 集合为 nvram、proinfo、nvdata、nvcfg、protect_f、protect_s，含 `/mnt/vendor/` 对应路径、规范化路径、子路径和解析到 NV 的别名。前缀相似的普通路径不误拦截。原厂 fstab 不删除，内部服务仍可访问；备份/恢复和特权终端不受此普通 GUI 策略限制。persist、metadata 不按 NV 集合隐藏。FactoryReset 仍按核心 `wipe_during_factory_reset_` 标记选择目标，未给 NV 新增该标记。

离线检查执行生产方法：26 个路径/批次场景覆盖列表、提交、执行、别名、混合清除预检和分号注入；旧实现同组 19 个失败，修正后通过。真实 LVGL 确认页与原回调覆盖五目标各 label/detail/arrow/blank/drag-out，共 25 场景；路由执行目标点击后的 REPLACE、返回安装入口的 POP、再次 PUSH。确认接合回归让五目标各四种有效点击位置完成真实滑块拖动，断言 `start_image` 收到所选镜像路径、目标挂载点和双槽标志，并进入 INSTALL_PROGRESS；另五种拖出手势取消，共 25 项通过。之后将同一套点击/确认测试绑定当前候选镜像中提取的 `twrp.flags`，再次25项通过，证实这份交付镜像确实包含五个目标。安装源和 manager 仍为观察替身，未执行分区写入；原镜像写入链 40 场景核对私有文件内容与双槽顺序，修复链 7 场景调用镜像 ARM64 e2fsck，挂载策略 26 场景回归通过。上述离线证据不代表实机触摸或完整刷写已验收。

最终候选：`recovery-dijun-unified-partition-actions.img`，SHA256 `f9a11c04da1669ef601ca52ee6c38a99f32011aedcab06a5005af4f74f386db6`。最终 `installclean` 后 `make -j$(nproc)` 以 30 并发构建；769 来源绑定、六 profile 封装和实际镜像 flags 字节核对。初次编译发现新增自由函数访问私有字段，已改用公开 `GetMountPoint()`，修正后重新清理构建。未操作手机或物理块设备。

本地证据：`logs/partition-actions-delivery.json`、`nv-partition-actions.json`、`install-target-lifecycle.json`、`install-target-confirmation-chain.json`、`install-target-current-image.json`、`partition-actions-image-chain.json`、`partition-actions-repair-chain.json`、`partition-actions-mount.json`。公开仓库仅发布源码、配置、补丁、测试及摘要，不上传镜像、编译产物或原始日志。

<a id="tool-page-worker-lifecycle"></a>
## 分区工具页面与后台接续

`tests/partition_tool_pages_test.py` 补齐此前分开验证的页面与 worker 交接：原分区选项 builder / 点击回调 → 确认或选择文件系统 → 原工具后台线程 → 原进度页状态更新 → 返回分区详情。真实 LVGL 指针点击与滑块输入、page_host / scaffold、PUSH / POP、操作锁、后台 start / run / status / acknowledge 均参与执行；路由器由夹具接到这些原始页面，返回逻辑只提取 PARTITION_OPTIONS、CHANGE_FS、TOOL_CONFIRM、TOOL_PROGRESS 四个相关分支。

十个场景通过：修复、扩容、格式转换各自成功与失败，格式未选择、启动被拒后重试、确认前返回，以及格式页完成后再次进入。检查目标 / 格式传递、运行时拒绝返回与第二任务、DONE / FAILED 文案和按钮、返回后清空旧 view 并重新取详情。格式化失败的 manager 替身保留已改变的文件系统类型，用于确认页面不会显示虚假的回滚状态；这不是实际格式化证据。

本地报告 `logs/partition-tool-pages.json` 保存输出、编译命令、源码及 LVGL 依赖指纹。首次编译的定义提取 / include 问题，以及第二次运行中重复进入时错误要求累计调用数为零的问题，均属测试夹具；修正后十项通过，未发现需要修改的生产缺陷。只新增接续证据，没有生产补丁或新镜像。

**范围限制：** PartitionManager 操作与详情提供者、设置、字体、console 读取和显示提交为明确替身。没有运行 mkfs / fsck、完整 GUI 主循环、内核挂载或 fscrypt，不将此测试与独立的[ARM64 工具证据](FILESYSTEM-TOOLS-EXECUTION.md)拼称一次完整文件系统生命周期。相关源码与输入未变时复用本结果，不追加等价回放。

## 嵌套分区操作路径

以下保留 0029 的核心路径修正记录。它与后续 GUI 的 NV 操作限制分属不同层次，不能据核心能够查找分区推断普通界面允许清除 NV。

2026-11-12。设置保存的0028修正使`/mnt/vendor/persist/TWRP`能找到persist，但清除、转换文件系统、修复、调整大小四个入口仍使用GetRootPath。dijun fstab登记`/mnt/vendor/protect_f`、protect_s、nvdata、nvcfg、persist，旧入口却只查`/mnt`，因此无法选择这些真实挂载点。转换/修复/调整大小还缺少`/system`→`/system_root`映射。

维护补丁[0029-nested-partition-operations.patch](../dtsrc/O1_asic_dual/patches/0029-nested-partition-operations.patch)复用真实FindPartitionByPath选出的owner，按owner挂载点执行，并在操作全程持有现有递归操作锁。保留原始Wipe/Repair/Resize能力检查和确认入口；没有添加分区、改变可清除权限、改写fstab或绕过解密失败保护。路径包含普通子目录时仍归属其分区，不能将WipeByPath当成文件删除接口。

同时修正两个错误返回：子分区失败不再被忽略；不存在独立cache时，`/data/cache`清理返回值不再被丢弃。后者只传播WipeDataCache的现有结果；该底层函数未完整检查目录删除错误，本轮不能据此承诺所有删除故障均能传播。多分区操作不具备回滚，某项失败时此前成功项仍可能已完成。

### 验证

[检查程序](../tests/partition_operation_path_test.py)提取真实lookup、两种WipeByPath、RepairByPath和ResizeByPath方法，用私有分区对象记录调用。46断言通过；[旧源码同组](../logs/partition-operation-path-before.json)有20失败断言，这不是20个独立缺陷。覆盖：

- 嵌套挂载点、相邻名称边界、/system别名、/sdcard归属。
- 目标返回失败、子分区失败、父子调用、同块设备别名卸载。
- cache降级成功/失败、and-sec专用入口和既有tmp语义。

底层Wipe、Repair、Resize、Mount、实际设备定位及操作锁为替身；未运行格式化/fsck工具、删除目录、挂载或访问任何块设备。这是目标路由和返回值检查，**不是完整文件系统或清除功能验收**。UBSan开启。

设置挂载31断言、设置存储21项、备份55项、恢复54项及profile核心门控均通过。补丁序列从固定基线复现；installclean后`make -j$(nproc) recoveryimage`以30并发成功，新的recovery二进制与镜像内容一致。当前候选[recovery-dijun-unified-partition-paths.img](../imgs/built/recovery-dijun-unified-partition-paths.img)，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`。来源清单记录710文件；封装检查通过，同镜像profile回归9组、102次阶段调用通过。历史全量审计不转移至新镜像。

### 使用范围

后续已补充[15项同镜像ARM64文件系统工具执行](FILESYSTEM-TOOLS-EXECUTION.md)：私有普通文件中的ext4/F2FS/EROFS格式化、填充、检查、ext4扩容及部分内容读回。此证据独立于上面的分区对象替身；仍未贯通GUI/真实PartitionManager与内核挂载、加密或物理I/O，不将其升级为完整清除验收。

清除页面选择明确分区后确认；修复/文件系统变更页面只显示底层判定可用的操作。清除Data和格式化Data仍是不同入口，不能因解密失败自动执行。本轮修正目标查找，不是建议操作persist或protect分区；对这些分区的真实清除未执行、未验证。以上为该阶段的历史输入和验证边界；后续 NV 界面限制以上文 0054 / 0060 为准，当前状态见 [工作队列](WORK-QUEUE.md)。
