# 电量、温度与时钟读取

温度GUI交付更新：维护补丁0037通过现有status backend/controller接入tw_cpu_temp，合法整数-273..1000°C独立于电量解析；缺失/非法/禁用时隐藏，后续读数恢复。状态栏按实际文本重新布局，窄屏优先时间/录屏/电量，空间不足隐藏温度；装饰不可点击。11组真实LVGL/provider/controller检查通过，含14种解析值、定时刷新、0/负温、晚到/禁用恢复、电量隐藏、Wi-Fi/录屏、四宽度与明暗主题；28项状态回归通过。已检查1440宽实际渲染图，host字体/settings/tick仍为夹具，未证明Android显示或物理温度。installclean后make -j$(nproc)30并发构建[新候选](../imgs/built/recovery-dijun-unified-temperature-ui.img)，SHA256 `f2dea7dbf8ad58a9363f0906effa9ade627e7903bc45ee71e1b1fc1159994d84`，723来源及封装/新二进制核对通过。震动未改且仍未解决，设置现场采集未到，完整12组保持进行中。


本项使用生产读取函数、状态栏 backend 和一次性文件进行主机测试。没有调用手机、Health HAL 或真实 RTC，也没有调整主机时间。

## 固件与实现

[五份原厂声明记录](../logs/status-firmware-nodes.json)显示，各样本的 `vendor/etc/init/init.target.rc` 都等待 `/sys/class/power_supply/battery`。维护树明确启用
`TW_USE_LEGACY_BATTERY_SERVICES` 并将 `TW_CUSTOM_BATTERY_PATH` 指向这一原厂节点。
状态栏直接读取 `capacity`、`status`；不再经过为 OTA 安装设计的 `GetBatteryInfo()` 的“缺失时假定 100%”分支。
OTA 安装接口本身没有修改，不将本项结果扩大到其电量门槛或 Health 服务调用。

`ReadLegacyBattery()` 用不抛异常的完整整数解析代替 `stoi`。有效容量为 0–100；缺失、空文件、垃圾后缀、
多个数值、溢出或越界返回 -1。每次重新读取节点，晚出现或暂时消失的节点不会留下假读数。
只有完整的 `Charging` 状态表示正在充电；`Full`、`Unknown` 和读取失败不被当作正在充电。
未知状态与不充电在当前布尔接口中仍相同，不能据此判断充电器是否物理连接。

GUI2 状态 backend 只接受完整的 `<0..100>%`、`<0..100>%+` 和旧格式的单个尾随空格。
实际 0% 保持可见；非法或缺失读数隐藏电量区，不能显示为 0% 或 100%。`tw_no_battery_percent` 仍可隐藏此区域。

`tw_cpu_temp` 对 `/sys/class/thermal/` 的 `temp` 使用有符号毫摄氏度：42000→42、-5000→-5、500→0。
拒绝部分解析、溢出及超出 -273150..1000000 毫摄氏度的数值；这个范围是输入合理性保护，不是 CPU 运行温度承诺。
读取成功与失败都使用单调时钟的五秒缓存，互斥锁保护并发刷新。刷新失败清除有效状态，不把旧值或垃圾输入当成 0°C。
显式配置的非 thermal 路径保留原来的单位兼容分支；本设备不走该分支。

**当前 GUI2 状态栏显示时间、电量和充电图标，没有 CPU 温度控件。** 温度修复只覆盖已有 DataManager 数据接口，
并不等于新增了温度显示入口。真实 thermal_zone0 的测量精度和传感器身份仍需硬件证据；树中原有 cpu-crg 注释没有升级成实测结论。

## 时钟策略

2026-11-12补充[时间失败显示修正](CLOCK-FAILURE-ADAPTATION.md)：真实时间格式化函数检查time/localtime_r失败，清空输出；读取失败/转换失败/恢复/前后跳变四组纳入状态测试，当前共28组通过，旧代码新增场景中3组失败。此证据是显示层错误处理，不是RTC硬件故障、hctosys或漂移模拟。

dijun 没有启用 `QCOM_RTC_FIX`。生产 `FixupTimeOnBoot()` 在这一构建下不读取 Qualcomm ATS，也不调用 settimeofday。
界面从继承的系统时钟读取当前时间，再用已经持久化的时区设置显示。北京/香港默认使用 CST-8（UTC+8）。
既有实机记录曾显示 RTC `hctosys=1`；这只是历史记录，不能证明所有样本的冷启动时钟。

