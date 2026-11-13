# MTP 上传、日期与目录元数据

本文集中说明文件上传提交、日期解析与目录上传状态。当前交付见[交付报告](../simulation-report.md)；各补丁的历史候选与报告哈希保留在机器索引和 Git 历史中，不作为完整 USB 验收。

## 文件上传原子发布（0041）

文件先接收到同目录的唯一 `.mtp-upload-*` 临时文件，接收、长度校验、文件同步和关闭均成功后才用 `rename` 发布。发布前失败只清理本次临时文件，保留已有目标；新建与覆盖使用同一流程。

数据库在同一 observer 锁下创建并登记精确临时路径。inotify、ReadDir 与 overflow reconciliation 均不发布传输中的临时文件。`createSendObjectFile` 是 `IMtpDatabase` 的必需接口，当前 `TwrpMtpDatabase` 转交所属 storage；不能绕过登记仅在 server 中创建临时文件。

权限沿用 `FILE_PERM` / `FILE_GROUP`。覆盖目标成为新 inode，不保留旧 inode 的扩展属性或硬链接关系；其他旧硬链接仍指向旧内容。`rename` 后目录同步失败只警告：完整新文件已经可见，但持久性不确定，不能承诺回滚。

68 项 server / database / storage 主机检查包含新建与覆盖各 11 个原子发布场景：成功、接收失败、长度不足、同步失败、零写、rename 失败、临时文件创建失败、关闭失败、目录同步失败、取消和进程退出。旧实现五项覆盖对照均失败；移动 / 复制 48 项回归通过。

```bash
python3 tests/mtp_objects_test.py --report logs/mtp-atomic-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-atomic-transfers.json
python3 scripts/audit_mtp_atomic_upload.py
```

<a id="upload-datetime"></a>

## 日期解析与文件时间（0039 / 0049）

0039 按 MTP 格式校验年月日、时分秒、一位可选小数、`Z` 及 `±HHMM`。显式偏移转换为 UTC，不依赖 Recovery 时区；无偏移沿用本地 `mktime` / DST 策略，并反向核对字段，拒绝无效日期和 DST 空档。DST 回拨的重叠时间沿用 libc 选择，不承诺特定偏移。解析失败不改变调用者输出。

年份为 0001～9999，偏移小时 00～23、分钟 00～59，不接收闰秒 60；小数不进入秒精度 `time_t`。合法 Unix 负一秒不因返回值为 `-1` 而被拒绝。直接执行生产 `MtpUtils`，以 Python `datetime` 独立计算预期的 80 项检查通过；旧实现 79 项中 48 项失败，旧版空指针输入未执行。

0049 将 server 的修改时间改为 `optional<time_t>`，区分合法零秒 / 负秒与缺失 / 非法日期。有效时间应用到上传临时 inode；无日期或非法日期保留新文件的当前时间。接收失败不尝试设置日期，`futimens` 失败在发布前中止，保留旧目标。

94 项对象链路中新增日期场景 16 项，新建 / 覆盖各八项：epoch 0、等价偏移、epoch -1、缺失、非法、时间设置失败、接收失败、文件同步失败；检查实际文件时间、内容、数据库日期、旧目标保持、临时文件清理和后续上传。旧实现同组十项失败，移动 / 复制 48 项回归通过。

```bash
python3 tests/mtp_datetime_test.py --report logs/mtp-datetime.json
python3 tests/mtp_objects_test.py --report logs/mtp-upload-time-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-upload-time-transfers.json
python3 scripts/audit_mtp_datetime_delivery.py
python3 scripts/audit_mtp_upload_time_delivery.py
```

首次接收失败夹具未排空剩余 bulk 数据，后续重试失败，报告保留在本地 `logs/mtp-upload-time-first-attempt.json`。最终该项使用 payload 已完整进入初始缓冲后的接收失败，不将 USB 替身调整当作真实端点恢复修正。

<a id="directory-finalization"></a>

## 子文件上传后的目录时间：现有协议路径

目录创建时设置的修改时间会被随后创建子文件更新。当前 server 没有“整棵目录上传完成”的协议通知；`CloseSession` 也不表示主机希望恢复哪一次目录日期。数据库将 `DateModified` 描述为只读，`SetObjectPropValue` 返回不支持；所对照的 Android `MtpDatabase.java` 同样只实现文件名 setter。因此，本批不增加在断开或会话结束时自动重放旧时间的行为，避免覆盖后续修改。

现有可用路径是：主机完成子文件上传后，对同一父目录和目录名再次发送带日期的 `SendObjectInfo`。0059 已允许接纳已有目录并设置时间，不需要 `SendObject` 数据阶段。这个路径要求客户端主动发送，不能保证 Windows 或其他客户端会采用它，也不把它当作通用属性 setter。

