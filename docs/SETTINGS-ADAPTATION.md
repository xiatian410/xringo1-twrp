# 设置保存与时区离线验证

**状态：用户已确认 `recovery-dijun-unified-backup-manifest.img` 的设置功能正常。** 该观察不扩展为所有版本或所有功能逐项验收；没有新故障不重复诊断。当前候选见 [交付报告](../simulation-report.md)。

## 已维护的修正

- **0028**：嵌套 persist 路径按完整路径边界查找，避免设置保存被误拒绝。
- **0033**：设置卡片整行点击，保留移出取消行为。
- **0038**：语言 / 主题保存失败时恢复内存状态，允许重试；目录 fsync 失败不等于磁盘已回滚。

入口导航已有 45 项有限检查，覆盖九个入口的标题、说明、箭头、空白点击与移出取消。LVGL、page host 和原始事件回调执行，目标页、字体、读数及挂载等范围仍有夹具；不据此宣称完整设备界面验收。

历史报告记录于 `simulation-report.json`；本地 `logs/` 不随源码发布。下文保留修正机制、复现入口和历史证据边界，其中旧候选、待采集及未解决表述不覆盖上述用户确认。

## 2026-11-12：嵌套 persist 路径导致保存被拒绝

2026-11-12 新增现场证据分两处：用户贴出的 `getevent -lt /dev/input/event3` 回显显示 raw-off 后有 `ABS_MT_TRACKING_ID`、`BTN_TOUCH`、变化的 X/Y 和成对 UP；解析为215条事件、7组按下/抬起，坐标约为面板的100倍并能映射回屏幕范围。所贴事件的原始X约109..1327、Y约2263..3103，集中在屏幕下部，不能证明设置页控件被点中。单独的 `imgs/built/1/touch-after-raw-off.txt` 是 UTF-16LE dmesg，不含这段getevent回显，也没有本次设置操作的GUI回调或Flush/persist回执。故目前只能确认该次raw-off后Linux input层有坐标；GUI消费和设置保存仍未知。当前源码上的设置行、保存路径回归通过，但其Android挂载/硬件是替身，不能用来判断运行镜像或现场persist。不要清除或重置已有设置文件。

用户报告多项设置无法修改后，发现真实分区查找此前先调用GetRootPath，把`/mnt/vendor/persist/TWRP`截成`/mnt`，然后与fstab登记的`/mnt/vendor/persist`作精确匹配。dijun没有`/mnt`分区，因此IsMountedByPath和MountByPath都会找不到persist；InfoManager的挂载保护会拒绝保存，即使该persist实际已由MiTEE脚本挂载。GUI通用开关在Flush失败时还原，语言/主题在失败时停止应用。这是确定的软件缺陷；尚无本次设置操作后的手机日志，不能把全部用户症状一并认定已修复。

维护补丁`patches/0028-nested-partition-paths.patch`让FindPartitionByPath按路径边界选择最长mount/symlink前缀，MountByPath/UnmountByPath使用选中分区的真实挂载点。支持`/system`映射与`/sdcard`别名；规范化`.`/`..`和尾斜线，拒绝把`persist-other`当作persist。保留存储错误传播与原设置文件，不删除或绕过校验。

新增[真实方法检查](../tests/nested_partition_path_test.py)执行原始/修改后的查找、挂载入口与InfoManager的twPersistMount，只有底层分区Mount/IsMounted、mkdir和操作锁为替身。旧实现31断言中13失败，[修改后31项通过](../logs/nested-partition-path-test.json)，包含无`/mnt`分区的实际fstab形状、已有/新挂载、挂载失败和备份info不依赖persist。此前21项设置检查把整个PartitionManager替换为布尔替身，无法发现此缺口；不能再用它单独证明真实分区匹配。 历史现场`logs/bootfix-recovery.log`第1023、3425、3988、3991行已记录同一路径的`IsMounted: Unable to find partition`。该旧版本仍继续保存，因此它证明路径缺陷曾在设备发生，不能作为本次新保存保护拒绝的直接回执。

21项设置文件回归、备份/恢复会话回归和profile核心门控在当前源码上通过。新候选`recovery-dijun-unified-touch-settings.img`同时包含普通触摸报告请求与嵌套路径修正，installclean后30并发构建并通过包装/新二进制一致性检查。SHA256 `487b5ce3d991e46241bcf7768350d8986b135f6e9b6d5b9aa4c3deb6e5457e32`。不访问手机或persist；设置保存、自动触摸和物理震动仍待对应现场证据。

## 修复内容

原实现以 `wb` 打开设置文件，立即截断旧内容；未检查 `fwrite` 和 `fclose` 的结果。
`DataManager::SaveValues()` 又忽略底层返回值，使 GUI 已有的保存失败处理无法得到错误。

