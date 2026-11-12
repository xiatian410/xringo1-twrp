# Xiaomi 15S Pro / dijun — unified recovery adaptation

面向 Xiaomi 15S Pro（dijun、XRing O1）的 TWRP / YARP 多版本设备树、平台补丁与离线验证工程。优先使用同一镜像适配 HyperOS 3 / 4，并对 HyperOS 2 建立独立兼容档案。

**项目仍在适配中。** 主机模拟、编译成功和 profile 选择通过，不代表全部功能已经实机验证。OS4 震动调用正常是用户最新确认；不再作为当前排查重点。此前用户确认 backup-manifest 版本设置正常，此结论不外推为所有功能均已验收。

## 当前修正

- OTG：完整匹配 USB 控制器路径，修复把内置 UFS 分区列成大量 0 B OTG 存储的缺陷。
- 挂载：NVData、NVCFG、protect 等内部维护目标不再列入普通挂载页面，后台也拒绝手动挂载/卸载请求；保留原厂 fstab 和内部服务使用能力。
- ZIP：通用 updater 优先，否则按设备公布的 ABI 顺序选择；校验进度协议，正确处理子进程和 I/O 失败。 多包清缓存请求累计保留，清理失败正确反馈整体失败。
- sideload：统一子进程回收，取消按会话隔离，保留SIGPIPE处理器；私有进程测试不等于实际USB侧载验收。
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
