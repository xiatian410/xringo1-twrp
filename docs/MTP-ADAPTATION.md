# MTP 传输、启停与存储消息

本文汇总传输实现与管理器生命周期。各节测试和候选属于对应历史阶段，当前状态以[交付报告](../simulation-report.md)为准。

维护补丁：`dtsrc/O1_asic_dual/0008-mtp-ffs-readiness.patch`。
本轮没有连接手机，也没有用 Windows 做物理 USB 枚举。

<a id="send-errors"></a>
## 发送失败传播（0083）

原生 `sendFile` 的磁盘异步读取返回 `-1` 时，旧比较先转为 `size_t`，因而绕过短读判断，可能继续使用无效长度。另一个独立遗漏是原生和兼容发送在最后一批 USB 写入失败后退出循环，错误只在下一次循环内部检查，最终仍返回成功。

固定补丁 `patches/0083-mtp-send-error-propagation.patch` 先检查负读取结果，再比较长度；原生磁盘失败仍请求取消，但返回前恢复磁盘错误，避免取消将其覆盖为 `ECANCELED`。原生 USB 完成短写明确使用 `EIO`，真实负完成保留原错误；两条发送路径均在循环结束后检查尾批写入错误。已排队的磁盘读取仍先等待结束，不提前释放栈上 AIO 请求或缓冲区。失败不代表已发送的字节被撤回。

有限检查复用原传输夹具：

```bash
python3 tests/run_mtp_transport.py --send-errors --report logs/mtp-send-current.json
python3 tests/run_mtp_transport.py --report logs/mtp-send-roundtrip.json
python3 tests/run_mtp_transport.py --completion-errors --report logs/mtp-send-completion-regression.json
python3 scripts/audit_mtp_send_delivery.py
```

原生 / 兼容各覆盖磁盘 EIO、磁盘短读、尾批 USB EIO 和短写，共八项通过；保留的旧源码在同一夹具中六项失败，其中原生磁盘 EIO 达到十秒截止，兼容磁盘两个对照原已通过。原生 / 兼容正常内容往返、偏移、描述符与 ENOSPC 回归及完成队列三项回归通过。每项独立子进程，ASan / UBSan 启用，只操作私有普通文件与管道。

磁盘错误在 worker 的 `pread64` 边界注入；兼容 USB 错误在 `write` 边界注入。原生 USB 在真实 AIO 完成被取出后修改完成记录，不能据此宣称模拟了物理 USB 的部分送达。当前定向数据仅含一批 body，未证明多批流水线取消、完整 server / Reset / FunctionFS 或 Windows 互操作。

清理构建使用 `installclean` 与 `make -j$(nproc)`，801 份生产来源绑定。相对 0082 仅 MTP 库、构建属性和 ramdisk 摘要改变，六份 profile 和其他资源字节不变；交付审计见本地 `logs/mtp-send-delivery.json`。候选和哈希统一见[交付报告](../simulation-report.md)。本项完成后不重复同类单批发送夹具，完整传输生命周期仍留在工作队列中。

<a id="pipeline-first-error"></a>
## 多批发送的首个错误（0084）

0083 后继续核对未覆盖的多批流水线，发现兼容模式在 USB 写入已经失败后，仍需收尾的下一批磁盘读取若再失败，会用磁盘错误覆盖先前 USB 错误。固定补丁 `patches/0084-mtp-pipeline-first-error.patch` 在 `aio_suspend` / `aio_return` 后优先返回已记录的 USB 错误。仍先等待实际读取结束，再释放栈上的 AIO 请求和缓冲区；不提前取消或跳过收尾。原生模式已有相同错误保留逻辑，此次不改变原生实现。

复用传输夹具新增 `--pipeline`：原生 / 兼容各三个场景，包含 7 MiB + 37 字节的内容往返、第一批 body 的 USB EPIPE，以及 USB EPIPE 与下一批磁盘 ENOSPC 重叠。使用 host 读取线程消费管道；错误场景在第二次 `pread64` 的条件变量边界等待实际生产发送路径观察 USB 失败，再完成该磁盘读取。返回时检查两次读取均已收尾且未排第三次；正常多批数据逐字节比较。原生 USB 错误仍在真实 AIO 完成取出后修改完成记录，不等于真实端点取消或物理部分传输。