维护树的 `0010-atomic-settings-persistence.patch` 修复了以下路径：

- 在同一目录用唯一临时文件保存；检查写入、flush、文件 fsync 和关闭结果，再用 rename 提交完整文件。
- 提交前失败时保留旧设置，并清理此次临时文件。若进程在提交前突然退出，旧文件保留；遗留临时文件不作为设置读取。
- 提交后执行目录 fsync。若这一步失败，返回失败并记录“已替换但持久性不确定”；此时可见的是完整新文件，不能声称仍是旧文件。
- 保存前拒绝无法按现有格式读回的字段：长度超过 510 字节、含嵌入 NUL；保留现有版本头和二进制布局。
- 先验证完整输入，再更新内存设置。截断、半条记录、错误长度、缺少终止 NUL、非法键都返回失败，保留原值与默认值。
- persist 挂载失败时拒绝读写设置，避免把 ramdisk 中的临时目录当成持久存储。备份 `.info` 文件继续独立工作。
- `DataManager::Flush()` 向 GUI 返回真实结果；日志只有在保存成功时才报告成功。

旧版本号不同的文件仍按既有规则跳过并保留默认值。文件权限与 SELinux 标签继续沿用原来的元数据处理；主机替身不验证 Android SELinux 标签。

## 证据

[修改前报告](../logs/settings-before-fix.json)覆盖首轮 19 组，其中 12 组未通过。
[修改后报告](../logs/settings-regression.json)增加挂载失败和备份文件独立性检查，共 21 组通过，并启用 UBSan。
报告包含源码与测试文件 SHA-256。新增两组不属于首轮修改前报告。

| 范围 | 已覆盖的行为 |
|---|---|
| 正常文件 | 新建、覆盖、中文键、空值、整数、默认值保留、权限、无版本头的 `.info` 格式 |
| I/O 故障 | 短写、ENOSPC、flush/close/fsync/rename/mkstemp 失败、父目录缺失 |
| 提交边界 | 提交前进程退出保留旧文件；目录 fsync 失败时完整新文件可读，但返回失败 |
| 损坏输入 | 截断头、尾部垃圾、孤立字段、零/超长长度、终止符缺失、嵌入 NUL、非法键 |
| 挂载 | persist 不可用时拒绝设置读写，恢复后可保存；其他路径的备份 `.info` 不依赖 persist |
| 上层返回 | 实际 DataManager Flush 传播错误，失败后锁可释放，后续保存恢复 |
| 时区 | 一次性旧默认迁移、保存后重新加载、自选时区/偏移/DST 保留、已有迁移标记、无设备默认属性 |
| 日期转换 | 历史 UTC 2026-11-10 18:09:53 转为 UTC+8 的 2026-11-11 02:09:53；美国冬夏时偏移与 UTC+8 全年固定偏移 |

运行命令：

```bash
python3 tests/settings_persistence_test.py
```

## 使用和边界

### 2026-11-12：整行设置点击与取消

维护补丁 `patches/0033-settings-row-hit-area.patch` 修正公共复选框/开关行的点击区域：文字、空白和右侧指示器统一命中卡片，原生指示器不再另行切换。复用公共press cancel guard，手指移出再返回、丢失按下、滚动列表均取消修改；禁用控件不触发。回调仍以原toggle为target并保留user_data，维持现有设置保存、失败回退和其他使用方的业务逻辑。

[真实LVGL输入检查](../tests/settings_row_test.py)共20项：checkbox/switch各10项，执行生产组件、公共guard和从gui2.cpp提取的真实general_setting_event_cb。覆盖文字/指示器/空白点击、连续两次切换、移出/返回、press lost、真实父容器滚动、禁用及保存失败后重试。保存与hardware为替身，成功只断言一次feedback请求，不证明电机输出；不是全页面路由或真实persist测试。旧组件同组8项失败，[新结果20项通过](../logs/settings-row.json)，[旧结果](../logs/settings-row-before.json)保留。

当前候选为 [recovery-dijun-unified-settings-row.img](../imgs/built/recovery-dijun-unified-settings-row.img)，SHA256 `3c0bed7c0e93b2b5b7a50aada62165d69562c6217955a35d85eb4e03ba7cbe67`。已按installclean及make -j$(nproc)构建，716来源和封装/新二进制核对通过。它解决已确认的点击区域缺口，不能据此认定用户所有设置问题均来自此处；操作前后采集工具仍适用于保存后回退的排查。没有修改震动播放/校准/增益，也没有访问手机。

### 设置仍无法修改时的定向采集

当前settings-row候选已继承0028路径修正。不能仅因用户报告“设置都改不了”就认定该修正已在设备生效，也不能用早期保存成功日志代替本次点击回执。

