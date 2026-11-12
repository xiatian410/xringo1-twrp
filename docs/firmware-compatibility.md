# 固件兼容性分析（离线阶段）

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

数据：[机器报告](firmware-compatibility.json)；来源：[获取清单](../firmware-inventory.json)。
