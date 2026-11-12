# USB configfs 切换与服务交接

实现位于 [usb_config.cpp](../dtsrc/O1_asic_dual/profiles/runtime/usb_config.cpp)、[设备 init](../dtsrc/O1_asic_dual/recovery/root/init.recovery.usb.rc) 和 [0024 补丁](../dtsrc/O1_asic_dual/0024-usb-configfs-reconciliation.patch)。当前产物及哈希见[模拟报告](../simulation-report.md)。本轮只运行主机回放。

## 修改内容

原先多个属性触发器分别执行绑定指令，双 ready、重复属性事件或快速切换会重复创建链接、重复绑定控制器；init 某条指令失败后仍执行后面的 state 发布。旧设备触发器也没有处理 MTP ready 撤销后的实际解绑和 ADB 恢复。

现在 dijun 由独立的 `dijun-usb-config` 程序负责切换。Android init 的同步 exec 串行执行它；每次重新读取当前请求，避免沿用队列中已过时的请求。解绑、属性写入、链接修改、绑定和读回均检查结果，只有实际配置匹配且 ready/请求未变化才发布成功状态。重复 ready 不重复绑定。函数链接清理覆盖配置目录的所有符号链接，拒绝未知控制器、配置及无效 USB 标识。

ADB 和 fastbootd 共享 ready 属性，切换时必须先停止旧服务并观察 stopped，再启动新服务并等待新描述符。`sys.usb.state=none` 只有在解绑且服务停止后确认；正在切换时为 `configuring`，失败为 `error`，具体阶段记录在 `sys.recovery.usb.error`。MTP+ADB 模式下 MTP ready 丢失会尝试恢复 ADB，ready 返回后恢复组合模式；任何写入或读回失败都不报配置成功。

旁加载由 recovery 自己 fork/exec `minadbd`。原调用方先等待 none，再启动 minadbd，最后请求 sideload；它的 ready 可能早于请求到达。helper 保留这种提前就绪，不启动普通 adbd，也不负责启动或终止 minadbd。没有经过正常服务停止交接的 sideload 请求会拒绝。旁加载调用方的完整安装/退出流程仍须另行模拟。

ADB/旁加载沿用 `ro.recovery.usb.vid` 和 `ro.recovery.usb.adb.pid`，本构建为 `18d1:d001`；fastbootd 沿用 `18d1:4ee0`。MTP 保留设备配置中的 `2717:ff40`，MTP+ADB 为 `2717:ff48`。恢复 ADB 时同时恢复其标识，不沿用 MTP 标识。

程序静态链接，沿用平台 recovery 的 rootfs 文件标签和显式进程域切换，避免依赖尚未重标记的 ramdisk 共享库，也不要求 init 改写执行文件标签。程序在专用、enforcing 的 `dijun_usb` 域执行，仅授予 configfs、所需属性和 adbd/fastbootd 的控制权限。没有借用 init 域执行任意程序。其他设备的通用 init 路径通过默认 managed=0 保留；dijun 在 init 阶段选择 managed=1。

## 模拟范围

[最终回放](../logs/usb-init.json) 42 项通过；[旧配置对照](../logs/usb-init-before.json) 使用同一测试代码，33 项失败。失败数不是独立缺陷数，也不是手机测试结果。

夹具编译实际 AOSP tokenizer、parser、import、Action/ActionManager、属性条件匹配和 ExpandProps，载入实际共同/设备 rc，执行实际 helper 状态机。configfs、属性存储及服务启动/停止完成由主机边界替身提供；未执行完整 Android init 引导。测试包含：

- 双 ready 的两种顺序、同时到达、重复事件、快速 none/MTP/ADB/fastboot 切换。
- MTP/ADB ready 丢失与恢复、服务死亡/restarting、延迟停止、启动/停止请求失败。
- 属性、链接、解绑、绑定、读回及状态发布失败；额外链接清理、切换期间请求或 ready 改变。
- ADB/fastboot/旁加载标识恢复、属性十六进制格式、缺失或溢出的标识拒绝。
- none 确认必须等待服务停止；minadbd 提前 ready、ready 丢失、返回普通 ADB及拒绝繁忙交接。
- 没有导入 dijun 管理器的通用 ADB 路径。

configfs 边界依据 [Android common android15-6.6](https://android.googlesource.com/kernel/common/+/refs/heads/android15-6.6/drivers/usb/gadget/configfs.c) 和 [Linux v6.6](https://raw.githubusercontent.com/torvalds/linux/v6.6/drivers/usb/gadget/configfs.c) 核对。Android 接受 `none` 解绑，上游没有这个别名；新程序写入换行，两者均将其归一为空控制器名称。零字节写入不是解绑，已经解绑再次请求会返回 ENODEV，因此程序先读回状态。属性写入和解除函数链接并非一律 EBUSY，夹具没有增加这种假设。两份参考的哈希见[来源记录](../logs/usb-configfs-kernel-references.json)。[Android 参考快照](../logs/usb-init-android15-6.6-configfs.c)、[上游快照](../logs/usb-init-linux-v6.6-configfs.c)仅为行为参考，不是五份厂商内核源码等价证明。

```bash
python3 tests/usb_init_test.py
python3 tests/usb_init_test.py --baseline --report logs/usb-init-before.json
```

第二条为负向对照，预期退出非零。旧配置未调用新 helper，虽然夹具仍将它链接进测试程序。可选 logd/ldconfig/mksh import 在夹具中为空，非 USB 指令和真实 FunctionFS 描述符传输不在本组验证范围。

USB 阶段 r2 镜像的 [45 项二进制策略检查](../logs/usb-configfs-r2-helper-policy.json)通过：验证 rootfs 执行入口、专用域保持 enforcing、所需 configfs/属性访问，同时拒绝任意服务控制、关机属性、应用数据读取、原始块写入、对 recovery 发 SIGKILL 和 rootfs 内不切换域的执行。镜像中的[六份 init 配置](../logs/usb-configfs-r2-init-verification.json)通过语法和服务门控检查。

## 使用与剩余限制

仍使用 MTP 开关、ADB、旁加载和 fastbootd 的现有入口，不需要手动运行 helper。`sys.usb.state` 是检查后的配置结果；界面的开关状态仍有独立调用者确认工作待完成，不能仅看开关亮起判断 Windows 已枚举成功。

本组没有证明真实 UDC 的解绑/取消耗时，没有连接 Windows 或手机。USB 控制请求、MTP 调用者的子进程退出和状态等待、解密后存储发布、完整媒体属性及覆盖上传原子提交仍未完成。USB/MTP 总体保持进行中。

第一份 `recovery-dijun-unified-usb-configfs.img` 通过编译和功能夹具，但镜像策略检查发现 init 无权重标记新执行文件类型，不能作为可用候选。该结果保存在[失败记录](../logs/usb-configfs-helper-policy-before-rootfs.log)；后续 r2 改用平台 recovery 的 rootfs 显式域切换，最终状态以模拟报告为准。策略没有改成 permissive，也没有放宽平台 neverallow。

后续[控制报文与事件批次修复](MTP-CONTROL-ADAPTATION.md)通过 66 项主机回放；其边界不包含完整取消/复位和调用者确认。当前镜像的策略/配置验证见模拟报告。