模拟覆盖 UTC+8 的午夜/正午、12/24 小时格式，以及墙上时钟回拨不冻结温度缓存。
没有用猜测偏移修复 RTC，也没有实现 NTP、漂移补偿或坏 RTC 读数校准。内核 hctosys、RTC 冷启动读错和漂移仍未模拟。

## 回归与使用范围

`python3 tests/status_readings_test.py` 执行 24 组测试，见[结果](../logs/status-readings.json)。
最初 23 组测试对修改前代码有 [13 组失败](../logs/status-readings-before.json)，包括异常终止、错误单位、缺值和解析问题。
追加的 16 线程并发用例在加锁前[失败](../logs/status-readings-before-cache-lock.json)，加锁后通过。
测试编译实际读取函数与整个 `status_backend.cpp`；仅替换 sysfs 文件路径、属性存储和时钟边界，启用 UBSan。

电量和充电状态直接在状态栏查看；读取失败时区域隐藏，等待后续有效读数。时间与时区仍从“设置 → 时间与时区”调整。
温度暂没有图形入口，不能把数据接口通过写成界面功能已完成。

交付镜像与五版本启动检查见[总报告](../simulation-report.md)。传感器硬件、充电器事件、Health Binder 行为和 RTC 校准保持未验证。

CPU温度身份核实：新增[六版本原厂DT/驱动注册证据](../logs/thermal-topology.json)。匹配base+overlay5合并后，cpu-crg均引用已启用的tsensor@EB008000通道0，同控制器22个物理传感器、整树38个thermal区域。原始模块通过devm_thermal_of_zone_register注册；通道0不等于Linux thermal_zone0编号，当前固定路径仍未获运行时身份验证。GUI2没有温度字段，后续应按type=cpu-crg匹配并补显示、缺值/晚注册/编号变化检查。此为静态证据，无生产修改/重编译；震动与完整12组目标继续未完成。

运行 `python3 scripts/audit_thermal_topology.py` 重建libfdt并合并六个原始overlay，`python3 scripts/verify_thermal_topology.py`核对报告来源与引用。先前“cpu-crg仅有注释”的证据已被原厂DT确认替代，但测量精度和sysfs编号仍未知。OS2/OS3没有OS4的xr_get_thermal_zone_by_id符号，脚本记录实际存在的函数，不能以缺少额外helper解释为温度驱动不兼容。只反汇编注册/读取函数，不执行probe、热管理、寄存器或GUI。

最新交付更新：`recovery-dijun-unified-thermal-identity.img`，SHA256 `338a4bf6c4e4563a30e6d26eecfbf6ac0793d5158974753a107eb38674f455db`。0036修正CPU温度固定thermal_zone0的身份假设：dijun设置ro.twrp.cpu_temp_type=cpu-crg，每5秒刷新按type精确匹配；缺失/重复/非法值返回无效，晚注册保持可重试。12项实际文件枚举/真实方法检查通过，旧实现同组9场景失败；28项状态/21项保存回归通过。installclean后30并发构建、719来源及封装/新二进制核对通过。同镜像profile回归另记。GUI尚无温度控件，震动未改/仍未解决，完整12组保持进行中。

复现 `python3 tests/thermal_identity_test.py`；旧版用 `--source logs/thermal-identity-before/data.cpp --report logs/thermal-identity-before.json`。覆盖编号重排、晚注册、错误type、重复type恢复、节点重新编号、垃圾/溢出/越界温度、缺值恢复、负温/不足一度、非zone名称、目录缺失恢复、显式关闭与无属性时旧路径。type按完整字符串匹配，普通文件名限定thermal_zone加数字，重复匹配拒绝选取。每次刷新重新枚举，5秒内仍复用上次有效/无效状态；未执行真实sysfs、内核thermal core或GUI。初始化只在配置type时允许晚注册，TW_NO_CPU_TEMP仍优先。

当前[交付审计](../logs/thermal-identity-delivery.json)绑定当前镜像，旧镜像段落为历史证据。读取功能推进不等于显示入口完成；下一步需GUI状态栏/页面布局与失败隐藏的真实LVGL检查，真实温度准确性继续U。

thermal-identity构建后收尾：同镜像9组/102阶段profile回放通过，719来源保持一致；当前交付审计见 `logs/thermal-identity-delivery.json`。GUI和FF库与otg-selection一致，温度界面/物理震动/完整目标仍未完成。

temperature-ui构建后收尾：同镜像9组/102阶段profile回放通过；723来源/维护补丁76+1+3文件重建一致、0待更新。当前交付审计 `logs/temperature-ui-delivery.json`；硬件温度/震动及设置现场仍未完成，完整12组保持进行中。