```bash
python3 tests/run_mtp_transport.py --pipeline --report logs/mtp-pipeline-current.json
python3 tests/run_mtp_transport.py --send-errors --report logs/mtp-pipeline-send-regression.json
python3 scripts/audit_mtp_pipeline_delivery.py
```

六场景通过，修改前同夹具仅 `send-compat-pipeline-dual` 失败，其他五个控制通过；既有八个单批错误必要回归通过。ASan / UBSan 启用，仅普通临时文件 / 管道 / host AIO。补丁按固定基线重建后以 `installclean` 和 `make -j$(nproc)` 构建；802 来源绑定、六份 profile 保持不变。相对 0083 仅 MTP 库、构建属性和摘要变化，审计 `logs/mtp-pipeline-delivery.json` 通过。现行候选见[交付报告](../simulation-report.md)。

这是首错误保留与指定读取重叠调度的收尾，不证明真实 FunctionFS outstanding 请求取消、server 到完整事务 Reset 接续或 Windows。生产修正与这六个场景到此收尾，不新增等价调度来刷通过数量。

## 修正内容

- 原生 AIO 和兼容路径共用描述符提交及端点准备流程。兼容路径此前直接打开端点，缺少描述符启动步骤。
- 关闭或启动失败清除 `sys.usb.ffs.mtp.ready`，描述符/字符串短写不能宣布 ready。
- 初始化并清理 AIO 上下文，重复关闭和失败清理不再使用未初始化的 context。
- 原生接收路径先检查负的异步写入结果，再比较长度；并检查最后一次写入的失败，保留 ENOSPC。
  旧代码把 -1 转为无符号长度，而且可能在最后一次写入失败后走到成功返回。
- 兼容接收未知长度的数据时，只写实际收到的字节。旧代码在短包结尾仍写缓冲区容量，会扩大文件。

设备 init 中的 ADB/MTP 双 ready 条件继续保留，VID/PID 与 FunctionFS 配置未因这些传输修正改变。

## 实际执行的测试

`python3 tests/run_mtp_transport.py` 编译当前 TWRP 的四份 MTP 生产实现及 libasyncio，
用 Linux 管道代替 USB 端点、用独占创建的临时文件代替手机存储。
属性与日志使用替身；文件读写和 AIO 使用实际主机实现，写盘满和描述符错误通过系统调用替身注入。

原生与兼容两条路径均通过 MTP/PTP 描述符、ready 生命周期、255001 字节读写和文件往返、
4096 字节偏移、事务头校验、空文件、无效源 fd、ENOSPC、输入 EOF、输出断开及描述符硬错误/短写。
兼容路径另外通过未知长度最后短包的文件大小及内容检查；这不代表已经传输过真正大于 4 GiB 的文件。

失败回归也已实际执行：HEAD 在 ENOSPC 用例返回成功；早先用例证明 HEAD 关闭后保留 ready；
中间版本仍在未知长度短包用例多写数据。最终工作树通过这些检查。

证据：[通过日志](../logs/mtp-events-transport-run.log)、
[范围和源码哈希](../logs/mtp-transport-regression.json)、
[旧实现 ENOSPC 失败](../logs/mtp-baseline-regression.log)、
[旧实现关闭失败](../logs/mtp-baseline-ready-close.log)、
[兼容短包失败](../logs/mtp-compat-unknown-before.log)。

## 验证边界

这组 S2 测试覆盖传输实现，不等于完整 MTP 对象数据库、媒体存储授权、解密后目录发布或 init/configfs 调度模拟。

