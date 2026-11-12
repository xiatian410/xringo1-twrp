# 分区列表、OTG 发现与存储挂载

本文合并分区显示策略、OTG 设备发现、system/vendor 挂载模式与存储选择的实现记录。历史候选与测试数字保留各自时间范围，当前交付以根目录验证报告为准。

2026-11-12 根据用户最新要求，0054将NV/proinfo/protection排除普通GUI挂载目标，并在后台阻止手动挂载和卸载（含规范化路径及解析别名）。此前“存在且可挂载所以显示”仅解释旧行为，不再作为当前普通界面的展示策略。原厂fstab声明及内部核心MountByPath保留；persist和metadata不在本次NV禁用集合。此策略不是对特权shell或备份恢复工具的访问控制。26项策略/旧17失败、六项LVGL链通过；新候选为recovery-dijun-unified-nv-mount-policy.img，未实机测试。

最新交付索引见`simulation-report.json`和`ADAPTATION-GOALS.md`；当前候选继承0048 OTG发现修正和0054 NV普通挂载限制。下方031497e5、741来源与旧列表策略均为历史说明，不代表当前NV条目仍允许普通GUI挂载。

2026-11-12 收到11张实机截图。上方内部存储673GB是有效的用户共享存储；列表中另有大量0B的`/storage/usbotg-sdd-1`、`sdb-*`、`sdc-83/84/85`、`sda-*`。这些是OTG枚举生成的项目。此前没有截图时的结论和已分类列表夹具范围见下方历史记录；当前不再缺少这类直接页面证据。

已定位并复现源码缺陷：原厂OTG配置为`/devices/platform/soc/*.xr_usb/*.dwc3/xhci-hcd.*.auto*`，但HandleUevent、ResyncUeventDevices和Coldboot均在第一个`*`截断，仅保留`/devices/platform/soc/`；内置UFS控制器也位于该路径，因而可能生成全部内置分区的OTG子对象。第二个缺陷是GUI的is_otg_path不识别真实`/storage/usbotg-*`，使这些项沿用“存储空间N”泛称。截图路径与复现机制吻合，但不把主机测试写成已证明每个实机对象的物理来源。

维护补丁`dtsrc/O1_asic_dual/patches/0048-otg-controller-discovery.patch`在三条发现入口共用完整sysfs模式匹配；支持控制器节点的后代、`/sys`前缀和路径分界，保留fstab的通配语义。没有按sda/sdc名称或removable标志排除设备，USB硬盘可以使用这些名称且removable可能为0。GUI共用分类器补充真实路径，合法OTG按磁盘/分区名称与数值顺序显示；不通过隐藏0B行掩盖发现错误。

`python3 tests/otg_discovery_test.py`执行生产热插拔、resync、coldboot、pending处理与FindWildcardBlockDevices。静态host可执行程序在私有临时chroot中访问普通文件/符号链接，USB/UFS拓扑来自显式夹具；块设备stat模式、文件系统分类、FindActualBlockDevice外层、容量及挂载是边界。12场景覆盖UFS85分区拒绝、USB多分区/无分区、重复事件、子分区移除/添加、重扫描删除/恢复、延迟节点、完整模式约束和名字交叉。修正通过12项，旧实现相同夹具8项失败，报告`logs/otg-discovery.json`、`logs/otg-discovery-before.json`；其中controller-pattern仅检查新增匹配器，不代表旧实现使用过该匹配器。没有真实netlink recv溢出、UDC或USB文件传输验证。

`tests/mount_list_chain_test.py`增加第六场景，使用`/storage/usbotg-sdz-2/10`，经实际列表快照/backend/LVGL builder核对`OTG sdz 2/10`命名和数值排序；其余五项回归保留。此列表输入仍是已分类夹具，与上面的发现测试分别说明边界。

