# MTP 控制报文、事务取消与 Reset

本文按主题收录实现与历史验证，旧候选和阶段性未完成描述不代表当前状态。当前状态见[兼容矩阵](../compatibility-matrix.md)，待办见[工作队列](WORK-QUEUE.md)。

本文按控制报文、活动事务匹配和 Reset 会话释放收录实现记录。各阶段的未覆盖项只代表当时边界；后续补充见对应小节，完整 USB 集成状态以工作队列为准。

导航：[分段编辑写入](#partial-edit-write) · [会话文件操作边界](#session-file-boundary) · [控制报文](#修复内容) · [活动事务取消](#transaction-cancel) · [Reset 会话释放](#reset-session) · [事件生命周期](#event-lifecycle) · [bulk 完成队列错误](#bulk-completion-error)。

<a id="command-boundary"></a>
<a id="metadata-data-boundary"></a>

<a id="streaming-data-boundary"></a>

## 上传与分段编辑数据边界（0111）

SendObject和SendPartialObject此前核对数据类型/操作/事务及初始数据量，却未核对container声明总长度。短头或错误头返回后仍继续读取下一条命令，无法保证剩余传输边界。0111共用流式数据头检查：已知payload长度加12字节头，64位运算后饱和为UINT32_MAX；未知长度沿用UINT32_MAX。校验声明长度、类型、操作、事务和初始payload上限，任何协议错误在写文件前终止连接；不发送该事务响应，不解析尾部，并沿原resetSession释放待传输登记/编辑fd。正常传输的I/O失败、取消与Reset保持各自原路径。

生产server/packet/database/storage、真实私有文件/inotify/线程在ASan/UBSan下共229项通过；同测试旧实现新增31项中27项失败。三类接收（新建/覆盖/分段编辑）各九种坏头覆盖长度过短/过长/零、类型/操作/事务错、短头/残留取消errno及超额初始数据，检查原文件保持、没有临时文件或receiveFile调用、下一条删除命令留在peer队列、无错误事务响应和编辑fd关闭。四项控制覆盖空文件、32位长度临界/溢出及未知长度；大/未知长度仅接入显式transport错误，不分配GB数据、不宣称完整大文件USB传输通过。其余既有上传/日期/原子覆盖/编辑/会话/Reset回归一并通过。

本地报告`logs/mtp-stream-objects.json`、`logs/mtp-stream-negative.json`；固定补丁`0111-mtp-stream-data-boundary.patch`，交付审计`python3 scripts/audit_mtp_stream_delivery.py`。关闭连接用于停止不可信边界，不代表主机自动重连或真实端点恢复已验收。没有ARM64 MTP、物理USB/Windows、断电持久性或跨重启临时文件归属/回收验证；不按文件名前缀删除用户数据。

## 元数据 DATA 与命令对应（0104）

通用数据阶段读取后，原主循环没有核对容器类型、操作码、事务号或声明长度便进入处理函数。例如 SET_OBJECT_PROP_VALUE 的重命名请求收到另一个事务的数据，仍会修改文件；SEND_OBJECT_INFO 也会登记错误请求。0104 在四个元数据入口（上述两项、SET_OBJECT_REFERENCES、SET_DEVICE_PROP_VALUE）分发前要求完整 DATA 容器及准确身份，不符则停止连接并执行原 resetSession 清理，不再解析后续排队的命令。正常客户端不会触发此拒绝；错误客户端需要重新建立会话。

MtpDataPacket::read 先清空旧包。真实读错误保持原 errno；成功但少于12字节的读视为 EPROTO，避免继承旧 ECANCELED 后跳回命令解析。长度相等仅用于这里的有界元数据阶段，不对流式 SEND_OBJECT / SEND_PARTIAL_OBJECT 的首块强加全包长度相等。没有新增端点排空逻辑。

现有对象套件198项全部通过；同一套件与旧0103源码的31个新增场景中25项失败。四种元数据操作各覆盖错误类型 / 操作码 / 事务号、短 / 长 / 零声明长度和短头；另有残留取消errno、有效重命名、有效上传三项。新实现要求原文件内容不变、无新文件或上传登记、连接关闭及后续删除命令仍未读；正常控制核对实际写入和下一命令成功。旧短头场景原本可停止，是保留的控制；旧残留取消errno场景则继续执行后续删除。

本地报告 `logs/mtp-data-objects.json`、`logs/mtp-data-negative.json`、`logs/mtp-data-delivery-audit.json`。执行生产主机服务器 / 数据库 / 文件和inotify线程，启用ASan/UBSan；USB、属性、日志、errno为明确替身。无真实USB / Windows / ARM64 MTP / 客户端重连或完整错误传输恢复证明。本批清理后30并发构建，镜像与831份生产来源绑定；具体产物见[交付报告](../simulation-report.md)。

```bash
# 已执行，来源和输入不变时复用。
python3 tests/mtp_objects_test.py --report logs/mtp-data-objects.json
python3 scripts/audit_mtp_data_delivery.py
```

## 命令容器边界（0103）

请求解析原先只检查实际读长为12–32字节且参数对齐，没有核对容器声明长度；错误返回也可能沿用成功read未清除的旧ECANCELED，主循环因此继续读取。0103读取前清空packet与参数计数，要求声明长度等于读长；损坏时再次清空，设置EPROTO。主循环按现有永久错误出口释放会话并关闭连接，不尝试盲目排空未知数据。

现有对象套件扩展7项：声明长度过短 / 过长 / 零、短头、未对齐、六参数，以及短头伴随残留ECANCELED。后面排队一条合法删除，核对连接停止、删除仍未读取、源文件内容保持。当前对象167项通过；保存旧源码同7项中4项失败，三个既有结构拒绝作为通过对照。ASan / UBSan启用；原server / parser / database / storage、普通文件与线程执行，USB / 属性 / 日志与errno故障注入为替身。

本地报告logs/mtp-command-objects.json、logs/mtp-command-negative.json与logs/mtp-command-delivery-audit.json；固定补丁0103。首次候选额外拒绝非COMMAND导致8项既有上传恢复失败，因此撤回类型限制，保留原服务端跳过非COMMAND行为。失败报告与镜像留存initial版本，最终回归167项通过。本项只修正命令长度与错误状态边界，未证明所有损坏上传均排空或恢复。数据阶段身份、完整Reset / 取消 / USB / Windows接续仍按各自边界维护。必要检查通过后收尾，不重复。

<a id="partial-edit-write"></a>

## 分段编辑报文校验、短写与响应计数（0099）

原 `doSendPartialObject` 在检查数据报文身份及长度前就执行 `pwrite`，超出声明长度的数据既会修改文件，又会使剩余无符号长度下溢。原实现忽略短写与零写，不重试 EINTR；成功响应填入剩余长度，通常是 0。部分写入失败时，入站数据还可能残留在响应中。

0099 在首次写入前校验数据类型、操作码、事务 ID、初始数据量及有符号文件偏移范围。短写继续、EINTR 重试，零写和其他错误停止；原接收阶段的取消响应保留。处理后清空入站数据，成功返回请求的总字节数并更新编辑尺寸。

现有对象测试增加 11 项，包含小段、跨接收阶段大段、空段、超长数据、三种报文身份错误，以及短写、EINTR、零写、ENOSPC。测试使用真实主机生产 server / packet / database / storage、普通文件和 ASan / UBSan；仅 transport、属性、日志与指定写入故障为替身。核对响应字节数、无入站数据反射、实际文件内容、拒绝前无写入，以及 EndEdit 的 fd 释放。修正后全套160项通过；相同新增夹具在旧实现中10/11失败，空段控制通过。

本地最终报告为 `logs/mtp-partial-objects.json` 与 `logs/mtp-partial-negative.json`，早期断言版本保存在带 `-initial` 的报告中。补丁为 `0099-mtp-partial-write-validation.patch`；清理构建后824份来源与六profile核对，ramdisk仅MTP库、构建属性及摘要改变。当前镜像及哈希见[交付报告](../simulation-report.md)。

这是就地编辑，失败前已写的内容不回滚，也没有新增 fsync 持久提交保证。畸形报文后的完整端点排空、ARM64 MTP、实际 USB / Windows 和完整取消 / Reset 接续不在本项覆盖范围。

```bash
# 已执行；相关实现与输入未变时复用结果。
python3 tests/mtp_objects_test.py --report logs/mtp-partial-objects.json
python3 scripts/audit_mtp_partial_delivery.py
```

<a id="session-file-boundary"></a>

## 会话文件操作与编辑状态释放（0098）

原请求分派只在部分 handler 内检查会话。尚未 `OpenSession` 或已经 `CloseSession` 后，文件信息、下载、重命名、删除、上传目录、复制、移动及 Android 编辑命令仍可进入实际文件操作；`CloseSession` / 操作码 `ResetDevice` 也只修改会话标志，没有关闭编辑 fd。重新打开会话后，旧编辑状态仍存在。这是协议生命周期缺陷；会话检查不是设备访问认证。

0098 在统一请求入口要求所有已公布的操作具有打开的会话，保留会话前 `GetDeviceInfo` 与 `OpenSession`；未知操作继续返回不支持。此处处理的是 `run()` 已读完数据阶段的命令，不改端点排空 / 取消机制。`CloseSession` 和当前共用该分支的 `ResetDevice` 在关闭通知后，刷新并释放所有编辑对象和 fd；class Reset / 断开沿用同一个编辑释放 helper。存储注册与数据库 handle 保留，已经写入或截断的内容不回滚。

扩展现有对象链路测试，新增 23 项：会话未开 / 已关各十种命令，关闭 / 重置编辑，以及待上传对象关闭后重新上传。使用真实生产 server / packet / database / storage、私有普通文件、inotify、线程及 ASan / UBSan。检查拒绝响应、无数据返回、内容和路径未变、发现及重新打开会话可用；编辑测试实际先截断，再验证 close 精确释放 fd、内容保留、新会话必须重新开始编辑。旧实现 22/23 不满足预期；待上传清理对照通过。修正后对象149项、复制 / 移动48项通过。

本地报告为 `logs/mtp-session-objects.json`、`logs/mtp-session-negative.json` 和 `logs/mtp-session-transfers.json`。USB transport、属性与日志为替身，未证明实际 FunctionFS / Windows / ARM64 MTP、物理设备 reset 或完整 USB 会话。每个响应的事务结束检查保留。`ResetDevice` 仍仅执行现有关闭会话语义，不宣称恢复所有设备属性或重启硬件。

```bash
# 已执行，输入与实现不变时复用结果。
python3 tests/mtp_objects_test.py --report logs/mtp-session-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-session-transfers.json
python3 scripts/audit_mtp_session_delivery.py
```

<a id="bulk-completion-error"></a>

## 原生 bulk 完成队列错误（0082）

原 `MtpFfsHandle::waitEvents` 在 `io_getevents` 返回 `-1` 后只保存 errno，随后仍将负值转换为无符号循环上限，逐项访问未返回的事件数组。一次完成队列报错即可触发栈缓冲区越界；这与此前 interrupt 事件 worker 的错误处理是不同路径。

0082 在错误返回时立即退出，保留原 errno，不解析事件、不将 `-1` 加入完成计数。`TEMP_FAILURE_RETRY` 对 EINTR 的既有重试保持不变。此修正不宣称 EAGAIN 会自动续传，也不更改取消、端点重置或控制器策略。

现有 `tests/run_mtp_transport.py` 增加 `--completion-errors` 和 `--source`。使用原生产 native handle、真实主机 Linux AIO / 管道 / 普通文件，仅对该 bulk context 的 `io_getevents` 注入一次错误。EIO / EAGAIN 两场景在旧实现触发 ASan `stack-buffer-overflow`，修正后安全返回 `-1` 并保持 errno；EINTR 对照真实重试成功、内容一致。测试在错误后关闭并销毁 AIO context，不假称遗留完成记录已恢复为可继续传输。

```bash
python3 tests/run_mtp_transport.py --completion-errors --report logs/mtp-aio-error-current.json
python3 tests/run_mtp_transport.py --report logs/mtp-aio-error-roundtrip.json
python3 scripts/audit_mtp_aio_error.py
```

同一夹具的原生 / 兼容模式往返、文件偏移、容器头、空文件、错误源 fd、ENOSPC、未知长度接收、描述符失败及启停回归通过，启用 ASan / UBSan。旧报告 `logs/mtp-aio-error-negative.json` 保留两项越界和一项 EINTR 通过；原始历史报告不改写。主机属性和日志是替身；管道不是实际 FunctionFS / UDC，本项不验证 Windows 或完整 server / cancel / reset 接续。

固定补丁为 `0082-mtp-aio-completion-error.patch`。最终清理构建 `installclean` + `make -j$(nproc)`，800 份来源、六份 profile；相对 0081 仅 MTP 库、构建属性和 ramdisk 摘要变化。未变的数据库、组件选择与模块结果按原范围复用；没有重跑震动或其他无关功能。镜像及 SHA-256 见[交付报告](../simulation-report.md)。

补丁：[0025-mtp-control-framing.patch](../dtsrc/O1_asic_dual/0025-mtp-control-framing.patch)。当前候选和哈希见[模拟报告](../simulation-report.md)。本阶段不连接手机。

## 修复内容

旧实现要求状态查询至少分配 8 字节，并把 `sizeof(st)`（指针大小）写入回复长度；在 64 位环境，正常状态误报 8 字节，取消状态又加到 12 字节，但实际只分配主机请求的空间。正常的 4 字节查询会失败，8 字节取消查询还可能越界。旧实现也忽略控制传输短读、短写和系统调用失败，不支持的 IN 请求会回复零数据。

现在用固定的小缓冲区生成回复：正常状态 4 字节，取消状态沿用当前 AOSP 的两个 16 位端点参数，共 8 字节，所有字段按小端编码。发送量不超过主机 `wLength`；主机先读头部、发送失败或 SETUP 被替换时，取消状态保留到完整回复发送成功。端点地址读取当前速度的 `FUNCTIONFS_ENDPOINT_DESC` 并验证方向/类型/地址；不用上游可能返回 255 的 `ENDPOINT_REVMAP` 值伪造地址。

严格检查请求类型、方向、接口、保留值以及 Cancel/Reset 长度。不支持的 SETUP 在消费 OUT 数据前，通过 FunctionFS 的反向 ep0 访问返回 STALL。成功发出 STALL 的 `EL2HLT` 不作为服务端退出原因；`EIDRM` 表示主机已替换 SETUP。EINTR 可以重试，短控制报文不能靠下一次 read/write 拼接，永久错误向调用者返回。

Cancel 数据要求 6 字节和 `0x4001` 取消码；Reset 要求零数据并完成零长度确认。这两种有效请求暂时保留原有 `ECANCELED` 中断契约，**没有因此实现交易 ID 匹配或完整会话复位**。

事件读取检查 EOF 和记录长度。批次内继续处理待回应的 SETUP，但后续 ENABLE 不再抹掉早先的取消/错误；DISABLE/UNBIND 优先返回断开，防止旧传输被同批重新启用事件复活。

## 依据

- [USB-IF 原规范及 2007-03-16 勘误](https://usb.org/sites/default/files/usb_still_img10.zip)：§5.2 规定控制请求布局，勘误将 `wIndex` 修正为实际接口号。本机 FunctionFS 描述符使用局部接口 0，内核会把组合设备上的主机接口号反向映射到它。并非要求电脑侧 MTP 永远占接口 0。
- [Linux v6.6 FunctionFS 实现](https://raw.githubusercontent.com/torvalds/linux/v6.6/drivers/usb/gadget/function/f_fs.c)：`ffs_func_setup`、`__ffs_ep0_stall`、ep0 read/write 和 endpoint ioctl 的行为。本地[来源与哈希](../logs/mtp-control-references.json)可复核；不是五版厂商内核等价证明。
- 状态端点参数保留 AOSP 现有的 16 位表示；原规范表 5.2-7 未固定此参数宽度。本阶段没有用 bulk 容器的 32 位参数规定替换控制请求布局，也没有声称完成 Windows 互操作验证。

## 离线验证

[66 项生产代码回放](../logs/mtp-control.json)全部通过；[修改前同组回放](../logs/mtp-control-before.json)有 60 项失败。失败数包含相同缺陷的不同输入，不是 60 个独立硬件问题。测试启用 ASan/UBSan/LSan，直接调用实际 `handleControlRequest` 和 `handleEvent`；仅替换 ep0 read/write、端点 ioctl，模拟一次 SETUP 对应一次数据阶段的内核边界。

| 范围 | 场景 |
|---|---|
| 状态报文 | 0～65535 字节请求、正常/取消回复的逐字节结果、先读头后读完整回复 |
| 发送和端点 | EINTR、短写、EIO、EAGAIN、SETUP 替换、描述符失败/错误方向/零地址/保留位/类型 |
| 请求拒绝 | 错误 recipient/type/index/value、未知及扩展请求、错误方向、Cancel/Reset 长度 |
| OUT 数据 | 正常取消/复位、错误取消码、短读、EINTR、失败、SETUP 替换 |
| 事件批次 | EOF、短记录、错误/暂不可读、挂起恢复、断开→启用、取消→启用、断开与状态查询同批 |

复现命令：

```bash
python3 tests/mtp_control_test.py
python3 tests/mtp_control_test.py --source backups/mtp-control-pre-fix --report logs/mtp-control-before.json
```

第二条是预期失败的负向对照。既有事件、文件传输、对象和移动/复制回归在最终源码上重新执行，报告继续绑定源文件哈希。

## 剩余范围

本阶段只解决报文解析、回复及事件批次错误保留。交易 ID 精确取消、DeviceBusy 时序、Reset 清理服务器会话、bulk AIO 的取消/回收、兼容传输 ep0 调度仍需整合回放。实际控制器的 STALL/CLEAR_FEATURE 时序也不由主机替身证明。

MTP 启停调用者对进程存活/USB 状态的确认、解密后目录发布、覆盖上传原子性及媒体日期仍待完成。完整 MTP 目标保持进行中；真实硬件解密、Windows 枚举与快速唤醒不在本组范围。

<a id="reset-session"></a>

## Reset 与服务器会话释放

2026-11-12。此前Reset和匹配Cancel都只返回ECANCELED，服务器会继续使用旧session。电脑复位后重新OpenSession会收到SESSION_ALREADY_OPEN，未完成的SendObjectInfo与编辑资源也可能保留。

维护补丁`patches/0045-mtp-reset-session.patch`增加独立的Reset信号。FunctionFS只在合法零长度OUT确认成功后置位；失败/被替换的SETUP以及Cancel不置位。信号未被服务器消费时GetDeviceStatus回复4字节DeviceBusy，消费后恢复OK；此前设备取消状态在Reset时清除。此处Busy只覆盖待消费信号，不代表完整硬件复位期间的状态机。

服务器在命令/数据读写与请求处理边界消费信号，由服务器线程释放旧session：停止新通知，撤销尚未完成的上传预留，清空数据/响应状态，重新扫描已打开的编辑对象并关闭其描述符。已写入的编辑字节不回滚，已成功发布的文件不删除。存储和数据库保持注册，下一条需session的请求得到SESSION_NOT_OPEN；重新OpenSession后可继续上传。Reset本身不发送MTP事务响应。原/dev/mtp_usb transport默认不产生用户态Reset信号，内核路径不变。

复位与断线同时返回时保留ESHUTDOWN等终止错误，释放后退出；不能因处理Reset吞掉断线而等待下一请求。首个候选实现曾在新增断线用例失败，已修正并重新installclean构建，首个构建不是交付产物。

离线证据：

- [控制请求80项](../logs/mtp-reset-control.json)：合法Reset信号、消费一次、DeviceBusy→OK、清除旧取消、失败/替换SETUP不发信号、Cancel不发Reset及Reset+DISABLE。旧实现同80项中3项失败。
- [服务器/数据库78项](../logs/mtp-reset-server.json)：真实生产server/packet/database和私有文件。新增10项覆盖空闲、未完成新建/覆盖、data-in/data-out/response、receive/send、编辑及断线；旧代码10项中9项失败，断线场景原来即可退出。恢复会话、抑制旧通知/旧事务响应、保留原文件、清除staging与再次上传均检查。
- [移动复制48项](../logs/mtp-reset-transfers.json)、[native/compat事件62项](../logs/mtp-reset-events.json)、[传输往返](../logs/mtp-reset-transport.json)回归通过。

控制和服务器使用不同USB替身，尚未把真实FunctionFS控制请求、bulk AIO取消/回收和服务器连成同一会话。compat ep0派发、队列中旧事件的撤回、复位后bulk残余包/端点halt清理、真实UDC/Windows仍未验证。server在同步操作返回后才消费信号；没有强行终止已开始的内核/文件I/O。测试启用ASan/UBSan；chroot服务器场景禁用无法访问/proc的LSan。不存在手机命令或实机验证。

候选`recovery-dijun-unified-mtp-reset.img`已按用户要求installclean后`make -j$(nproc)`30并发构建，哈希和最终审计以simulation-report.json及logs/mtp-reset-delivery.json为准。本轮只修正 MTP 软件缺口，全目标保持进行中。

复现：`python3 tests/mtp_control_test.py --report logs/mtp-reset-control.json`、`python3 tests/mtp_objects_test.py --report logs/mtp-reset-server.json`。负向对照使用`--source backups/mtp-reset-pre-fix`与独立报告；服务器对照只选10个reset场景。交付审核入口`python3 scripts/audit_mtp_reset_delivery.py`。

<a id="transaction-cancel"></a>

## 取消请求与活动事务匹配

2026-11-12 后续0045已补充[Reset服务器会话释放](MTP-CONTROL-ADAPTATION.md#reset-session)，当前候选为mtp-reset（046ab9e3…）；下文Reset未实现的描述是本阶段历史边界。真实端点/bulk取消与残余包/旧事件队列仍待整合，不以此次软件检查证明真实USB。

2026-11-12。此前 FunctionFS 验证 Cancel 的 6 字节长度和 `0x4001` 取消码，却忽略其后 4 字节事务 ID，所有合法 Cancel 都以 `ECANCELED` 中断当前操作。旧上传结束后的延迟取消可能打断新上传，空闲时的取消也会被当成传输中断。

维护补丁 `patches/0044-mtp-transaction-cancel.patch` 增加服务器拥有的事务生命周期。解析命令后、进入数据阶段之前调用 `beginTransaction(id)`，作用域结束时调用 `endTransaction()`，覆盖响应、continue、break 和正常完成。FunctionFS 仅对活动 ID 相同的 Cancel 保留中断契约；空闲或 ID 不同的请求消费一次 OUT 数据阶段后正常返回。活动标志与完整 32 位 ID 一起原子读取，ID 0 不与空闲混淆，也不截断高位。旧 `/dev/mtp_usb` transport 的默认生命周期方法为空，其内核控制请求处理不变。

[73 项真实控制请求检查](../logs/mtp-transaction-control.json)通过：原有 66 项加空闲、不同 ID、已结束、下一事务、ID 0、ID 0xffffffff 及高位不匹配。保存的旧源码运行相同测试时有 [5 项失败](../logs/mtp-transaction-control-before.json)，均为不应中断却返回 ECANCELED；旧源码缺少生命周期接口时测试适配器显式不调用该接口，不代替其控制请求实现。

[68 项服务器/数据库检查](../logs/mtp-transaction-server.json)执行真实 `MtpServer::run` 和私有文件操作，在 USB peer 边界记录 begin/end，断言所有返回后的活动状态清零且生命周期成对。另有 [48 项移动/复制](../logs/mtp-transaction-transfers.json)、[62 项 native/compat 事件检查](../logs/mtp-transaction-events.json)及[传输往返](../logs/mtp-transaction-transport.json)通过。主机检查启用 ASan/UBSan；ep0 和服务器 USB peer 是不同测试中的显式边界，没有把它们说成一次真实主机取消会话。

最终镜像为 `recovery-dijun-unified-mtp-transaction.img`，SHA256 `da614695843c1c8f7dd8e1eabc747a65d4e5d755680ba1a0c1dbaeec08ac79b8`。已执行 installclean 和 `make -j$(nproc)`，30 并发构建成功；734 份来源与镜像封装核对，后续同镜像 profile 回放结果见交付审计。与上一 haptics-probe 候选对比，封装检查记录的核心二进制只有 `libtwrpmtp-ffs.so` 改变。

本项不完成 Reset 的服务器会话清理、DeviceBusy 状态时序、bulk AIO 取消回收或 compat ep0 调度。服务器尚未解析出命令时没有活动事务；不把空闲取消处理当成部分命令恢复验证。未验证真实 UDC、Windows 枚举或手机传输，也没有修改震动播放、校准或触摸策略。完整适配目标仍未完成，已解决项以兼容矩阵和用户后续确认为准。

复现：`python3 tests/mtp_control_test.py --report logs/mtp-transaction-control.json`；负向对照增加 `--source backups/mtp-transaction-pre-fix` 和独立报告路径。完整交付核对入口为 `python3 scripts/audit_mtp_transaction_delivery.py`。此次定向审计不替代仍被历史来源漂移阻断的 `audit_unified_delivery.py` 全量审计。

<a id="event-lifecycle"></a>

## 事件请求、退出与重连（0023）

补丁：[0023-mtp-event-lifecycle.patch](../dtsrc/O1_asic_dual/0023-mtp-event-lifecycle.patch)。当前镜像和哈希见[模拟报告](../simulation-report.md)。只运行主机夹具，没有连接手机。

### 问题和实现

此前每个事件创建一个线程，线程直接写 interrupt endpoint；close 先 join 所有线程，再关闭端点。端点停止接收时，写入和 join 都可能一直等待。线程对象也一直积累到关闭，多个写入的提交顺序没有保证。

仅增加 O_NONBLOCK 不足以解决此问题：[Linux v6.6 FunctionFS](https://raw.githubusercontent.com/torvalds/linux/v6.6/drivers/usb/gadget/function/f_fs.c) 的同步请求提交后仍等待完成，异步请求另有取消路径。本地保存了[参考源码](../logs/mtp-events-linux-v6.6-f_fs.c)；这是上游实现参考，不是五版 XRing 厂商内核逐行等价证明。

原生和兼容传输现在共用一个事件工作线程、最多 128 个排队事件和一个正在发送的请求。每个事件复制到独立缓冲区，最长 512 字节；无效长度/空指针拒绝，队列满返回 EAGAIN，关闭后返回 ESHUTDOWN。生产服务端已有错误日志，入队返回成功只表示接受发送，不表示电脑已经收到。

事件端点使用独立的单请求 Linux AIO context，打开为非阻塞；eventfd 同时承载新事件、完成和停止唤醒。依次提交保持顺序，提交或完成阶段的 EINTR/EAGAIN 均有期限地重试；完成通知先排空再等待，避免端点仍堵塞时忙循环。单事件期限为两秒，超时、永久错误或短完成会停止事件工作线程、丢弃未发送队列、撤销 MTP ready；后续发送明确报错。短完成不补发尾部，以免把不完整 USB 事件当作新的容器。

close 先阻止生产者入队并唤醒工作线程；工作线程取消在途请求并回收 AIO context 后才释放缓冲区。取消可能异步完成，或与正常完成竞争，因此依赖 io_destroy 的内核回收语义，不通过 detach、关闭后复用 fd 或提前释放缓冲区逃避等待。正常退出、析构和失败启动均清理资源；start/close 串行化，重复 start 返回 EBUSY。重连只使用新一代队列。

### 主机验证

[62 项最终报告](../logs/mtp-events.json)通过，[同一测试的旧源码结果](../logs/mtp-events-before.json)有 56 项失败；其中顺序/并发场景的旧版失败可能受调度影响，不能把失败数量当作固定缺陷数。每个场景分别运行原生与兼容实现，编译实际 MtpFfsHandle、MtpFfsCompatHandle、描述符及 libasyncio，启用 ASan/UBSan/LSan。

| 范围 | 验证内容 |
|---|---|
| 顺序与所有权 | 64 个连续事件、调用后覆盖原缓冲区、四个并发生产者；逐字节确认事件内容和唯一性 |
| 输入/生命周期 | 零/超大长度、转换为 size_t 的负值、空指针；启动前、关闭后、重复关闭、重复启动 |
| 积压/退出 | 填满 interrupt 管道后关闭或析构；180 次入队验证上限；发送与关闭竞争；重新附加端点后无旧事件 |
| 请求失败 | 端点断开、提交 EINTR/EAGAIN/EIO、完成 EINTR/EAGAIN、短完成、错误完成、两秒期限；堵塞后主机恢复接收 |
| 取消 | 请求保持在途；同步取消、异步取消、完成抢先导致 EINVAL 三种边界，回收后关闭 |
| 启动失败 | 单请求 AIO context 创建失败、端点 fcntl 失败；ready 撤销及资源清理 |

普通事件通过实际主机 AIO/管道传输。管道不能模拟 USB 控制器的挂起请求，因此在途完成、取消竞争和指定错误通过 AIO 边界替身注入；队列、线程、截止时间、生产者锁和缓冲区生命周期执行生产代码。阻塞失败夹具由独立测试进程的五秒期限终止，不终止工作区或构建进程。

第一版事件候选仅重试提交错误，在完成结果返回临时错误时过早停止。[6 项补充负向回放](../logs/mtp-events-completion-before.json)全部失败，修复后纳入本组 62 项。`recovery-dijun-unified-mtp-events.img` 是这一中间版本；该阶段候选为 `recovery-dijun-unified-mtp-events-r2.img`；最新 USB 候选见模拟报告。

原有 [MTP 文件传输](../logs/mtp-transport-regression.json)、[42 项对象/会话](../logs/mtp-objects.json)、[48 项移动/复制](../logs/mtp-transfers.json)在当前源码上通过。对象数据库测试仍使用内存 USB 对端，其通过不能替代本组传输退出检查。

```bash
python3 tests/mtp_events_test.py
python3 tests/mtp_events_test.py --source backups/mtp-events-pre-fix --report logs/mtp-events-before.json
python3 tests/run_mtp_transport.py
```

第二条是负向对照，预期非零；失败场景数不等于独立缺陷数。

### 使用和未完成项

使用入口仍是挂载/存储页面的 MTP 开关，无需选择原生或兼容事件模式。事件发送失败会记录 `MTP interrupt event worker stopped`；队列拥塞或发送失败时不能把缓存目录视为电脑已同步完成，应停止当前传输并重新枚举。

本组验证生产传输层在模拟边界下的退出，不证明实际 UDC 的取消期限。内核驱动若不兑现取消/回收语义，用户态不能据此保证绝对时间上限。Windows 枚举、物理 USB 拔插与控制器行为仍为 U。

Android init/configfs 的属性队列、双 ready 顺序、ready 撤销后的解绑及 ADB 恢复已有后续独立调度夹具；仅看到 ready=0 不证明 USB 配置已切换。USB 控制请求、解密后存储发布、媒体格式/日期和覆盖上传的原子提交也仍未完成。整项 MTP 和总目标保持进行中。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。

后续[控制报文与事件批次](MTP-CONTROL-ADAPTATION.md)补充 66 项验证；实际 UDC、bulk AIO 回收、兼容模式 ep0 调度和取消/复位整合仍未完成。
