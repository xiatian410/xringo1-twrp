# MTP 离线修正与传输验证

维护补丁：`dtsrc/O1_asic_dual/0008-mtp-ffs-readiness.patch`。
本轮没有连接手机，也没有用 Windows 做物理 USB 枚举。

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

后续 [MTP 对象与会话回放](MTP-OBJECTS-ADAPTATION.md)另有 42 项通过，旧实现同组 28 项失败，运行实际请求分发、数据包、数据库与目录监视。再后续 [移动/复制与重建](MTP-TRANSFERS-ADAPTATION.md)完成 48 项回放；后续 [事件生命周期](MTP-EVENTS-ADAPTATION.md)有 62 项通过；目录发布与 USB 控制请求仍待验收；configfs 时序见后续独立回放，不能合并宣称全部 MTP 已适配。
管道没有 FunctionFS 的 endpoint ioctl，因此相应用例走包长/分配后备路径，日志中的 ioctl 失败是夹具预期。
USB 物理枚举、Windows 驱动识别、控制器取消传输行为和手机存储性能保持 U。
最新构建和镜像核对状态以 [模拟报告](../simulation-report.md) 为准。

后续 [USB configfs 与服务交接](USB-CONFIGFS-ADAPTATION.md)使用真实 init 调度和生产 helper 完成 42 项回放；实际 USB 控制器、Windows、完整旁加载和 MTP 调用者确认仍不由此证明。


最新上传接收修正见[MTP原子发布](MTP-ATOMIC-UPLOAD.md)：失败保留旧目标，完整接收后rename；68项host对象检查/48项传输回归通过，进程退出残留/目标断电/物理USB仍未完成。当前产物以simulation-report.json为准，旧审计仅对应历史源码和镜像。
