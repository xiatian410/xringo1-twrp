# 设置保存与时区

**用户已确认 `recovery-dijun-unified-backup-manifest.img` 的设置功能正常。** 无新故障不重复诊断；该观察不扩展为所有版本逐项验收。当前候选见 [交付报告](../simulation-report.md)。

## 设置文件与错误传播

设置原子保存修正（维护系列中的早期 0010） 使用同目录唯一临时文件，检查写入、flush、文件 fsync 和关闭后，以 rename 发布完整设置；提交前失败保留旧文件并清理本次临时文件。进程退出遗留的临时文件不作为设置读取。

提交后执行目录 fsync。失败时返回错误并记录持久性不确定，此时新文件已经可见，不能声称磁盘已回滚。格式保留原版本头与布局；拒绝超过 510 字节或含嵌入 NUL 的字段。先验证完整输入，再更新内存；损坏输入保留旧值和默认值，版本不匹配按原规则跳过。

`DataManager::SaveValues()` 与 `Flush()` 向 GUI 返回实际错误，只有成功才记录保存成功。persist 挂载失败拒绝设置读写，避免将 ramdisk 临时目录误当成持久存储；备份 `.info` 文件独立工作。权限与标签沿用原元数据处理，主机夹具不验证 Android SELinux。

## 分区路径与点击

补丁 0028 按完整路径边界选择最长挂载点 / 别名前缀，修正 `/mnt/vendor/persist/TWRP` 被截为 `/mnt` 后找不到分区的问题。挂载入口使用选中分区的真实挂载点，支持 `/system` 和 `/sdcard` 映射，规范化 `.`、`..` 与尾斜线，拒绝把 `persist-other` 当成 persist。既有设置文件保留。

补丁 0033 将文字、空白和右侧指示器统一为整行点击；原生指示器不重复切换。公共取消 guard 处理移出、press lost 和滚动，禁用控件不触发。回调保留原 target / user_data 和错误回退逻辑。

补丁 0038 在语言 / 主题保存失败时恢复内存状态并允许重试。目录 fsync 失败后的磁盘发布依然不具回滚保证。

## 时区与保存失败回退

通过“设置 → 时间与时区”选择时区、偏移和 DST。默认 `CST-8` 是 POSIX 的 UTC+8；旧默认迁移仅匹配完整旧美国配置且没有迁移标记的设置，自选值保留。不通过改写 RTC 补偿时区差异。

补丁 0042 在提交前保存五项旧值。部分 SetValue、时区生成或 flush 失败时，恢复选项及精确旧 `tw_time_zone`，更新旧环境，并保留待选项供重试；同时检查时区 / 偏移索引边界。回退不能从 GUI 选项重新构造自定义时区，例如 `CUSTOM-9:45`。

回退不重复 flush，不篡改已经 rename 的磁盘文件。恢复 SetValue 自身持续失败或存在并发修改时，不保证完整事务。

## 已有定向验证

| 入口 | 范围 | 边界 |
| --- | --- | --- |
| `tests/settings_persistence_test.py` | 21 组，含格式、I/O 故障、提交边界、挂载与时区 | 一次性文件及挂载 / 属性替身；启用 UBSan |
| `tests/nested_partition_path_test.py` | 31 断言；旧实现 13 失败 | 原查找、挂载入口及 InfoManager 保护；底层 Mount 为替身 |
| `tests/settings_row_test.py` | 20 项；旧组件 8 失败 | 真实 LVGL 输入、公共 guard 及回调；保存为替身 |
| `tests/settings_navigation_test.py` | 九个入口共 45 项 | 实际 page host / 路由；目标页面、字体和读数为夹具 |
| `tests/settings_joined_test.py` | 22 场景；只换回旧分区方法时全部失败 | 点击到原文件保存 / 重载；底层挂载、属性及元数据为替身 |
| `tests/timezone_retry_test.py` | 17 项；旧回调 11 失败 | 原回调 / adapter / libc，存储和路由为夹具；旧对照只替换回调 |

时区用例包括 UTC+8、分钟偏移、DST、五个写入位置失败、flush 失败 / 重试、索引边界、无效事件和空 store。保存链覆盖 ENOSPC、短写、只读、rename / fsync 失败、未初始化 BackingFile 等，核对失败后重试。

报告与来源摘要保留于本地 `logs/` 及 `simulation-report.json`，公开摘要见 [CURRENT-VALIDATION.json](CURRENT-VALIDATION.json)。来源未变时复用结果，不重复完整检查。

## 故障定位入口与限制

仅有新故障时使用 [设置采集工具源码](../tools/settings-state-collector)，区分点击未触发、修改后回退和保存成功。先查看保存回执及 `Cannot access settings`、`Failed to save settings`、字段超长或目录同步失败；没有保存日志不能直接判为存储损坏。不要删除或重置原设置文件。

离线结果不证明真实 persist 挂载 / 标签、断电持久性、Android Bionic 全 GUI、RTC 冷启动或漂移。工具采集与用户现场结果独立记录，不将主机夹具写成硬件验收。
