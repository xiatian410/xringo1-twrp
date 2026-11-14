# 固件组合选择与启动激活

## 当前规则：按功能组件兼容，不按每次 OTA 的构建标签锁定

用户已确认 `1.0.1-rc2` 触摸正常，同时报告解密与震动不可用。rc2 的“仅触摸”分支会有意跳过其余组件，未满足完整使用要求。`1.0.1-rc3` 将触摸、震动、解密分别选择和激活；不再因 system/vendor/ODM 整份 `build.prop` 的日期、版本号或无关配置变化关闭全部功能。

**内核、对应组件与所需配置不变的 OTA，无需逐个增加系统小版本 profile。**六套原厂档案作为已知组件集合，允许运行时复用，而不是 OTA 版本白名单。若实际内核 ABI、驱动/固件、TEE/TA/HAL 或加密布局发生变化，仍需确认兼容；当前实现不承诺任意未来内核或未知安全组件。

`dijun-select-profile.sh` 只读预检。四个来源分区的 dm 名称必须对应 `/proc/bootconfig` 的唯一活动槽位，拒绝另一槽位、缺失与重复映射。每个功能必须恰好匹配一套组件；成功只代表可进入激活流程。

| 功能 | 运行时匹配条件 | 与其他功能的关系 |
| --- | --- | --- |
| 触摸 | 精确 kernel release、Synaptics 全部硬依赖的来源 SHA-256、当前 ODM 固件与配置、内置资源一致 | 不依赖解密或震动匹配 |
| 震动 | 精确 kernel release、原厂震动驱动及硬依赖、当前 vendor/ODM 固件与所封装资源一致 | 组件不匹配只停用该功能；不改动驱动内部振动实现 |
| 解密 | 精确 kernel release、MiTEE/FBE/UFS/RPMB 硬依赖、原厂 HAL/TA/私有库/VINTF 字节、当前 Android release 家族和加密存储布局 | 触摸或震动不匹配不会自动拒绝解密；安全服务与真实密钥操作另行判断 |

解密从活动槽位的原始 `system/build.prop` 读取 `ro.build.version.release` 与 `ro.build.version.security_patch`，从 `vendor/build.prop` 读取 `ro.vendor.build.security_patch`，不使用 Recovery 自己的构建身份。重复、缺失、非法日期或未采样 Android release 家族均拒绝该解密组合；合法的新补丁日期不需要重新编译。系统与 vendor 的 SPL 分别传递，不能统一写成旧值或最高值。

加密布局检查只比较 `/data`、`/metadata`、persist 三项的源设备、挂载点、文件系统与规范化后的选项。注释、行顺序、选项顺序和其他挂载项变化不会拒绝解密；实际加密参数变化仍拒绝。

默认 `--purpose full` 保留旧的完整原包身份检查，供档案溯源与诊断使用；生产 runtime 分别调用 `--purpose touch|haptics|crypto`，不再把 `full` 作为全部功能开关。返回码为 0 匹配、2 输入/清单异常、3 无兼容集合、4 多个匹配。坏清单或歧义阻止激活，正常无匹配仅影响对应功能。

## 启动顺序

1. `KernelModuleLoader` 挂载活动槽位来源，`cache` 分别校验三个功能。来源包含已加载模块的文件；模块已经 live 也不能绕过版本检查。
2. 合并已通过功能的资源、硬依赖及震动/解密的可用原厂软依赖；共享模块或目标路径必须字节一致。按触摸、震动、解密顺序合并，闭包内依赖先于使用者，重复模块仅保留一次。
3. 暂存完成后先发布 `/lib/firmware`，再进入 `modules`。已加载模块不重插；保留模块状态等待和失败记录。触摸普通报告请求继续使用 rc2 原字节脚本。
4. 源分区卸载后，`publish` 复核暂存资产，再复制到 RAM，禁止写穿仍挂载的 system/vendor/ODM。仅通过的功能有对应资源。
5. 解密闭包全部 live、缓存的当前身份未变时，设置并回读三个实际版本属性，准备原始 persist 与 MiTEE 节点。没有解密兼容集合时，保留已通过的驱动。
6. 显式启动 tee-supplicant、KeyMint、Gatekeeper；五个 Binder 接口注册/ping 后设置 `twrp.crypto.ready=1`。启动失败、服务退出或 keystore2 重启撤销就绪；不自动格式化或重启。

`ready` 代表服务接口就绪，不代表已经成功解开硬件密钥或 CE 数据。节点等待、模块插入、Binder 等待继续有界；外层 cache/modules/publish 为 45/45/35 秒，不能保证终止内核不可中断睡眠。

## 生成与依赖

`generate_profile_runtime.py` 从原始 ELF/depmod 和资源来源生成每个功能的 `*-modules.plan`、`*-files.list`、`*-checks.list`；震动和解密还保留原厂可用软依赖及其可实现顺序，而触摸沿用 rc2 硬依赖范围。另生成 `crypto-layout.conf`、`crypto-release.conf`。OS2/OS3 各 44 项触摸硬依赖，OS4 各 46 项；解密独立纳入 FBE/UFS/RPMB，避免仅检查触摸闭包里的 MiTEE 就误报安全链路齐全。震动使用现有原厂组件，没有重新做 DSP 或振动实现研究。

模块仍从当前 vendor_dlkm/system_dlkm 与继承 vendor_boot 获取，Recovery 不打包或跨版本混用 `.ko`。公共 VINTF 与 blob 保持原字节；清除来源分区或换入未知组件会影响依赖这些来源的功能，不伪装为已支持。

## 本批有限验证

