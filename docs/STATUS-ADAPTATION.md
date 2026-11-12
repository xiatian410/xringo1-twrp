# 电量、温度与时钟

当前状态栏显示时间、电量、充电状态和有效温度。温度由补丁 0063 放在时间 / 录屏标记之后，并限定于左半区，避开中央摄像头；窄屏空间不足时隐藏温度。当前候选与来源见 [交付报告](../simulation-report.md)，不以本页历史候选作为当前版本。

## 电量与充电

设备树启用 `TW_USE_LEGACY_BATTERY_SERVICES`，`TW_CUSTOM_BATTERY_PATH` 指向原厂 `/sys/class/power_supply/battery`。状态栏直接读取 `capacity` 和 `status`，不使用 OTA 电量接口“缺失时假定 100%”的回退；OTA 电量门槛未因此改变。

- `ReadLegacyBattery()` 完整解析整数，只接受 0–100，缺失、空值、垃圾后缀、溢出和越界返回 -1。每次重新读取，节点恢复后可重试。
- 仅完整的 `Charging` 表示充电。`Full`、`Unknown` 和读取失败均不显示正在充电，不能据此判断充电器是否物理连接。
- GUI backend 接受完整的 `<0..100>%`、`<0..100>%+` 及旧格式的单个尾随空格。0% 正常显示，非法 / 缺失读数隐藏；`tw_no_battery_percent` 可关闭显示。

## 温度来源与显示

原厂六份 DT 的 `cpu-crg` 引用启用的 `tsensor@EB008000` 通道 0；控制器有 22 个物理传感器，整树有 38 个 thermal 区域。通道 0 不等于 Linux `thermal_zone0` 编号。

补丁 0036 配置 `ro.twrp.cpu_temp_type=cpu-crg`，按完整 type 匹配重新枚举 `thermal_zone` 加数字的目录，不依赖固定编号。缺失、重复匹配或非法读数返回无效，支持晚注册、重新编号及故障后恢复。`TW_NO_CPU_TEMP` 优先，未配置 type 时保留原路径行为。

thermal 的 `temp` 使用有符号毫摄氏度：42000 → 42、-5000 → -5、500 → 0。拒绝部分解析、溢出及 -273150..1000000 范围外输入；此范围只是输入保护。显式非 thermal 路径保留单位兼容分支。

成功和失败均缓存五秒，使用单调时钟及互斥锁；墙上时间回拨不会冻结刷新，失败清除有效状态。补丁 0037 接入 GUI backend / controller，合法读数显示，缺失、非法或禁用时隐藏，后续有效值恢复。文字宽度变化会重新布局，装饰不可点击。0063 进一步维护摄像头避让，见 [布局与边界修正](archive/BOUNDED-MAINTENANCE.md)。

## 时钟与时区

dijun 未启用 `QCOM_RTC_FIX`；`FixupTimeOnBoot()` 不读取 Qualcomm ATS，也不调用 `settimeofday`。界面使用继承的系统时钟及持久化时区。北京 / 香港默认 `CST-8`（UTC+8），自选时区和 DST 保留，见 [设置与时区](SETTINGS-ADAPTATION.md)。

历史设备记录曾显示 `hctosys=1`，不证明所有版本冷启动正常。没有猜测 RTC 偏移、加入 NTP 或漂移补偿。原厂回调范围见 [RTC 驱动说明](STATUS-ADAPTATION.md#原厂-rtc-回调离线验证)。

## 定向验证

| 入口 | 已有范围 | 限制 |
| --- | --- | --- |
| `tests/status_readings_test.py` | 28 组，含解析、时区、时钟失败 / 恢复及并发缓存 | 生产函数与 backend；sysfs、时钟、属性边界为替身 |
| `tests/thermal_identity_test.py` | 12 项；旧代码 9 项失败 | 实际文件枚举，未运行内核 thermal core |
| 温度 GUI 检查 | 11 组，含缺值恢复、主题与宽度 | LVGL 执行；字体、读数、flush 为夹具 |
| `scripts/audit_thermal_topology.py` | 六份原厂 DT 合并及驱动注册静态证据 | 不执行 probe 或寄存器访问 |

原始报告保存在本地 `logs/`，公开摘要见 [CURRENT-VALIDATION.json](CURRENT-VALIDATION.json)。相关来源、输入和范围未变时复用结果，不为刷新日期重跑。实际传感器精度、Android 注册、Health Binder、RTC 冷启动失败与漂移仍未验证。

## 时间读取失败


2026-11-12。`DataManager::GetMagicValue("tw_time")`此前没有检查`time()`或`localtime_r()`结果，使用未初始化的tm继续格式化。失败时可能生成无效显示；旧实现也没有清除调用者传入的旧字符串。

维护补丁[0031-clock-read-failure.patch](../dtsrc/O1_asic_dual/patches/0031-clock-read-failure.patch)先清空输出、零初始化tm，`time()`返回-1或`localtime_r()`返回空时返回-1。有效时间继续沿用当前时区和12/24小时制。GUI设置适配器在读取失败时使用空字符串fallback；不引入RTC偏移、NTP或时钟写入。DataManager通用GetValue在magic失败后仍允许既有值查找，当前生产默认没有普通`tw_time`键；本检查不承诺外部另行写入同名键时仍强制隐藏。

[状态读取测试](../tests/status_readings_test.py)编译真实GetMagicValue、当前非QCOM的FixupTimeOnBoot和状态backend，时钟/sysfs/设置边界为替身，不调整主机时钟。新增读取失败、转换失败、失败后恢复、前后跳变四项，合计28组通过。[旧实现](../logs/clock-failure-status-before.json)3组失败；[新结果](../logs/clock-failure-status-regression.json)。转换失败替身返回空并填入定义明确的无效日期值，以确定性捕获旧实现忽略失败，不依赖未初始化内存偶然表现。

边界：本次没有模拟内核hctosys、真实RTC读取失败/漂移、启动时钟继承或电池断电；这些仍未知。既有UTC+8、DST和时区持久化检查独立保留。dijun未启用QCOM_RTC_FIX，FixupTimeOnBoot不读取ATS或调用settimeofday；坏硬件时钟不能由本显示修正校准。

该修正由补丁 0031 维护。历史交付与输入摘要保留在 `simulation-report.json`，当前交付以总报告为准。

## 原厂 RTC 回调离线验证

以下保留该验证阶段的输入与候选，不作为当前镜像信息；当前候选见[交付报告](../simulation-report.md)。

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