下载并解压 [设置采集工具](../tools/settings-state-collector.zip)，在解压目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\collect-settings-state.ps1
```

脚本先保存一次状态，然后等待用户在“设置 → 常规”点击一次“交换导航按钮”的右侧复选框并填写现象，再采集第二次。请注明点击无响应、短暂改变后回退，或保持改变。输出当前目录的 `dijun-settings-日期-时间-PID.zip`。不需要重新刷镜像或重启。

采集包含完整Recovery/logcat/dmesg、挂载信息、属性和设置文件元数据/摘要；不复制设置文件内容，不挂载、不删除或重置设置，也不自动修改设置。设置文件不存在等错误保留在commands.tsv中，属于待分析证据。共享前可检查日志中的设备标识。没有在Windows、Android或手机上执行采集工具；本地主机仅完成shell语法和打包检查。

分析时先确认事件是否触发保存，再看 `Cannot access settings`、`Failed to save settings`、`Settings field exceeds` 或 `directory sync failed`。没有保存日志也可能是点击未命中、SetValue被拒绝或BackingFile尚未初始化，不能直接推断为存储损坏。settings-row之前的常规页只有右侧复选框绑定修改回调，文字区域不触发切换；新候选已修正此缺口。

通过“设置 → 时间与时区”选择时区、偏移、DST；保存后由现有入口重新加载。
默认值为 `CST-8`（POSIX 表达式中的 UTC+8），迁移只针对完整匹配旧美国默认配置且未标记迁移的设置。
自选配置保留；无需通过改写 RTC 补偿时区差异。

本项修复的首个输出是 [recovery-dijun-unified-settings.img](../imgs/built/recovery-dijun-unified-settings.img)，
镜像与来源记录在相邻 JSON 中。此前统一候选保留；新文件增加设置修复，不扩大硬件验证声明。

这些测试属于 S2，编译及镜像内容检查属于 S3。主机文件系统、libc 和故障替身不能证明真实断电恢复、
Android persist 挂载/标签、RTC 冷启动读错/漂移或手机上的完整 GUI 操作；对应硬件行为仍未验证。

settings-row构建后验证：同镜像profile回归9组/102次阶段调用通过，21项既有控件反馈检查通过；来源重建73+1+3文件一致、0待更新。公共行20项输入检查及保存21/路径31回归作为不同边界证据保留。未确认实际触摸冷启动、设置保存或物理震动，完整目标仍进行中。

2026-11-12 后续产物：当前候选已切换为 `recovery-dijun-unified-mount-mode.img`（SHA256 `848096d4…`），只新增 system/vendor 挂载模式失败处理，继承 settings-row 控件与设置存储修正；libgui2/libtwrpminui 字节与上一候选一致。settings-row 交付审计绑定旧镜像/旧树，属于历史证据，不应在新树上当成当前总验收。当前交付见 `logs/mount-mode-delivery.json` 和[挂载范围](MOUNT-MODE-ADAPTATION.md)。设置现场修改/保存仍未确认。

settings-retry交付收尾：新镜像内脚本回放9组/102次阶段调用通过；724来源及维护补丁76+1+3文件重建一致、0待更新。已有控件反馈21项通过，FF库与temperature-ui一致。交付审计见logs/settings-retry-delivery.json；设置现场、物理震动及完整12组仍未完成。


2026-11-12 设置完整保存链路续查：新增tests/settings_joined_test.py/.cpp，在私有chroot保留真实/mnt/vendor/persist/TWRP路径，执行真实LVGL文字点击/公共行/取消guard/general回调→twrp_settings_store→DataManager Get/Set/Flush/Save→分区lookup/mount入口→InfoManager文件保存与重新加载。checkbox/switch各11场景，共22项通过；只换回HEAD旧partitionmanager方法同22项均失败。已有挂载/保存时挂载、拒绝挂载、ENOSPC、短写、只读、rename失败、目录fsync失败、BackingFile未初始化、常量键拒绝、其他字段超长均覆盖，并在故障解除后再次点击验证重试。目录fsync失败会出现磁盘新值已发布但UI/内存回退，不声称磁盘回滚。底层Mount/IsMounted、属性/元数据、页面导航/电机为显式替身，不是完整Recovery或现场persist；不推导用户设置已恢复。无生产修改或新构建，当前610f4acc诊断候选不变，震动/设置现场和完整12组继续进行中。复现python3 tests/settings_joined_test.py；审核python3 scripts/audit_settings_joined.py，范围详见docs/SETTINGS-ADAPTATION.md。


时区失败回退续修见[TIMEZONE-SAVE-ADAPTATION.md](TIMEZONE-SAVE-ADAPTATION.md)，当前候选以simulation-report.json为准；不是现场所有设置问题已解决的结论。
