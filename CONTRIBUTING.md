# 贡献指南

欢迎针对 Xiaomi 15S Pro（dijun / XRING O1）提交可定位的问题与修正。项目目标见 [适配规范](ADAPTATION-GOALS.md)，当前队列见 [工作队列](docs/WORK-QUEUE.md)。

## 报告问题

请描述系统样本 / profile、Recovery 候选名称和哈希、操作步骤、预期与实际结果。引用日志时去掉密码、密钥、账户信息和个人文件路径。不要将完整原厂 OTA、专有 blob 或原始个人日志提交仓库。

硬件观察与离线模拟需分开表述；编译成功和 CI 通过不能代替设备功能正常。

## 提交修改

1. 围绕具体缺陷修改，避免无关重构和重复验证。
2. 生产修改维护在 `dtsrc/O1_asic_dual/patches/`，更新固定基线、补丁摘要和结果绑定；设备配置修改进入维护树。
3. 运行与改动相关的必要检查；来源未变的已有结果可复用。说明真实执行、替身与剩余限制。
4. 更新对应主题文档。README 只保留项目入口；不在多个根文档复制测试流水账。
5. 提交说明包含问题、行为变化和验证结果。源码 CI 由 [公开完整性脚本](scripts/check_public_tree.py) 与 [文档检查](scripts/check_documentation.py) 执行。

文本使用 UTF-8、LF 换行和文件末尾换行，去掉行尾空白；编辑器约定见 [.editorconfig](.editorconfig)。Markdown 使用单一一级标题、连续标题层级与相对链接，列表及代码块前后留空行。不要批量格式化固定补丁或历史证据；[.gitattributes](.gitattributes) 保留补丁原始字节，避免改变已绑定的 SHA-256。

公开 checkout 缺少构建 blob 与本地资源，准备方式见 [构建指南](BUILD-AND-TEST.md)。最终镜像构建必须先 `installclean`，再使用 `make -j$(nproc)`。

## 发布约定

维护者从完整工作区运行：

```bash
python3 scripts/sync_github.py --push --message "Describe the actual change"
```

导出只包含已审核文本，推送后核对远端提交。镜像、编译文件、原厂资源、私钥和原始设备日志不公开。详见 [发布说明](MAINTENANCE.md#github-同步)。
