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

“初始 / 最后 / 首个正式版”沿用用户对样本的定位，不代表独立核验了全部官方发布序列。下载身份、提取结果和组件摘要见 [firmware-inventory.json](firmware-inventory.json)。完整 OTA 和提取分区不公开上传。

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

新增档案步骤见 [维护指南](MAINTENANCE.md)，选择规则与证据见 [PROFILE-SELECTION.md](docs/PROFILE-SELECTION.md)。
