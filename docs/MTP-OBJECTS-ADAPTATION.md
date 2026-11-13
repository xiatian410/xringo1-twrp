# MTP 对象数据库与会话适配

本文按主题收录实现与历史验证，旧候选和阶段性未完成描述不代表当前状态。当前状态见[兼容矩阵](../compatibility-matrix.md)，待办见[工作队列](WORK-QUEUE.md)。

日期：2026-11-11。补丁：[0021-mtp-object-lifecycle.patch](../dtsrc/O1_asic_dual/0021-mtp-object-lifecycle.patch)。当前候选和哈希见[模拟报告](../simulation-report.md)。本组只运行主机夹具，没有连接手机。

## 修正内容

| 原行为 | 当前行为 |
|---|---|
| 移除存储只删除 server 列表项，数据库与目录监视仍保留 | 同步撤销数据库、对象句柄和监视线程；空存储返回空指针，重复 ID 和无效根目录不发布 |
| 全存储查询只返回首个存储；递归属性查询遗漏尚未展开的子目录 | 合并各存储结果，递归加载子目录，落实目录/普通文件格式过滤；depth=1 包含对象自身和直接子项 |
| 删除前先删除数据库记录，文件系统删除失败后原文件失去句柄 | 先验证句柄，仅在删除成功后移除记录 |
| 重命名可覆盖已有目标，两个句柄随后指向同一文件 | 使用 renameat2(RENAME_NOREPLACE) 拒绝冲突；拒绝根目录、空名、点目录和带路径分隔符的名字 |
| USB 断线后会话状态和待上传对象保留 | 清理会话、未完成上传预约和编辑状态，使新会话能够重新打开 |
| 多个目录监视线程复用同一个事件包 | 每次创建独立事件包，并串行发送；会话开关和事务编号使用原子状态 |
| 上传初始数据短写、中断、长度不符或同步失败可能误报成功 | 累计短写、重试 EINTR，检查包类型/操作/事务、实际文件长度及 fsync；失败进入清理路径 |
| 根目录上传绕过父路径核对；目录创建失败保留预约节点 | 所有父句柄都核对路径；文件和目录失败后移除不存在对象的预约 |
| 初次扫描及目录事件把符号链接、FIFO 等当作普通对象 | 只发布目录和普通文件；部分读取偏移超过 EOF 时拒绝，避免剩余长度下溢 |

枚举、格式和深度语义对照本地 AOSP `frameworks/base/media/java/android/mtp/MtpStorageManager.java` 与 `MtpDatabase.java`；两份参考文件哈希记录在测试报告。普通文件当前仍使用通用格式，不据扩展名推断全部媒体类型。

## 实际执行与结果

[测试驱动](../tests/mtp_objects_test.py)编译 14 份生产 C++ 源码，包含 MtpServer 请求分发、数据包编解码、TwrpMtpDatabase 和 TwrpMtpStorage。每个场景在独立临时 chroot 中使用真实文件、inotify 和线程；USB 收发、属性和 Android 日志接口由主机替身提供。

[42 项最终报告](../logs/mtp-objects.json)全部通过，[同一测试的旧源码对照](../logs/mtp-objects-before.json)有 28 项失败。失败数包含同一缺陷的多个场景，不能解读为 28 个独立硬件故障。

- 枚举：根目录、递归、多个存储、数量、属性递归、格式过滤和 depth=1。
- 文件往返：上传下载、60,000 字节跨初始包与后续数据传输、目录上传、部分读取越界。
- 失败处理：放弃上传、断线、ENOSPC、声明长度不符、后端假成功短文件、短写、EINTR、零写、fsync 失败、mkdir 失败。
- 生命周期：成功/失败删除、成功/冲突重命名、根目录和点名称拒绝、父目录不匹配、移除/重新添加存储、空存储、重复 ID、根目录缺失、新会话重连。
- 外部变化：新建/修改/删除、子目录删除、初次及后续发现符号链接/FIFO、6 个线程共 3,000 条对象事件的完整性。

ASan/UBSan 启用；LSan 因私有 chroot 中无法检查 `/proc` 而关闭，本组不证明无内存泄漏。Android ARM64 编译与镜像内共享库一致性另行检查，主机通过不替代目标平台编译。首次目标编译发现有符号长度比较警告，已在确认长度非负后转换为 size_t，保留[失败日志](../logs/build-unified-mtp-objects-sign-compare-failure.log)。

复现：

```bash
python3 tests/mtp_objects_test.py
python3 tests/mtp_objects_test.py --source backups/mtp-objects-pre-fix --report logs/mtp-objects-before.json
```

第二条为负向对照，预期非零。写入只发生在本次创建的私有目录内。

## 使用与边界

内部媒体完成解密和挂载后，从挂载/存储页面启用 MTP；未解密的媒体不能作为可访问目录发布。实际入口与其他功能见[使用说明](../FEATURE-USAGE.md)，此前 native/compat FunctionFS 传输验证见[MTP 传输适配](MTP-ADAPTATION.md)。

