# 原厂 RTC 回调离线验证

六份 OS2/OS3/OS4 原厂 `dw_apb_rtc.ko` 的 ARM64 读取、设置回调，以及两份 OS4 的计数刷新回调，共 56 场景通过。每个模块重新从原始 vendor_boot 的 fragment-0 读取，先核对 OTA payload manifest 中的镜像大小和 SHA256，再逐字节比较提取模块。公开仓库仅包含测试和摘要，不包含原厂模块或镜像。

原始指令通过有界 Unicorn 执行器运行，未知导入和指令预算耗尽视为失败。复用的执行器文件名含 haptics，仅复用 ELF 装载/重定位机制，不涉及继续排查震动。MMIO、锁、PMIC、reset、延迟及日历转换是显式夹具；没有启动内核、修改主机时间或访问设备。

| 范围 | 场景与观察 |
|---|---|
| 读取：每份 5 项 | 零值、UTC、分频、32 位相加回绕、零分频畸形输入。原始读取回调不逐次读取 PMIC。零分频返回零是原始指令观察，不是可接受的设备配置。 |
| 设置：每份 3 项 | 成功、PMIC 失败、闹钟调整。软件 saved 偏移在调用 PMIC 前更新，PMIC 失败返回 -5，但不回滚该偏移。 |
| OS4 刷新：每份 4 项 | 成功、PMIC 失败、reset assert/deassert 失败。PMIC 失败使用当前计数加 saved 的回退值；reset 失败传播 -5，并在相应边界停止写入。 |

当前 dijun 未启用 `QCOM_RTC_FIX`，本次没有发现应引入 Qualcomm 校时偏移或修改原厂模块的依据。56 项不是冷启动、完整 probe/hctosys、实际日历算法或物理漂移验收；这些边界仍留在任务文档中。

在完整本地环境中复现：

```bash
python3 tests/rtc_driver_emulation.py
python3 scripts/audit_rtc_driver_emulation.py
```

完整证据位于本地 `logs/rtc-driver-emulation.json`，审计位于 `logs/rtc-driver-emulation-audit.json`；公开摘要见 [CURRENT-VALIDATION.json](CURRENT-VALIDATION.json)。本批次没有修改生产源码或重新编译，候选仍为 `recovery-dijun-unified-mtp-directory.img`，SHA256 `215914df1f8768bf00272f5c10c03b90fa8e624e9b1337fa6801a0ef3e5155b0`，765 份生产来源保持一致。全部 12 组目标仍进行中。