`tests/mtp_objects_test.py` 的五个新增场景执行生产 server / packet / database / storage：根下目录、嵌套目录、设置时间失败后的重试、会话关闭不重放、日期属性只读。每项先通过协议实际上传子文件，确认目录时间已改变；显式重发场景再验证 epoch 0、目录 inode、目录与子文件 handle、文件内容、数据库日期及重新打开会话后的结果。五项通过，启用 ASan / UBSan。本地报告为 `logs/mtp-directory-finalization.json`。

这是现有行为的定向证据与实现决定，没有生产修改或新构建。报告来源中与现有镜像构建清单重叠的 17 份 MTP 文件哈希相同；构建清单并未覆盖全部 MTP 文件，不能将此称为完整库内容审计。主机私有 chroot 使用普通文件、inotify 和线程；USB、属性与日志是替身，未执行 ARM64 MTP、实际端点或 Windows 客户端。

```bash
# 已执行；相关输入与实现未变时复用，不例行重跑其他 MTP 套件。
python3 tests/mtp_objects_test.py --cases directory-final-root directory-final-nested directory-final-retry directory-final-close directory-final-readonly --report logs/mtp-directory-finalization.json
```

<a id="directory-metadata"></a>

## 目录上传时间与完成状态（0059）

`SendObjectInfo` 创建或接纳目录后，以 `O_DIRECTORY | O_NOFOLLOW` 打开目录 fd，应用有效修改时间（包括零秒、负秒及偏移），再刷新数据库。目录操作立即结束，不进入等待文件 `SendObject` 的状态。时间缺失或非法时不设置日期。

目录打开、时间设置或关闭失败时返回错误并释放数据库传输保护；保留目录和现有子文件供重试。不承诺撤销已成功的元数据写入或删除新建目录。

生产 server、packet、database 和 storage 使用私有 chroot 的普通文件、inotify 与线程，USB 和属性为替身。新增 16 项覆盖日期、已有目录、open / futimens / close 故障、失败重试、无日期目录后的意外 `SendObject`、后续命令与文件上传。修正前同组 14 项失败；当时对象链路 110 项、移动 / 复制 48 项通过，启用 ASan / UBSan。

```bash
python3 tests/mtp_objects_test.py --report logs/mtp-directory-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-directory-transfers.json
python3 scripts/audit_mtp_directory_delivery.py
```

<a id="active-staging-identity"></a>

## 活跃上传路径被替换时拒绝发布（0114）

上传使用打开的临时文件描述符接收数据，但旧实现随后直接按临时路径 rename 或在失败时 unlink。如果其他文件操作已移走原 inode 并重建同名文件或链接，服务器可能把外部文件发布为上传目标，或者在接收失败时删除替换文件。既有0091只处理传输结束后的遗留可见性，没有覆盖这个活跃阶段。

0114在发布前以lstat核对临时路径为普通文件，且device/inode与接收文件描述符的fstat结果一致；不一致返回错误、保留原目标。失败清理也要求相同身份，保留外部替换文件。结束传输时若发现替换，退役活跃记录后重新协调父目录，让上传期间已被忽略事件的普通替换文件恢复可见。链接仍按既有规则不展示，不跟随其目标。

原server/database/storage、真实私有文件及inotify/线程在ASan/UBSan下241项通过；新增十二项覆盖新建/覆盖目标、普通文件/链接/路径消失，以及接收成功/失败。旧实现同十二项有八项失败；路径消失四项本来就失败返回，作为控制保留。另有既有移动/复制48项回归。替换文件及原目标内容、移走inode的正常接收结果和替换普通文件可见性均核对。

该检查不是原子路径所有权：lstat之后与rename/unlink之间仍有竞争窗口；父目录替换、原inode就地改写、inode复用不在保证内。跨重启归属/回收仍未实现，不按文件名前缀删除用户文件。USB/属性/日志为替身，没有ARM64 MTP、真实USB/Windows或断电验收。此批不重跑完整OTA或已解决功能。本地报告 `logs/mtp-active-identity.json`、`logs/mtp-active-identity-old.json`、`logs/mtp-active-identity-transfers.json`，交付核对入口 `python3 scripts/audit_mtp_active_identity.py`。

<a id="staging-retry"></a>

## 临时文件删除失败后的重试（0081）

旧实现将临时路径按对象 handle 登记。上传失败且 `unlink` 失败时，为避免 observer 暴露临时文件，会保留这条登记。但 `CreateSendObjectFile` 拒绝已有登记的 handle，因此再次覆盖同一已有对象永远无法创建新的临时文件，直到 storage 重建。新建文件失败后节点消失、再次上传取得新 handle，故同样的故障不一定触发此问题。

0081 将结束传输的精确路径移入独立集合，释放 handle 的当前传输登记。ReadDir、inotify 和 reconciliation 同时排除当前临时路径及该集合中的精确路径。重试使用新的唯一临时文件；失败期间已有完整目标不变。**本修正不删除遗留文件、不持久化其归属，不按 `.mtp-upload-*` 前缀隐藏或清除用户文件。** 该阶段尚未处理外部替换同一路径；后续 0091 补齐下述身份检查，跨重启识别仍未完成。

