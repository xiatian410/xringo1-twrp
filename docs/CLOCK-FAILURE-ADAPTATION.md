# 时间读取失败与界面显示

2026-11-12。`DataManager::GetMagicValue("tw_time")`此前没有检查`time()`或`localtime_r()`结果，使用未初始化的tm继续格式化。失败时可能生成无效显示；旧实现也没有清除调用者传入的旧字符串。

维护补丁[0031-clock-read-failure.patch](../dtsrc/O1_asic_dual/patches/0031-clock-read-failure.patch)先清空输出、零初始化tm，`time()`返回-1或`localtime_r()`返回空时返回-1。有效时间继续沿用当前时区和12/24小时制。GUI设置适配器在读取失败时使用空字符串fallback；不引入RTC偏移、NTP或时钟写入。DataManager通用GetValue在magic失败后仍允许既有值查找，当前生产默认没有普通`tw_time`键；本检查不承诺外部另行写入同名键时仍强制隐藏。

[状态读取测试](../tests/status_readings_test.py)编译真实GetMagicValue、当前非QCOM的FixupTimeOnBoot和状态backend，时钟/sysfs/设置边界为替身，不调整主机时钟。新增读取失败、转换失败、失败后恢复、前后跳变四项，合计28组通过。[旧实现](../logs/clock-failure-status-before.json)3组失败；[新结果](../logs/clock-failure-status-regression.json)。转换失败替身返回空并填入定义明确的无效日期值，以确定性捕获旧实现忽略失败，不依赖未初始化内存偶然表现。

边界：本次没有模拟内核hctosys、真实RTC读取失败/漂移、启动时钟继承或电池断电；这些仍未知。既有UTC+8、DST和时区持久化检查独立保留。dijun未启用QCOM_RTC_FIX，FixupTimeOnBoot不读取ATS或调用settimeofday；坏硬件时钟不能由本显示修正校准。

新候选`recovery-dijun-unified-clock-failure.img`，SHA256 `1c0813cf324d76be52e588e4dd3358c1c104946841e393aef84df2d951437adc`。installclean后make -j$(nproc) recoveryimage完成，712来源指纹与封装/新二进制检查通过。本轮未改震动、触摸、解密或分区操作；整体任务仍未完成。

同镜像profile回归9组/102次阶段调用通过；设置21组和同镜像ARM64文件系统工具17项通过。`python3 scripts/audit_clock_failure_delivery.py`复核当前712来源、实际封装字节与对应回归输入；此定向审计不转移历史全量审计或认定全部功能完成。
