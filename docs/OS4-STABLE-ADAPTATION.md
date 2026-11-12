# OS4.0.4.0 正式版增补记录

样本 `os4-stable`；用户将此包指定为 OS4 首个正式版。既有 `os4-current` 保留表示 OS4.0.0.19，不将其历史实机结果转移到正式版。

来源：https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XODCNXM/dijun-ota_full-OS4.0.4.0.XODCNXM-user-17.0-b0ce732f48.zip

当前进度：15 个所需分区完整 SHA-256 校验通过；全部所需系统分区目录及选定配置资源已读取。正式版独立档案进入本轮统一候选镜像。只做主机分析与模拟，不连接设备。

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

后续当前产物已更新为[GUI 震动后台候选](HAPTICS-WORKER-ADAPTATION.md)，保持六份精确档案；本页上列正式版增补镜像与哈希作为该阶段历史记录保留。
