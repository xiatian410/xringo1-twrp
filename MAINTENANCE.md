# 维护指南

本文说明如何维护固件档案、平台补丁和交付；功能优先级见 [工作队列](docs/WORK-QUEUE.md)，验收要求见 [适配目标](ADAPTATION-GOALS.md)。不在本文追加逐轮测试流水账。

## 工作原则

- OS4 震动用户确认正常，作为已解决项，不例行重查。
- 相关源码、输入、范围未变时复用证据。检查需对应具体缺陷或实现决定，通过后结束本批。
- 不操作手机、物理块设备或 AVB / vbmeta；分析已有设备日志不等于代理实机测试。
- 每次生产修改由设备树的固定补丁重建，最终镜像先清理、再以全部 CPU 构建。

## 固件增补

1. 从 [固件映射](FIRMWARE-MAP.md) 与 [固件清单](firmware-inventory.json) 确认样本来源。新版本独立建档，不只按 HyperOS 大版本或内核主次版本归类。
2. 使用 `scripts/acquire_firmware.py --help` 查看提取参数。记录 OTA 身份、payload metadata、分区 SHA-256 和提取组件来源。HTTP ETag 不等于完整 ZIP 哈希。
3. 比较内核 release、模块 vermagic / CRC、fstab、TEE / TA / HAL、私有库和系统身份。只允许经字节或兼容性证明的资源去重。
4. 维护 `dtsrc/O1_asic_dual/profiles/` 中的选择规则和资源。未知、冲突或缺失组合必须明确失败，不能混装组件。
5. 更新固件映射、状态矩阵与必要的定向验证。新增 profile 不自动证明完整设备功能。

原厂 blob 和完整 OTA 仅留本地。公开资源摘要不应包含私钥或凭据。

## 平台源码与补丁

唯一维护树为 `dtsrc/O1_asic_dual/`；Android 内的设备目录由同步工具生成。

- [series.json](dtsrc/O1_asic_dual/patches/series.json) 固定各平台仓库的 commit、补丁顺序、补丁摘要与结果文件摘要。
- 新生产修正需加入对应仓库的维护补丁并更新结果绑定。
- `python3 scripts/sync_device_tree.py` 先检查；确认后使用 `--sync` 同步。脚本拒绝覆盖未列入维护系列的源码修改。
- 不在构建输出、临时目录或手工重打包产物中单独保留修正。

构建步骤见 [构建指南](BUILD-AND-TEST.md)。不新增自定义 first-stage 模块列表来覆盖原厂 vendor_boot 的加载所有权。

## 验证与交付

1. 明确本批缺陷、改变的生产行为和必要检查范围。
2. 优先使用真实生产方法；替代设备、HAL、属性、挂载等边界必须写明。能复用的结果不为刷新日期重跑。
3. 生产修改完成后执行 `installclean` 和 `make -j$(nproc) recoveryimage`，核对最终二进制、ramdisk、六份 profile 及来源绑定。
4. 记录候选 SHA-256、补丁和源码来源、构建日志、验证结果与剩余限制。原始报告在本地 `logs/`，公开摘要为 [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。
5. 更新 [验证报告](simulation-report.md)、机器索引 `simulation-report.json` 和相关主题文档。不要把历史结果自动标为当前来源一致。

新增证据、生产修复和文档整理分别说明；测试数量、构建成功及 CI 通过不等于设备功能已修复。

## GitHub 同步

每个连贯修改批次完成后：

```bash
python3 scripts/sync_github.py --push --message "说明实际修改"
```

导出脚本校验公开文件清单、补丁摘要、语法及文档入口，然后提交、推送，并确认远端 `main` 等于本地提交。仅在核对成功后报告已同步。

公开的是维护源码、配置、补丁、测试和文档；不上传镜像、编译文件、原厂 blob、完整 OTA、私钥或原始设备日志。公开 checkout 不能反向覆盖完整工作区。详细约定见 [GitHub 发布说明](docs/GITHUB-PUBLICATION.md)。

## 文档维护

README 负责项目入口；目标文档负责需求；工作队列负责下一步；验证报告负责当前交付；主题文档保留技术细节。旧的重复进度不再复制到多个入口，无关的本机运维记录不随源码发布。历史内容通过 Git 历史追溯。

清理文档时合并重复总览和候选流水账；独立实现说明、可复现脚本、固定补丁及许可保留。README 不重复镜像哈希和逐轮检查数字，统一链接交付报告；删除的历史内容通过 Git 追溯。
