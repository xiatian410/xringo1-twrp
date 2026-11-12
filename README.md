# Xiaomi 15S Pro / dijun — unified recovery adaptation

2026-11-13 当前候选：`recovery-dijun-unified-bounded-maintenance.img`，SHA256 `218c5edd28c4e458464fc035a73b68808b016598c51e50877b2c0a1b055da3c3`。修正温度中央摄像头遮挡、ext扩容尺寸边界及A/B更新器同步拒绝收尾；有限页面生命周期检查未复现刷新现场故障。775来源、清理构建、六profile封装、5份init与9组/102阶段激活回放通过。范围与剩余项见[本批维护](docs/BOUNDED-MAINTENANCE.md)。编译文件不上传GitHub。

当前新增 [A/B 命令失败与 payload ZIP 存储检查](docs/AB-COMMAND-VALIDATION.md)，尚未完成真实 OTA 安装验收。

当前候选加载页显示 `XRING O1`，并修正刷入目标缺失与高级清除/分区工具 NV 暴露，见 [分区操作说明](docs/PARTITION-ACTIONS.md)。源码公开同步；镜像与编译文件不上传。

面向 Xiaomi 15S Pro（dijun、XRing O1）的 TWRP / YARP 多版本设备树、平台补丁与离线验证工程。优先使用同一镜像适配 HyperOS 3 / 4，并对 HyperOS 2 建立独立兼容档案。

**项目仍在适配中。** 主机模拟、编译成功和 profile 选择通过，不代表全部功能已经实机验证。OS4 震动调用正常是用户最新确认；不再作为当前排查重点。此前用户确认 backup-manifest 版本设置正常，此结论不外推为所有功能均已验收。

## 当前修正

六份固件的18个原厂安全服务已通过真实ARM64 linker重定位检查，停在构造函数前；另有12项缺库/缺符号对照。已补查私有chroot中的实际namespace字段和配置消费对照；真实init环境、TEE和解密仍未验收，见[运行时搜索配置](docs/PROFILE-SERVICE-NAMESPACE.md)。本轮没有更改生产镜像。

ZIP安装离线检查现已接续真正的ARM64测试updater（20场景），使用当前镜像Android linker/libc；父安装器及QEMU启动桥的限制见[范围说明](docs/ZIP-ARM64-EXECUTION.md)。该检查不代表原厂OTA/payload或设备验收；镜像按后续生产修正另行更新。

最新本地候选为`recovery-dijun-unified-mtp-directory.img`，新增MTP目录上传修改时间及完成状态修正，继承NV普通挂载限制、OTG发现与侧载重启交接。对象链路110项、转移48项通过；实际USB/Windows/实机仍未验收。源码按每批次修改同步本公开仓库，编译镜像不上传。

- OTG：完整匹配 USB 控制器路径，修复把内置 UFS 分区列成大量 0 B OTG 存储的缺陷。
- 挂载：NVData、NVCFG、protect 等内部维护目标不再列入普通挂载页面，后台也拒绝手动挂载/卸载请求；保留原厂 fstab 和内部服务使用能力。
- ZIP：通用 updater 优先，否则按设备公布的 ABI 顺序选择；校验进度协议，正确处理子进程和 I/O 失败。 多包清缓存请求累计保留，清理失败正确反馈整体失败。
- sideload：统一子进程回收、逐包清缓存、避免ORS重复安装、报告清理失败；私有进程/ZIP测试不等于实际USB侧载验收。
- sparse：检查展开容量及写入完成状态。MTP 上传日期和 CE 解密失败清理等范围见文档。

当前候选、校验和、验证边界以 [simulation-report.json](simulation-report.json) 和 [任务文档](ADAPTATION-GOALS.md) 为准。**仓库不提供编译镜像或 Releases 二进制。**

## 源码组织