后续 [MTP 对象与会话回放](MTP-OBJECTS-ADAPTATION.md)另有 42 项通过，旧实现同组 28 项失败，运行实际请求分发、数据包、数据库与目录监视。再后续 [移动/复制与重建](MTP-OBJECTS-ADAPTATION.md#object-transfers)完成 48 项回放；后续 [事件生命周期](MTP-CONTROL-ADAPTATION.md#event-lifecycle)有 62 项通过；目录发布与 USB 控制请求仍待验收；configfs 时序见后续独立回放，不能合并宣称全部 MTP 已适配。
管道没有 FunctionFS 的 endpoint ioctl，因此相应用例走包长/分配后备路径，日志中的 ioctl 失败是夹具预期。
USB 物理枚举、Windows 驱动识别、控制器取消传输行为和手机存储性能保持 U。
最新构建和镜像核对状态以 [模拟报告](../simulation-report.md) 为准。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。


最新上传接收修正见[MTP原子发布](MTP-ATOMIC-UPLOAD.md)：失败保留旧目标，完整接收后rename；68项host对象检查/48项传输回归通过，进程退出残留/目标断电/物理USB仍未完成。当前产物以simulation-report.json为准，旧审计仅对应历史源码和镜像。

## 启停与存储消息

本轮执行实际管理器函数、实际 ForkServer/Start、实际存储接收循环，使用主机进程、线程、socket、信号与 wait；Android 属性/USB 配置完成和存储对象接收端使用替身。没有连接手机或执行真实 UDC。

[调用层报告](../logs/mtp-caller.json) 40 项通过，同一测试在[保留旧源码](../logs/mtp-caller-before.json)有 24 项失败；[接收端报告](../logs/mtp-receiver.json) 11 项通过，[旧源码](../logs/mtp-receiver-before.json)有 4 项失败。失败数量是用例数，不等于独立缺陷数。ASan/UBSan 覆盖主机执行。

启动现在核对受管理子进程、USB 请求、实际配置状态和 FunctionFS ready，八秒内未确认则返回失败并请求恢复 ADB。重复启动只复用仍存活且已确认的实例。旧式 android_usb 路径保留配置状态检查，不要求其不提供的 FunctionFS ready。

关闭先撤销界面状态，确认子进程归属后发送 SIGKILL，最多等待两秒；无法确认归属或退出超时保留 PID，禁止新建重叠实例。ADB 配置最多等待五秒确认，属性失败和配置错误向调用者返回失败。此期限只约束相应等待循环；挂载、执行器排队和调度仍不属于严格的端到端期限。

状态读取使用 try-lock 和非阻塞子进程观察，不在 GUI 线程等待启动/关闭；它核对当前进程与 USB 状态，属于瞬时快照。管理器按操作事务锁→MTP 锁的顺序串行修改，进程工具要求本管理器是该子进程的唯一回收者；不能把此实现当作支持任意外部 reaper 的 PID 句柄。

存储消息使用 SOCK_SEQPACKET，send 带 MSG_NOSIGNAL/MSG_DONTWAIT，避免接收端退出杀死 recovery 或满队列阻塞。短发送和失败返回 false。接收端重试 EINTR，拒绝长度错误及未终止的字符串。消息发送成功只表示入队，不表示数据库已接纳；队列重试、AddAll 每项结果汇总、解密后发布确认仍待补。

子进程定期检查 recovery 父进程关系，父进程退出后主动退出。没有使用 PR_SET_PDEATHSIG：Linux 将其绑定到创建线程的退出，而 MTP 可能由临时操作线程启动。真实线程回放已覆盖“启动线程结束后 MTP 仍存活”，子收割器夹具覆盖实际父进程退出。检测周期 250 ms，实际调度可能延后。

[补丁](../dtsrc/O1_asic_dual/patches/0026-mtp-caller-lifecycle.patch)可从固定源码基线重建。[当前模拟报告](../simulation-report.md)绑定镜像、构建来源与 53 项二进制策略检查，含 recovery 的 socket 与 fork/signal 权限。没有修改 recovery 域权限来掩盖错误。

复查命令：

```bash
python3 tests/mtp_caller_test.py
python3 tests/mtp_receiver_test.py
python3 tests/mtp_caller_test.py --source backups/mtp-caller-pre-fix --report logs/mtp-caller-before.json
python3 tests/mtp_receiver_test.py --source backups/mtp-caller-pre-fix --report logs/mtp-receiver-before.json
```

后两条是负向对照，预期返回非零。测试超时清理其独立进程组，避免故障夹具遗留子进程。

尚未完成完整 GUI/挂载/init/解密后发布端到端联调；临时工作线程与真正进程退出的测试不代表整套 fork 后 C++ 库在任意并发负载下无锁风险。完整交易取消、会话 reset、compat ep0 调度、bulk AIO drain、真实 USB/Windows 枚举仍保持独立未完成项。TEE 与唤醒延迟不由本组用例证明。