`tests/mtp_objects_test.py` 新增两个场景：覆盖与新建均连续注入两次文件同步失败及 unlink 失败，再成功上传。检查失败目标保持、两份遗留内容不变且隐藏、最终内容、已有 handle 保持，以及用户自建同前缀文件可见且不变。旧实现覆盖场景在第二次失败时无法创建新的临时文件而失败，新建对照通过；修正后两项通过。对象链路共 116 项、移动 / 复制 48 项通过，使用实际 server/database/storage、普通文件、inotify、线程与 ASan/UBSan；USB transport 和属性为替身。

```bash
python3 tests/mtp_objects_test.py --report logs/mtp-staging-retry-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-staging-retry-transfers.json
python3 scripts/audit_mtp_staging_retry.py
```

旧实现对照保存在本地 `logs/mtp-staging-retry-negative.json`，没有改写历史报告。最终镜像先 `installclean`，再 `make -j$(nproc)`，799 份来源、六份 profile。相对 0080 仅 MTP 库、构建属性和 ramdisk 摘要变化；未变的选择与模块证据按原范围复用，不重新运行震动或其他无关套件。当前镜像和 SHA-256 见[交付报告](../simulation-report.md)。未执行 ARM64 MTP、真实 USB / Windows 或设备重启清理。

<a id="staging-identity"></a>

## 遗留路径被用户替换后的可见性（0091）

上传失败且临时文件删除失败后，旧实现只按路径隐藏遗留文件。用户随后删除并重建同名普通文件或目录，或者原 inode 内容发生变化，observer 仍一直忽略该路径，新对象无法出现在 MTP 列表。

0091 在 `mkstemp` 后用 `fstat` 记录设备号和 inode；传输结束时，对仍匹配的普通文件记录 ctime。ReadDir、inotify 和 reconciliation 共用身份核对：路径消失、类型变化、inode 替换或 ctime 变化时撤销旧隐藏登记。未知对象收到修改 / 关闭 / 属性事件时重新检查类型，普通文件和目录可加入数据库；符号链接仍排除。无法确定的 lookup 错误继续保留隐藏，避免仅凭查询失败认定用户已替换。

这只是可见性记账，不删除文件，不按 `.mtp-upload-*` 前缀认定归属。当前传输中的路径仍受原有保护；跨重启归属与回收未实现。ctime 不是内容摘要或可靠所有权凭据：相同 / 粗粒度时间戳下的修改仍可能无法识别，外部并发修改活跃传输的竞争也不在本批验收范围。

五个新增差分场景覆盖替换为文件、目录、符号链接、删除及原 inode 修改。实际使用私有普通文件、inotify、生产 server / database / storage 和 ASan / UBSan；USB 与属性为替身。原 inode 修改场景显式断言 inode 不变、ctime 变化；短暂等待为夹具提供可分辨的时间戳，不代表所有文件系统精度。修正后对象链路 121 项与移动 / 复制 48 项通过；相同测试对旧实现复现文件、目录、原 inode 修改三项不可见，符号链接 / 删除对照通过。每项还检查用户内容保留及后续正常上传。

```bash
# 本批已完成。相关来源、输入与范围不变时复用结果。
python3 tests/mtp_objects_test.py --report logs/mtp-staging-identity-objects-delivery.json
python3 tests/mtp_transfers_test.py --report logs/mtp-staging-identity-transfers-delivery.json
python3 scripts/audit_mtp_staging_identity.py
```

最终先 `installclean` 再 `make -j$(nproc)`；810 份生产来源及六份 profile 绑定。相对 ordinary-reports 候选，ramdisk 仅 MTP 库、构建属性与摘要变化。旧实现副本与报告留本地，公开仓库只保存源码、补丁和结果摘要。没有 ARM64 MTP、真实 USB / Windows 或断电验收；未变的 OTA、触摸等功能复用各自证据。

## 验证边界与未完成项

上述数量对应各次补丁的输入与源码，不表示重跑后仍应得到同一数量。旧实现对照及定向交付审计还依赖本地备份、镜像和历史报告；公开 checkout 不具备全部依赖。

- 临时文件只在所属 storage 生命周期内登记；进程退出、unlink 失败或重启后可能留下残留。跨重启归属及回收尚未实现，不能按通用隐藏前缀删除用户文件。
- 目录日期在 `SendObjectInfo` 阶段应用；子文件上传后显式重发可恢复，见[目录收尾路径](#directory-finalization)。没有整棵树完成通知或自动日期重放，真实客户端是否发送收尾请求仍未验证。
- 主机文件 I/O、线程与数据库执行不等于真实 FunctionFS、Android 挂载 / SELinux、Windows、完整媒体属性或断电持久性验收。
- 取消夹具的 USB peer 会显式丢弃余量；控制请求与 bulk 恢复边界见[控制生命周期](MTP-CONTROL-ADAPTATION.md)。外部并发 rename、父目录替换和真实存储仍有未覆盖边界。