本组没有执行 Android init/configfs、物理 USB 或 Windows 枚举。内存 USB 对端在发送时不阻塞，不能证明真实事件端点阻塞时的移除/关闭一定有界；后续 [事件生命周期](MTP-CONTROL-ADAPTATION.md#event-lifecycle)已提供独立生产传输回放，实际 UDC 仍为 U。解密后目录发布、取消事件及 ADB 恢复也不能仅由此组会话测试宣称完成。

后续 [0022 转移与重建](MTP-OBJECTS-ADAPTATION.md#object-transfers)已实现 MoveObject/CopyObject/rescan、inotify 溢出与根目录变化，48 项通过。本页 42 项仍在新代码上通过。剩余媒体格式/日期属性、解密后发布与撤销、USB 控制请求待补；configfs 双 ready 另有后续独立回放；事件线程退出已有独立回放。覆盖已有同名文件时尚未采用临时文件原子提交，上传失败可能影响旧内容；发现之后的路径被外部替换为符号链接也仍存在竞态。当前排除符号链接不等于已完成所有路径约束。整项 MTP 目标保持未完成。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。

后续0039补齐上传日期解析：原42项加4项日期落盘共46项通过；直接MtpUtils80项与转移48项另记，见[MTP日期范围](MTP-ATOMIC-UPLOAD.md#upload-datetime)。原子上传覆盖、输出日期、完整元数据及现场USB仍未完成。

## 文件格式与筛选一致性（0071）

数据库声明支持多种媒体格式，但此前所有普通文件在对象信息、属性和枚举中一律为 `UNDEFINED`，按 JPEG / PNG / MP3 等查询会得到空列表。0071 在 storage 内使用同一个扩展名映射，接通 `GetObjectInfo`、`GetObjectFilePath`、`ObjectFormat` 属性、对象列表与属性列表的格式过滤；重命名立即更新缓存格式属性。

映射覆盖已声明支持的常见文本、图片、音频、视频和播放列表扩展名；最后一个扩展名使用 ASCII 大小写折叠。目录始终为 `ASSOCIATION`。无扩展名、仅 `.jpg` 这样的隐藏名、末尾点及未知扩展名保持 `UNDEFINED`。上传完成后按最终文件名识别，不采信主机任意传入的格式码。Android 原始 `MtpStorageManager.getFormat()` 也以 MediaFile 的文件名识别作为后备；Recovery 使用明确的小型表，不引入 MediaProvider。

这是文件名分类，不验证内容、解码能力或真实 MIME，也没有提取 EXIF、尺寸、时长、艺术家和封面。扩展名不能证明媒体内容有效；创建日期和媒体属性全流程仍未完成。

现有对象链路新增四个场景：33 种扩展名/边界与带扩展名目录、两次跨格式重命名、上传后识别、跨目录格式筛选及计数。逐项检查真实 MTP 包响应、数据库属性和路径格式；旧实现四场景均失败。当前对象链路 114 项与复制/移动 48 项通过，ASan/UBSan 启用。原 server/database/storage、真实私有文件、inotify 与线程执行；USB、属性和日志为替身，未执行 ARM64 MTP、真实 USB / Windows。

```bash
python3 tests/mtp_objects_test.py --report logs/mtp-format-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-format-transfers.json
# 需本地旧源码；预期四项失败：
python3 tests/mtp_objects_test.py --source backups/mtp-format-pre-fix \
  --cases media-format-inventory media-format-rename media-format-upload media-format-filter \
  --report logs/mtp-format-before.json
python3 scripts/audit_mtp_format_delivery.py
```

首次测试把两字节 UINT16 响应误用四字节读取，报告保留在本地 `logs/mtp-format-first-attempt.json`；修正测试包读取后再执行，没有将夹具错误计为生产缺陷。

清理构建候选 `recovery-dijun-unified-mtp-format.img`，SHA-256 `117d67ba178c1a66739571436287d7a01e975fea169fddb7e28706d55bada9fe`，786 项生产来源及六份 profile。与 tool-console 候选相比仅 MTP 库、构建属性与 ramdisk 摘要变化；GUI / updater / profile 字节不变，复用对应既有证据。

<a id="object-transfers"></a>

## 移动、复制与目录重建（0022）

日期：2026-11-11。补丁：[0022-mtp-transfer-reconciliation.patch](../dtsrc/O1_asic_dual/0022-mtp-transfer-reconciliation.patch)。当前镜像、哈希与分层验收见[模拟报告](../simulation-report.md)。本组没有连接手机或执行物理 USB 操作。

### 实现变化

原数据库的移动、复制和 rescan 都返回未实现。CopyObject 的 begin 返回类型是 16 位响应码，却被当作 32 位对象句柄；end 还把非零响应码隐式转为成功布尔值。现在数据库提供一个带独立结果句柄的 `transferObject` 操作，服务端直接返回其结果，消除拆分回调的状态歧义。

操作期间同时锁住源和目标存储树，阻止 inotify 把移动中的对象先删除、再分配新句柄。移动保留顶层与已缓存子项的句柄及持久 UID，更新存储 ID、父目录、属性和监视路径；复制分配新句柄。重复目标、无效父目录、跨存储父句柄、把目录移入自身子树等请求均拒绝。

文件操作用目录 fd 锚定递归访问，父路径和源文件使用 `O_NOFOLLOW`，不沿符号链接读取外部文件。复制通过排他创建拒绝覆盖，累计 sendfile 短传输，重试 EINTR，零进展、ENOSPC、文件长度/修改时间变化、fsync 与 close 错误均返回失败。目录递归检查每个普通文件的大小上限，保留修改时间，文件权限按 MTP 的媒体访问常量设置；这不是备份权限/xattr 复制实现。

移动优先使用 `renameat2(RENAME_NOREPLACE)`；遇到 EXDEV 才复制并同步目标，然后删除源。源删除失败时保留完整目标副本并返回失败，重建两个目录以反映实际文件状态。源目录可能已经部分删除，不能承诺回滚；用户应检查两边内容再继续。目标已完成但父目录 fsync 失败时也返回失败，完整副本可能已经可见。

`rescanFile` 按已知对象路径刷新属性，拒绝把不相关路径绑定到已有句柄。队列溢出会重读已缓存目录，移除消失或类型改变的项、发现新增项并保持未变化的句柄；只为实际变化生成事件。根目录移走/删除后清空旧项，路径恢复后可重新枚举和监视。对象信息和路径查询不再把消失或被替换成符号链接的文件报告成零字节普通文件。

### 验证与复现

[48 项报告](../logs/mtp-transfers.json)通过；[旧源码同组对照](../logs/mtp-transfers-before.json)有 36 项失败。测试使用实际 MTP server、packet、database、storage 和文件工具，独立 chroot 内真实文件、inotify、线程与 fd；仅 USB 对端、日志/属性和指定故障系统调用是替身。ASan/UBSan 启用，LSan 因 chroot 内无法访问 `/proc` 而关闭。

| 范围 | 本组覆盖 |
|---|---|
| 复制与内容 | 单文件、目录、空目录、同存储子目录；逐字节核对内容，原件保留、新句柄可查询 |
| 移动 | 同目录不变、同存储、两个存储、模拟 EXDEV、目录子项句柄保持、移动后继续观察新增文件、修改后持久 UID 保持 |
| 拒绝与失败 | 重名文件/目录、父目录/存储/对象无效、根对象、目录循环、符号链接/FIFO、父路径被替换、文件大小上限 |
| 复制 I/O | sendfile 短传输/EINTR/零返回/ENOSPC、目录中途失败、文件 fsync/close、目标父目录 fsync 失败 |
| 移动失败 | rename 拒绝、源文件删除失败、源目录部分删除失败；完整副本仍可访问，错误不伪装成功 |
| 重建 | rescan 元数据/文件消失/路径不匹配；注入 IN_Q_OVERFLOW 后核对根与已缓存子目录；根目录删除及重建 |

EXDEV 通过 syscall 包装注入，因为夹具源与目标位于同一个主机文件系统；后续复制、同步、删除和数据库重建执行真实代码。溢出测试先消费并丢弃指定 inotify 事件，再向生产事件处理器注入一个真实格式的 IN_Q_OVERFLOW 记录，不靠修改数据库来制造通过。对照中的失败数量不代表独立缺陷数量。

原有[42 项对象用例](../logs/mtp-objects.json)在当前代码上再次通过，同一新版测试驱动的[旧对象实现](../logs/mtp-objects-before.json)仍有 28 项失败。其删除故障注入同时覆盖 unlink 和新的 unlinkat，避免系统调用变化后原测试失去作用。

```bash
python3 tests/mtp_transfers_test.py
python3 tests/mtp_transfers_test.py --source backups/mtp-transfers-pre-fix --report logs/mtp-transfers-before.json
python3 tests/mtp_objects_test.py
```

第二条预期非零。所有写入限制在驱动创建的私有目录，不使用主机物理盘或手机分区。

### 使用和仍需验收的边界

从[挂载/存储页面启用 MTP](../FEATURE-USAGE.md)，在电脑文件管理器中复制、移动已解密并发布的媒体文件。目标已有同名项时本实现拒绝覆盖；应先改名或明确处理旧文件。复制成功有新对象句柄，移动成功保留原对象身份。

这组不验证 Windows 枚举、真实 USB 取消、Android configfs/双 ready 时序或解密后目录发布。后续 [0023 事件生命周期](MTP-CONTROL-ADAPTATION.md#event-lifecycle)改为单工作线程、有限队列及可取消 AIO，62 项主机回放通过；实际 UDC 仍未验证；configfs 调度另有后续独立回放。前述树锁保护只覆盖本进程的观察者，不等于外部程序无法在操作中修改路径；目录内容并发变化、源部分删除与断电不提供事务回滚。普通文件格式仍为通用类型，完整媒体属性/日期协议和上传覆盖的原子提交另列待办。

原厂内核、MiTEE、UFS、物理电机与真实触摸唤醒均未由这些 MTP 用例验证。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。
