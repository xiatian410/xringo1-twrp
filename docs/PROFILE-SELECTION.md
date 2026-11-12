# 固件组合选择与启动激活

六份原厂 system/build.prop 已从校验后的 EROFS 分区读取，release/SPL 与 OTA 元数据一致。
vendor/ODM 的 Android 15 身份单独保留，不能替代 OS3 的 Android 16 或 OS4 的 Android 17。
当前维护树已把六套档案、去重资源和运行时脚本接入构建；完整功能验收仍在进行。

## 输入与判断

`dijun-select-profile.sh` 是只读预检。recovery 先挂载当前槽位的 system、vendor、ODM、vendor_dlkm。
脚本读取 `/proc/bootconfig` 中唯一的 `androidboot.slot_suffix`，只接受 `_a`、`_b`。
四个挂载的 dm 名称必须分别匹配当前槽位；缺失、重复、另一槽位或未知映射名称返回错误。

每个候选同时核对完整 kernel release、system/vendor/ODM build.prop、vendor fstab、
Synaptics 模块、对应震动模块的 SHA-256，以及全部所需 blob 的 SHA-256 和大小。
必须恰好匹配一个候选；未知组合、混装模块、损坏资源不选择“接近”的版本。
选择器成功只输出 profile、槽位、内核和 `matched-not-activated`；激活由后续脚本负责。
返回码：0 匹配；2 输入/清单不合法；3 无完整匹配；4 多个匹配。

## 启动顺序

1. `KernelModuleLoader` 的 profile 分支先挂载所需来源，仅暂存实际匹配的资产。
   该分支完全绕过 legacy major.minor 目录和通用模块清单；失败也不回退。
2. `dijun-runtime.sh cache` 校验全部用户空间资源和尚未加载的模块来源，再发布 `/lib/firmware`。
   已在 `/sys/module` 的模块由原厂首阶段保留，不重新插入。
3. `modules` 保持原厂硬依赖与可实现的软依赖顺序，在就绪模块中优先触摸依赖，触摸先于可选震动模块，再调用 insmod，记录缺失硬依赖或失败。
   可选外设模块插入失败不阻止独立的安全服务准备。资源哈希不符则终止该档案激活。
4. 外层 `ProcessFstab` 与 `SetupFstabPartitions` 完成卸载后，`publish` 才把 HAL、TA、私有库复制到 RAM 路径。
   发布前重新验证缓存；若 system/vendor/ODM 仍挂载，拒绝写入。
5. 从该 profile 的 `crypto.prop` 设置并回读三个身份属性，再准备 MiTEE 节点和原始 persist 存储。
   已有 persist 挂载必须解析到原始 persist 块设备；不接受 tmpfs 或其他分区替代。
6. 显式启动三个 MiTEE 服务，检查 KeyMint、Gatekeeper、SharedSecret、SecureClock、keystore2 五个 Binder 接口。
   注册与 ping 就绪后才设置 `twrp.crypto.ready=1`。HAL 不设置 lazy interface 触发，采用 oneshot，避免失败重启循环。
7. 自动解密与手动凭据入口均检查就绪状态。服务退出/keystore 重启会撤销就绪状态；失败不调用格式化或重启。

MiTEE 节点等待上限约 5 秒；Binder 轮询 15 秒，外加 18 秒进程期限。
cache/modules/publish 外层期限分别为 45/45/35 秒。它们约束用户空间启动等待；
无法保证终止陷入内核不可中断睡眠的驱动，也不等于已为后续真实 TEE 密钥操作实现硬超时。

原厂模块计划由 `generate_profile_runtime.py` 从真实 ELF 和 depmod 元数据生成。
四个 OS2/OS3 样本各有 51 项依赖闭包，两个 OS4 样本各为 54 项；这不是每次实际插入的数量。
原厂 `pre:dw_apb_rtc` 缺少分隔符，Android libmodprobe 不把它作为有效软依赖；报告保留该原始异常。
OS4 有一个可选顺序与硬依赖形成循环，保留两端模块、按硬依赖加载，并在 `module-sources.json` 记录循环。
不存在的可选软依赖也逐项保留，不把它们伪装成已满足。完整内核导出 CRC 尚未取得，仍属未验证边界。

## 依赖与覆盖范围

一个镜像内含六套用户空间资产，按内容去重为 78 个 blob、40,184,830 字节；
模块从当前安装的对应 vendor_dlkm/system_dlkm 或继承的 vendor_boot 获取，不在 recovery 混装模块。
清除 system/vendor/ODM、未知中间版本、自定义内核、异常槽位/快照命名都会使选择失败。
此时不会尝试猜测 ABI 或解密身份；原厂已加载的显示/USB 驱动可继续使用，但离线检查不能保证缺失系统下的实际可用性。
这六个采样版本不代表其间所有版本，新增版本须重新建立档案。

## 离线证据

- [选择测试](../logs/profile-selection-test.json)：8 组、77 场景；含正式版与旧 OS4 双向组件混装拒绝，真实固件身份与资源字节，模拟挂载/proc；成功后输入不变。
- [运行时测试](../logs/profile-runtime-test.json)：直接执行生产 shell；六包两槽位、全部未加载模块顺序、重复加载避免、缓存损坏、混装、节点缺失、persist 冲突、HAL/属性错误。
- [核心分支测试](../logs/profile-core-test.log)：编译执行原 C++ 分支，替换挂载/属性/命令；验证无 legacy 回退、只释放自行挂载的分区、自动/手动解密门控。
- [Binder 就绪测试](../logs/wait-services-test.log)：编译真实 helper，仅替换 Binder 与时钟；缺服务、延迟注册、死亡 Binder、引用释放和期限。
- 最终镜像及从镜像取出的脚本测试见 [模拟报告](../simulation-report.md)。

这些测试不执行原厂 ARM64 HAL，不访问 TEE、RPMB 或真实手机块设备。接口模拟成功不表示真实解密成功。
诊断状态为 `twrp.profile.selected`、`twrp.profile.state`、`twrp.profile.modules`、`twrp.crypto.ready`；
日志在 `/tmp/dijun-runtime.log`、`/tmp/dijun-mitee-prepare.log` 与 `/tmp/recovery.log`。

OS4 正式版增补验证发现激活阶段仍有五档案允许列表，已明确加入 `os4-stable`。选择器和激活阶段必须同时验证，首份失败镜像记录见[正式版增补](OS4-STABLE-ADAPTATION.md)。

触摸失效反馈及加载优先修正见[OS4 触摸排查](OS4-TOUCH-FAILURE.md)。`twrp.profile.touch_modules` 只反映模块存在，不能代替 input 注册或事件交付证明。