历史截图中NVData/NVCFG、protect_f/s、persist等出现在挂载复选框，是旧fstab与“存在且可挂载”的展示策略所致。12份原厂fstab来源核对仍有效；这些条目不因此成为用户共享存储，不是本次假OTG项目的修复对象。截图未显示原始emmc类型NVRAM成为挂载项，无依据删除原厂声明。

构建与交付：installclean及`make -j$(nproc)`（30并发）完成。候选`imgs/built/recovery-dijun-unified-otg-discovery.img`，SHA256 `031497e53bf500805a2ba6d74b4bc0a9315fbdbc5e6740ec028df33059d27561`；741份生产来源和六配置封装/新二进制核对通过。设置保存完整链路22项、存储选择15项回归通过，分别见`logs/otg-discovery-settings-joined.json`与`logs/otg-discovery-selection.json`。当前镜像profile9组/102阶段调用、module4组/24阶段调用检查及定向来源审计统一绑定在`logs/otg-discovery-delivery.json`。历史全量审计的来源漂移仍未全部解决，不把本次定向审计当作全部目标验收。交付审计期间旧backup-manifest镜像及来源清单已不在原路径，不能重新做旧镜像字节比较；审计改为明确核对同步前保存的设备树规格、固定Git基线与旧源码副本，当前候选741份来源直接核验。此来源规格比较不冒充旧镜像二进制复核。用户已确认的settings正常结论保留；本修正不构成自动触摸、物理震动或全部适配完成证明。

---

以下为收到截图前的历史检查点，所述“缺截图”及“当前”仅指当时。

## backup-manifest 挂载页项目核对

2026-11-12 用户确认当前backup-manifest镜像设置正常，同时询问挂载页三十多个“内部存储”和NV项目。此次只做实际镜像与源码核对，无生产改动、隐藏条目、分区操作或新构建。

原厂来源现已核实：`python3 scripts/audit_stock_nv_fstab.py`直接从六份OTA的recovery/vendor_boot镜像重新读取ramdisk，各镜像先按payload-manifest.pb中的尺寸与SHA256验证，再与现有提取文件逐字节核对。12份原始fstab都包含nvram、proinfo、protect_f/s、nvdata、nvcfg，六项的设备路径/挂载点/格式/挂载参数/fs_mgr参数与当前维护树完全一致；报告`logs/stock-nv-fstab-audit.json`。所以这些配置有原厂依据，不是据名称猜测保留的其他平台残留。原厂声明不能证明实际分区存在、数据用途、允许修改或应在普通GUI暴露；也不能解释现场重复“内部存储”。此次不删除、改写或隐藏条目。

当前镜像SHA256为`9a1b057d001821b0d9a908c003c3810f5295e6fa500e1716f59ae50364126123`。运行`python3 scripts/inspect_mount_inventory.py`，报告`logs/shipped-mount-inventory.json`。镜像内`system/etc/recovery.fstab`与维护树内容一致，共32行声明、22个不同挂载点；10个逻辑分区各有ext4/EROFS两个格式候选。`ProcessFstabFile`将同挂载点传给`ProcessFstabLine`的additional_entry，后者保存替代格式并拒绝另建对象。因此配置行数不能直接当作GUI条目数。

后续列表到界面验证：`python3 tests/mount_list_chain_test.py`的五场景通过，报告`logs/mount-list-chain.json`。从同镜像声明构造已分类分区夹具，加两个显式OTG设备，执行生产GetPartitionList的mount/storage分支、真实快照订阅/发布与backend targets/storages，再调用真实LVGL挂载/存储选择builder。分类、存在状态与挂载状态是夹具，未运行ProcessFstabLine、块设备发现、点击或Android GUI。正常场景20个mount行、3个storage行（一个内部存储、两个OTG），32配置行未被复制成32存储行；30次刷新未累加。nvdata缺失时mount行减少，data缺失时storage行减少；NV/emmc没有进入storage，emmc没有进入mount。删除/恢复OTG后行数相应恢复。显式把所有非OTG挂载分区display_name设为Internal Storage时出现19个同名标题（18挂载行加顶部当前存储卡），说明builder保留输入名称，不能据此认定现场已发生同一上游命名错误。正常标签与每个目标逐项核对，没有发现应立即修改的生产缺陷。

