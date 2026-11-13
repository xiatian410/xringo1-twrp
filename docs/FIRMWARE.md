# 固件来源与组件映射

设备：Xiaomi 15S Pro（dijun / XRING O1）。六份固件各自建档，不因相同 HyperOS 或内核主次版本而混用组件。

## 样本来源

| Profile | 系统版本 | Android | 来源 |
| --- | --- | --- | --- |
| `os2-initial` | OS2.0.121.0.VODCNXM | 15 | [OTA](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS2.0.121.0.VODCNXM/dijun-ota_full-OS2.0.121.0.VODCNXM-user-15.0-06c0ede3f3.zip) |
| `os2-final` | OS2.0.209.0.VODCNXM | 15 | [OTA](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS2.0.209.0.VODCNXM/dijun-ota_full-OS2.0.209.0.VODCNXM-user-15.0-b8b8e6c29b.zip) |
| `os3-initial` | OS3.0.4.0.WODCNXM | 16 | [OTA](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS3.0.4.0.WODCNXM/dijun-ota_full-OS3.0.4.0.WODCNXM-user-16.0-1398c39929.zip) |
| `os3-final` | OS3.0.304.0.WODCNXM | 16 | [OTA](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS3.0.304.0.WODCNXM/dijun-ota_full-OS3.0.304.0.WODCNXM-user-16.0-67dca2cb87.zip) |
| `os4-current` | OS4.0.0.19.XODCNXM | 17 | 本地来源包 `dijun-ota_full-OS4.0.0.19.XODCNXM-user-17.0-aa6a58e947.zip` |
| `os4-stable` | OS4.0.4.0.XODCNXM | 17 | [OTA](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XODCNXM/dijun-ota_full-OS4.0.4.0.XODCNXM-user-17.0-b0ce732f48.zip) |

“初始 / 最后 / 首个正式版”沿用用户对样本的定位，不代表独立核验了全部官方发布序列。下载身份、提取结果和组件摘要见 [firmware-inventory.json](../firmware-inventory.json)。完整 OTA 和提取分区不公开上传。

## 启动与组件所有权

| 来源分区 | 主要用途 |
| --- | --- |
| `boot` | 对应系统内核；不能凭相同 6.6 / 6.18 断言模块 ABI 一致 |
| `vendor_boot` / `init_boot` | 原厂 ramdisk、首阶段模块、init 与 bootconfig |
| `recovery` | 无内核 v4 恢复镜像布局，是统一候选封装的依据 |
| `vendor` / `odm` | HAL、安全服务、私有库、固件、VINTF 与 fstab |
| `vendor_dlkm` / `system_dlkm` / `odm_dlkm` | 对应固件的驱动模块与依赖 |
| `system` / `system_ext` / `product` | 系统身份、运行时依赖及配置 |
| `mi_ext` / `mi_product` | 以各包实际存在的逻辑分区为准，不强行补齐缺失分区 |

运行时 profile 同时考虑组件身份与兼容条件。原厂 first-stage 加载归 vendor_boot 管理，Recovery 不新增严格列表去覆盖它。TEE、TA、KeyMint / Gatekeeper 和私有库须保持匹配组合。

## 提取与核验

入口：`scripts/acquire_firmware.py`。工具支持本地 ZIP 或固定 HTTP 对象的范围读取，校验 payload metadata 与最终分区 SHA-256。HTTP ETag 不应冒充完整 ZIP 哈希。

payload v2 的操作数据偏移是**相对 DATA 区起点**，不是相对 ZIP 或 payload 文件起点：

```text
DATA 起点 = payload 在 ZIP 中的偏移 + 24 字节头 + manifest 长度 + metadata signature 长度
操作字节位置 = DATA 起点 + operation.data_offset
```

只提取工具支持的完整 payload 操作；未知或增量操作必须明确拒绝，不能输出不完整分区。完整包签名验证、提取哈希和镜像运行验证是不同范围。

新增档案步骤见 [维护指南](../MAINTENANCE.md)，选择规则与证据见 [PROFILE-SELECTION.md](PROFILE-SELECTION.md)。

## ABI 与封装比较

<!-- BEGIN GENERATED COMPATIBILITY -->

这是固件证据与静态冲突报告，不是单镜像兼容完成声明。完整导出符号、运行时选择、解密组合及功能模拟尚在补齐。

| 样本 | 包内 Android / SDK | 内核 release | 去重模块数 | recovery |
|---|---|---|---:|---|
| os2-final | 15 / 35 | `6.6.77-android15-8-g561b227c0e7d-abogki425270610-4k` | 382 | v4, kernel=0, 104857600 B |
| os2-initial | 15 / 35 | `6.6.30-android15-8-g8eff17a54aa9-abogki407711482-4k` | 381 | v4, kernel=0, 104857600 B |
| os3-final | 16 / 36 | `6.6.118-android15-8-gc44b714366cc-abogki519650608-4k` | 387 | v4, kernel=0, 104857600 B |
| os3-initial | 16 / 36 | `6.6.77-android15-8-g5770c661275f-abogki443185593-4k` | 386 | v4, kernel=0, 104857600 B |
| os4-current | 17 / 37 | `6.18.21-android17-5-g1d099fcb35e0-abogki538445360-4k` | 369 | v4, kernel=0, 104857600 B |
| os4-stable | 17 / 37 | `6.18.21-android17-5-g284297031c53-abogki553682993-4k` | 368 | v4, kernel=0, 104857600 B |

6 份 recovery 的头页（仅清零 ramdisk 长度后）共 1 种哈希。各样本的头格式、内核长度和容量见上表；同一镜像封装仍需逐包验证。

| 对比样本 | 共同模块名 | 存在导入 CRC 冲突的模块数 |
|---|---:|---:|
| os2-final--os2-initial | 381 | 31 |
| os2-final--os3-final | 378 | 21 |
| os2-final--os3-initial | 378 | 20 |
| os2-final--os4-current | 319 | 319 |
| os2-final--os4-stable | 319 | 319 |
| os2-initial--os3-final | 377 | 37 |
| os2-initial--os3-initial | 377 | 37 |
| os2-initial--os4-current | 318 | 318 |
| os2-initial--os4-stable | 318 | 318 |
| os3-final--os3-initial | 386 | 3 |
| os3-final--os4-current | 326 | 326 |
| os3-final--os4-stable | 326 | 326 |
| os3-initial--os4-current | 326 | 326 |
| os3-initial--os4-stable | 326 | 326 |
| os4-current--os4-stable | 368 | 1 |

同为 6.6 并不代表模块可互换。OS2/OS3 的 `module_layout` CRC 相同，但触摸、USB 或其他厂商符号仍存在版本差异。额外模块必须按精确 profile 选择，不能把 `lib/modules/6.6` 目录当作跨版本兼容依据。

以上比较读取 ELF `__versions` / 扩展版本节和 `__crc_*` 符号。机器报告保留每个冲突的符号名与两个 CRC，并检查原厂模块之间可解析的导入/导出关系。缺失的内核导出表明确记为 unresolved，不能据此声称全依赖通过。

包内身份以每份 `analysis/facts.json` 为准。尤其 OS3 末版下载名与包内 `16OS3.1.260921…` 不同。

来源：[获取清单](../firmware-inventory.json)。逐符号机器报告约 17 MB，留在本地，不随源码发布。准备原厂样本后，运行 `python3 scripts/compare_firmware.py` 可重新生成本节及本地 `docs/firmware-compatibility.json`；生成脚本见 [compare_firmware.py](../scripts/compare_firmware.py)。

<!-- END GENERATED COMPATIBILITY -->
