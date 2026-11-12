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

## 验证边界与未完成项

上述数量对应各次补丁的输入与源码，不表示重跑后仍应得到同一数量。旧实现对照及定向交付审计还依赖本地备份、镜像和历史报告；公开 checkout 不具备全部依赖。

- 临时文件只在所属 storage 生命周期内登记；进程退出、unlink 失败或重启后可能留下残留。跨重启归属及回收尚未实现，不能按通用隐藏前缀删除用户文件。
- 目录日期只在 `SendObjectInfo` 阶段应用。之后创建子文件会更新父目录时间，尚未实现整棵树传输完成后重放目录日期。
- 主机文件 I/O、线程与数据库执行不等于真实 FunctionFS、Android 挂载 / SELinux、Windows、完整媒体属性或断电持久性验收。
- 取消夹具的 USB peer 会显式丢弃余量；控制请求与 bulk 恢复边界见[控制生命周期](MTP-CONTROL-ADAPTATION.md)。外部并发 rename、父目录替换和真实存储仍有未覆盖边界。