| 路径 | 内容 |
|---|---|
| `dtsrc/O1_asic_dual/` | 唯一维护设备树，含六份固件 profile、init、SELinux、构建配置 |
| `dtsrc/O1_asic_dual/patches/series.json` | 平台仓库的固定 commit、补丁顺序、补丁及结果文件 SHA256 |
| `manifests/` | 本地实际 Android 源码仓库的固定 revision 清单 |
| `scripts/` | 固件提取、档案生成、设备树同步、构建和验收工具 |
| `tests/` | 实际生产函数/线程/协议与临时文件夹具结合的离线检查 |
| `docs/` | 功能边界、固件比较、维护和验证说明 |
| `PRIVATE-ASSETS.json` | 未发布二进制资源的路径、大小及摘要；不含文件内容或私钥 |
| `SOURCE-MANIFEST.json` | 本次公开快照的文本来源摘要和文件权限 |

平台修改以补丁形式提供，基线来自 [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery)，并非另放一份无法追溯的生成源码。`sync_device_tree.py`先从固定 Git commit 重建补丁结果，再同步设备树，拒绝覆盖未列出的源码修改。

## 准备与构建

当前维护脚本默认路径为 `/root/AAA/xringo1-twrp` 和 `/root/AAA/twrp`。公开 checkout 是源码快照，不能在未准备 Android 依赖、原厂资源和本地构建密钥时直接产出完整镜像。

1. 将本工程放到 `/root/AAA/xringo1-twrp`，准备与 `manifests/pinned.xml`一致的 Android 源码；`patches/series.json`中的四个仓库必须匹配指定 commit。
2. 根据 [FIRMWARE-MAP.md](FIRMWARE-MAP.md)、[firmware-inventory.json](firmware-inventory.json) 中的原厂地址获取所需 OTA 资源。提取工具支持范围读取；ETag 不等于完整 ZIP 的 MD5。校验分区与文件哈希后再生成 profile。不要混用不同样本的模块、安全组件或 TA。
3. 恢复 `PRIVATE-ASSETS.json`列出的本地构建资源。原厂二进制、字体/图片等资源没有随源码上传；已有合法本地资源目录时可使用 `scripts/restore_private_assets.py`按摘要导入。该工具不生成或导入私钥。
4. 当前配置引用 `dtsrc/O1_asic_dual/security/releasekey`构建密钥。自行在本地准备相应 `.pk8` / `.x509.pem`文件；这些文件不参与 GitHub 同步。
5. 同步、清理并构建：

```bash
python3 scripts/sync_device_tree.py --sync
cd /root/AAA/twrp
source build/envsetup.sh
lunch twrp_dijun
make -j$(nproc) installclean
make -j$(nproc) recoveryimage
```

主机还需提供 `python`命令指向 Python 3；构建详情见 [MAINTENANCE.md](MAINTENANCE.md)。历史构建说明中的旧候选、内核覆盖目录和测试结果不代表当前支持范围。

构建机磁盘布局、swap 与编译负载内核参数的实测记录见 [docs/BUILD-ENV-DISK-TUNING.md](docs/BUILD-ENV-DISK-TUNING.md)，含重建顺序与回滚边界。该文档只描述本地构建环境，不涉及生产源码或镜像内容。

## 验证与贡献

```bash
# 公开快照的完整性检查，不需要固件或 Android 构建树
python3 scripts/check_public_tree.py

# 完整本地环境中执行；全部使用临时文件或明确替身
python3 tests/nv_mount_policy_test.py
python3 tests/zip_install_chain_test.py
python3 scripts/sync_device_tree.py
```

许多检查还需要本地 Android 头文件/主机库、原厂样本、LVGL 或 QEMU；不要把缺依赖和实机功能故障混为一谈。原始设备日志、完整本地测试报告和本地工具包未公开上传，公开结果摘要见 [docs/CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。CI 只检查源码清单、Python/JSON语法和补丁完整性，不宣称执行了全部硬件或固件依赖测试。

新修改需维护基线与补丁、添加能复现问题的必要检查，并更新适配边界。后续源码/测试/文档修改须同步 GitHub，流程见 [公开仓库维护](docs/GITHUB-PUBLICATION.md)。不要求实机回测，不在本任务中执行 adb/fastboot、刷写或真实分区操作。

## 来源和许可

TWRP / Team Win 及 AOSP 源码保留各自原有版权与许可；上游 recovery 的许可说明随 `NOTICE`保留。补丁中的文件头与原仓库许可仍适用，不以一个新许可覆盖全部上游代码。原厂专有 blob、完整 OTA 和私钥均不在本仓库内。