定向来源审计：`python3 scripts/audit_current_offline_paths.py`核对当前镜像及738份生产来源、45项设置入口、五项列表与七项修复工具接续，输出`logs/current-offline-paths-audit.json`。这不是完整任务总审计；历史总审计来源漂移仍未解决。未生成新镜像，用户设置正常的反馈保持有效。

| 类别 | 配置内容与当前列表行为 |
|---|---|
| 用户内部存储 | `/data`的data/media配置提供内部共享存储；不是所有内部物理分区都属于用户文件存储。storage列表要求`is_storage_ && is_present_`，与mount列表不同。 |
| 系统逻辑分区 | system、system_ext、vendor、product、mi_ext、mi_product、vendor_dlkm、system_dlkm、odm、odm_dlkm；10个挂载点、20行格式声明。实际出现还取决于逻辑分区准备和存在状态。 |
| 数据与维护文件系统 | data、metadata、persist、protect_f、protect_s、nvdata、nvcfg、cache；挂载列表当前只筛选`can_be_mounted_ && is_present_`，没有普通/维护分区分级过滤。 |
| 原始镜像分区 | nvram、proinfo、misc为emmc类型，不经SetupFileSystem设置可挂载能力，按此配置不应显示为mount复选框；备份等其他列表语义不同。 |
| OTG | `/storage/usbotg`是可移动设备模板，不是内部存储；运行时可按设备枚举扩展，静态数量不能精确预测最终GUI条目。 |

非emmc声明合并后为19个挂载点，其中包含OTG模板。NVData/NVCFG显示的原因是维护树显式保留了对应ext4条目，而mount页目前展示所有存在、可挂载分区；出现本身不意味着它们应作为用户内部存储、备份目标或普通文件目录使用。名称不能证明本机每个NV分区的具体数据语义，不从名称推导应格式化或移除它们。

源码入口：`partitionmanager.cpp:GetPartitionList`分别生成mount/storage列表，`gui2/backend/twrp_mount_backend.cpp:targets/storages`保留对应名称，`gui2/pages/mount_page.cpp`将当前存储卡片与分区复选框分区显示。只有上方当前存储卡片取`tw_storage_display_name`；其余挂载复选框使用各条目的`display_name`。当前没有证明源码把所有分区统一命名为“内部存储”。

还缺当前页面的直接证据：若用户描述是三十多个项目都带“内部存储”名称，需要一张包含标题与多个条目的截图，先区分mount列表、storage选择列表、分组标题与重复标签，再核对运行列表。不能把32行fstab解释成已确认的现场重复原因，也不能以此静态核对否定用户观察。此次不要求重刷或重复测试设置。

<a id="mount-mode"></a>

## system/vendor 挂载模式事务

2026-11-12，维护补丁 `0034-mount-mode-transaction.patch` 修正 `gui2/backend/twrp_mount_backend.cpp` 的 `mountsystemtoggle`。旧代码只卸载 system，直接修改仍挂载 vendor 的模式；忽略重新挂载失败，并用后续 vendor 分支覆盖前面的失败。无独立 vendor 也会误报失败。它是挂载模式切换缺陷，不是一般设置保存或物理震动故障的根因结论。

新实现由现有递归操作锁串行化，先查找必需 system 和可选 vendor，保存各自挂载状态及只读策略。所有原本挂载的目标先卸载，然后修改策略，并只重新挂载原本已挂载的目标。全部成功后才提交 `tw_mount_system_ro`；失败返回非零，并尝试恢复原策略与原挂载状态。失败不会被其他分区成功覆盖，operation_end 接收失败状态，返回前刷新分区快照。

回滚也可能失败：重新卸载失败时保留该目标当前策略标志，不能把仍以新模式挂载的目标伪装成旧模式；恢复挂载失败则保留未挂载状态。均有独立日志，并保持操作失败、全局设置不提交。这不是对真实 mount flags 的重新探测，也不是不可失败的原子内核操作。