- 生产 shell 回归 13 组、175 次阶段调用：六样本双槽、更新构建标识与当前 SPL、独立功能不匹配、模块失败、暂存完整性、服务/属性/persist 错误。
- 从 rc3 实际镜像取出的脚本：六样本同次触摸/震动/解密启动，共 18 次阶段调用；旧 rc2 在六样本的同一更新条件全部只能进入 touch 分支。
- 默认完整原包选择器保留 8 组、77 场景检查；清理构建、943 项生产来源及实际载荷差异通过，原厂资源、触摸 helper 与平台二进制未变。

挂载、insmod、sysfs/input、属性和 Binder 都是明确替身。以上不执行手机、真实 TEE/RPMB 密钥操作，也不证明 rc3 现场解密或震动已经恢复。rc2 的触摸由用户确认正常，rc3 保留其触摸 helper 和输入二进制；原始 OS4.0.5 全包未取得，不声明完整支持该包。具体镜像和状态见[交付报告](../simulation-report.md)。

诊断字段：`twrp.profile.touch_selected`、`haptics_selected`、`crypto_selected`、`twrp.profile.state`、`twrp.profile.modules`、`twrp.crypto.ready`；日志为 `/tmp/dijun-runtime.log`、`/tmp/dijun-mitee-prepare.log` 与 `/tmp/recovery.log`。

## OS4 正式版增补记录

样本 `os4-stable`；用户将此包指定为 OS4 首个正式版。既有 `os4-current` 保留表示 OS4.0.0.19，不将其历史实机结果转移到正式版。

来源：https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XODCNXM/dijun-ota_full-OS4.0.4.0.XODCNXM-user-17.0-b0ce732f48.zip

以下为正式版增补阶段记录：15 个所需分区完整 SHA-256 校验通过，全部所需系统分区目录及选定配置资源已读取，正式版独立档案进入统一候选。此阶段只做主机分析与模拟。当前候选见[交付报告](../simulation-report.md)。

包内 OTA 身份为 Android 17 / SDK 37，安全补丁 `2026-10-01`，增量构建 `17OS4.0.261106.161950561.XRPECN.S`。下载文件名和内部构建身份分别保存，不相互替代。

已校验的 boot 给出内核 `6.18.21-android17-5-g284297031c53-abogki553682993-4k`；旧 OS4 为 `6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k`。两个 recovery 清零 ramdisk 长度后的头页相同；正式版触摸驱动字节变化、震动驱动字节相同。目前检查的触摸/震动模块共享导入 CRC 未变化，不代表全部内核符号或运行时驱动已经验证。

完整模块集合共有 368 个同名模块；`mi_memory` 的 `mi_ufshcd_query_descriptor_retry` 与 `mi_ufshcd_read_desc_param` 导入 CRC 改变，`mi_low_lat_mem`、`mi_reclaim`、`mitee`、`wlan_drv_gen4m_eap_6639`、`xr_ddr` 的导入集合改变。两个版本不能盲目混装模块；正式版内部已解析的 module-to-module CRC 无冲突，未取得的内核导出仍明确未验证。

获取器使用强 ETag 固定 HTTP Range 对象，核验 payload metadata hash、操作数据 hash（存在时）和每个完整分区 SHA-256。完整 ZIP 未下载，不能把 ETag 当作 ZIP 摘要。获取清单保留对应范围限制。

vendor 提取完成后，KeyMint/Gatekeeper/tee-supplicant 的强符号闭包检查通过；26 个私有 DSO 与旧 OS4 相同。`tee-supplicant` 和 `07578c47-fb20-4d61-a3098be0e5a419d2.ta` 不同，必须按正式版原始字节独立封装。system/OTA SPL 为 `2026-10-01`、vendor SPL 仍为 `2026-09-01`，正式版不得沿用旧 system SPL 或统一覆盖两者。system 原文件已核对，与 OTA 身份一致。

增补流程：完成关键分区和系统资源清单→对比启动/fstab/HAL/TA/私有库/固件→独立 profile→六样本只读选择与拒绝混装→构建统一镜像→从同镜像提取脚本回放并检查策略/内容/容量→更新任务与矩阵。

工具已移除 OS4 样本名称对震动模块选择的特殊处理，改为核对已提取 vendor_dlkm 的 cs40l26 probe 导出；缺失或歧义直接拒绝。原模块解析与独立 libkmod 对照、缺失和重复候选检查共六组通过；获取器四组异常夹具通过。

证据：[获取日志](../logs/os4-stable-acquisition.log)、[获取清单](../firmware/samples/os4-stable/inventory.json)、[初步结构](../firmware/samples/os4-stable/analysis/facts.json)、[解析回归](../logs/os4-stable-facts-test.log)、[提取回归](../logs/os4-stable-acquire-test.log)。完整目标与进度以[任务文档](../ADAPTATION-GOALS.md)为准。

首份正式版候选在实际镜像脚本回放中失败：选择器匹配成功，但激活脚本允许列表仍只有五个档案。`recovery-dijun-unified-os4-stable-rejected-activation.img` 和对应失败回放保留作为中间证据；该镜像不属于可用交付候选。已补齐允许列表，修正后构建已重新通过同镜像回放。

正式版增补阶段镜像：`统一正式版候选`（历史文件当前缺失），SHA-256 `9350417bf9b53af8a323ddf6597bf89153c926ace1e79bd350edce67076533de`；78 个去重 blob，压缩 ramdisk 76,623,610 B。选择 77 场景、六包两槽位/全部未加载模块顺序共 77 次阶段调用通过。构建和实际镜像策略/init/容量检查通过；硬件与完整功能未完成项继续保留。

本节记录正式版增补时的历史候选；当前产物统一见[交付报告](../simulation-report.md)。
