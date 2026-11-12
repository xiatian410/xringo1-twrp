> 历史技术记录：OS4 震动现已由用户确认正常，已解决，不属于当前排查或例行检查。以下旧状态只对应当时的记录。当前进度见 [工作队列](WORK-QUEUE.md)。

# 原厂震动注册、效果生命周期与 DTBO 离线复核

2026-11-11，六份固件的原厂 ARM64 函数完成 **90 项模拟**，原始 DTBO 完成 **48 次合并检查**。报告分别为[生命周期 JSON](../logs/haptics-lifecycle-emulation.json)、[执行日志](../logs/haptics-lifecycle-emulation.log)、[DTBO JSON](../logs/haptics-devicetree-audit.json)、[合并日志](../logs/haptics-devicetree-audit.log)。六份模块的原始 `cs40l26_input_init` 均观测到相同 input 名称、PERIODIC/CUSTOM/SINE/GAIN 能力、96 个效果槽及四个非空回调地址。该契约已写入逐样本报告并由交付审计核验。本轮没有修改生产驱动源码、重编译 recovery 或访问手机；物理震动仍为 U。

## 原始指令执行范围

[生命周期模拟器](../tests/haptics_lifecycle_emulation.py)复用[原厂 ARM64 模拟器](../tests/haptics_driver_emulation.py)，绑定五份唯一模块哈希。执行原厂 `cs40l26_input_init`、`cs40l26_upload_effect`、`cs40l26_upload_worker`、`cs40l26_playback_effect`、`cs40l26_erase_effect` 和 `cs40l26_erase_worker`。输入来自当前生产 FF 捕获器的 80 ms 正弦请求，效果 ID 为 input core 夹具分配的 7。

`flush_work` 边界暂停回调、保存 CPU 上下文，在独立栈执行对应原厂 worker，再恢复回调。因此覆盖回调读取 worker 结果的路径；并未运行真实内核调度器。输入核心、内存分配、PM、DSP 符号/寄存器、完成事件均有明确替身。start/stop worker 和 IRQ 未执行，播放状态由夹具注入；等待值被记录，不消耗对应墙钟时间。不能把本测试描述为完整 probe、真实并发队列或物理播放验证。

| 范围 | 数量 | 观察结果 |
|---|---:|---|
| input 注册与四种失败 | 30 | 名称 `cs40l26_input`、PERIODIC/CUSTOM/SINE/GAIN、96 个效果容量、四个 FF 回调指针；分配/FF 创建/设备注册/sysfs 失败返回值正确 |
| 每样本连续 12 轮上传→播放回调→擦除 | 6 | 共 72 轮，效果链表归空、五个正弦槽恢复空闲、分配记录释放 |
| 活跃效果擦除：完成/超时 | 12 | 80 ms 请求等待上限为 580 ms；完成后释放槽，超时返回 `-ETIME`（-62）并保留效果 |
| 第 1/2/3 次 DSP 写入失败 | 18 | 上层得到 `-EIO`，没有残留效果链表记录，已分配记录释放 |
| PM 失败后的结果字段 | 12 | 上传/擦除 worker 提前退出可能保留原有 0 结果，见下文 |
| 两份 OS4 组合模块初始化/探测包装 | 12 | 子初始化失败与 Cirrus 探测失败不一定让外层模块加载失败 |

六份样本的 input contract 字段是执行各自原始 ELF 函数的观察值，不是从模块名推断。它只确认驱动交给 Linux input core 的注册请求；测试没有执行真实 input core、`EVIOCGEFFECTS`/`EVIOCGBIT(EV_FF)` 查询、节点权限检查、播放 IRQ 或电机。Recovery 的运行时 `cs40l26_input` 名称探测也只证明节点出现，不能替代这些检查。

这里的一项可包含多轮断言；90 是报告中的场景数量，72 轮不另加进用例数。

## 两种“成功”不能证明电机可用

原厂 worker 的 PM 进入返回 `-EIO` 时，上传路径可能保持零初始化的结果字段：回调返回 0，但没有 DSP 写入、没有新增效果。成功上传后再注入擦除 PM 失败，擦除回调也可返回 0，而槽与链表记录仍在。这是已执行原始指令的结果，没有修改原厂模块修补它。

OS4 `init_module` 在本次测试的四个子初始化函数均返回 `-EIO` 时仍返回 0。`xring_haptic_i2c_probe` 的 Cirrus 子探测连续失败时，前三次返回 `-EPROBE_DEFER`，第四次进入音频组件后备注册；夹具让该注册成功后，包装回调返回 0，却没有注册 `cs40l26_input`。子探测和音频注册在此是注入边界，没有执行真实 I2C 或 sound core。

因此，`/proc/modules` 中模块存在、外层 probe 返回 0 或上传 ioctl 返回 0，分别只能证明对应层面的状态。以上结果不能确诊历史设备无震动的唯一根因。

## 六份原始 DTBO

[合并检查器](../scripts/audit_haptics_devicetree.py)校验原始 `vendor_boot.img`、`dtbo.img` 的档案哈希，重新解析 vendor boot 组件并逐字节核对分析目录的基础 DTB；随后由主机编译的 AOSP libfdt 把每份 DTBO 的八个条目分别应用到匹配基础 DTB。报告记录源码、原始分区、基础树、每个 overlay 与合并结果的哈希。

六份样本的第 5 条 overlay 均为 `board_id = 0x090f0000`，合并后模型为 `XiaoMi Xring_o1 O2S PHONE`，启用的 `/soc/i2c@EC100000/cs40l26@43` 明确具有 `bind-product = "dijun"`。其 `cirrus,f0-default` 为 `130 << 14`，没有 `cirrus,fw-defer` 或 `cirrus,rom-only`。这为 dijun 对应条目的固件初始化策略提供静态证据；没有模拟 bootloader 的条目选择。

其他板型的配置不同：条目 2 存在实际的 `cirrus,fw-defer`，条目 0/1/3/4 使用字面名称 `#cirrus,fw-defer`，条目 6/7 没有启用 CS40L26 节点。二进制属性名中的 `#` 不能作为 DTS 注释忽略，也不能把一个板型的配置推广到全部条目。本轮没有修改 DTBO、引导选择或原厂驱动。

## 已确认的软件后续项

当前生产 FF 在下一次播放前同步执行 `EVIOCRMFF`；原厂擦除回调会 `flush_work`，活跃效果分支可能等待“效果时长 + 500 ms”。这构成 GUI 同步调用阻塞的明确代码路径，580 ms 是本用例记录的驱动请求上限，实际设备等待时间未测量。

后续已完成[GUI 后台 owner](HAPTICS-WORKER-ADAPTATION.md)，覆盖连续请求、合并/过期、失败报告及 stop/join；永久内核阻塞仍无退出期限。后续[播放与初始化边界模拟](HAPTICS-PLAYBACK-EMULATION.md)另有 120+54 项通过，补充 start/stop worker、早期固件失败与 PLL 前的 probe。完整 DSP 启动、IRQ 和真实硬件项仍待验证，硬件继续 U。

## 复现

```bash
python3 scripts/setup_haptics_emulator.py
python3 tests/haptics_lifecycle_emulation.py
python3 scripts/audit_haptics_devicetree.py
python3 scripts/audit_unified_delivery.py
```

模拟器依赖锁与安装方式见[前一轮记录](HAPTICS-DRIVER-EMULATION.md)。DTBO 检查需要主机 gcc 和 Android 树内 `external/dtc`，临时构建与合并文件在退出时清理；所有操作仅使用主机固件文件。