[执行程序](../tests/mount_mode_test.py)提取真实生产函数，以分区与 DataManager 边界替身覆盖读写/只读、已卸载、只有 vendor 已挂载、可选 vendor 缺失、system 缺失、两个卸载失败、两个 remount 失败、两种回滚失败、非法参数、重复调用和混合原模式。真实递归锁、ASan/UBSan 和宿主编译执行；不访问设备、块设备或执行 mount。[新实现 15 项通过](../logs/mount-mode.json)，[相同用例旧实现 8 项失败](../logs/mount-mode-before.json)。不是 8 个独立缺陷。

交付候选 `recovery-dijun-unified-mount-mode.img`，SHA256 `848096d4b42b41926e2741ba4a34ef1ec4922aaa66036281724e7a2d65b652f1`。installclean + make -j$(nproc)（30并发）构建，717 个来源文件及打包/新二进制核对通过；同镜像 profile 回归结果单独记录。第一次目标编译发现替身错误接受 `UnMount` 名称，已按真实 `Unmount` API 更正并重跑清理构建，失败日志保留。

入口为“挂载”页的 system 读写切换，按现有只读警告确认；动态分区设备可能隐藏该控件，启动只读选择也复用此后端。真实启动选择对返回值的界面展示、完整页面异步体验、真实内核文件系统挂载及用户现场状态仍未验证。没有改 AVB、vbmeta、校准或震动参数。全部任务保持进行中。

<a id="storage-selection"></a>

## 存储选择的失败处理

维护补丁 `0035-storage-selection-failure.patch` 修改真实 `select_storage`：目标必须存在、标记为存储并且路径等于发布的存储根；可移除存储即使已挂载也刷新容量。刷新禁止再次尝试挂载，避免 `UpdateSize` 通用观察路径把挂载失败返回为成功。容量失败、刷新时设备消失或设置值提交失败均返回失败；本次新挂载会尝试卸载，原先挂载的目标保留。卸载恢复失败单独记录，不能声称状态已恢复。

满盘但容量可读的目标仍可选择，后续写入任务负责空间检查。内部存储继承原有挂载逻辑。GUI 发布的 `storage_path_` 是选择入口接受的根路径，子目录不作为存储设备提交。

[测试](../tests/otg_selection_test.py)抽取生产选择方法和真实 `TWPartition::UpdateSize`，执行真实递归锁和作用域清理；底层挂载、设备存在、statfs/df、容量与 DataManager 是替身。ASan/UBSan 下 15 项通过；[旧实现同组](../logs/otg-selection-before.json)12 项失败，这是场景数而非独立缺陷数。覆盖新挂载、已有挂载、失败回退、拔除窗口、无目标、非存储、子目录、满盘、df 回退、恢复卸载失败、内部存储和提交失败。没有执行 USB 发现、真实挂载或读写中拔除。

复现：`python3 tests/otg_selection_test.py`；旧实现使用 `--backend logs/otg-selection-before/twrp_mount_backend.cpp --report logs/otg-selection-before.json`。改变选择方法时同时运行 mount_mode_test、settings_persistence_test、nested_partition_path_test 和 settings_row_test；各测试的替身边界仍然适用。

交付 `recovery-dijun-unified-otg-selection.img`，SHA256 `aaa4b25c1bd58a0b61508288a479d824f38701c38d2ed606530b39c503181ef7`。installclean 后 `make -j$(nproc)`，30 并发构建，718 来源与封装/新二进制核对通过。继承设置整行点击和 persist 路径修正；这些改动不能证明用户这次设置故障已经消失，也不是物理震动修复。

同镜像验证收尾：9组/102次profile阶段调用通过，718份构建来源仍一致，设置交互20/保存21/路径31与挂载模式15回归通过；当前交付审计见 `logs/otg-selection-delivery.json`。硬件与完整12组验收仍未完成。
