# MTP 控制报文与 FunctionFS 事件批处理

2026-11-12 后续0045已补充[Reset服务器会话释放](MTP-RESET-SESSION.md)，当前候选为mtp-reset（046ab9e3…）；下文Reset未实现的描述是本阶段历史边界。真实端点/bulk取消与残余包/旧事件队列仍待整合，不以此次软件检查证明真实USB。

后续0044已加入[活动事务匹配](MTP-TRANSACTION-CANCEL.md)：当前73项控制检查覆盖空闲/不同ID/结束后Cancel不再中断，原有66项为本阶段历史结果。服务器生命周期在独立真实server/USB peer检查中覆盖；Reset、DeviceBusy、bulk取消及compat ep0仍待整合，未验证真实USB。

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

MTP 启停调用者对进程存活/USB 状态的确认、解密后目录发布、覆盖上传原子性及媒体日期仍待完成。目标保持进行中；震动、真实硬件解密、Windows 枚举与快速唤醒延迟保持硬件未验证。
