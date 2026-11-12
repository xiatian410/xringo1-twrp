# MiTEE 组合比较（静态候选）

服务、TA、私有库按原厂来源整理；本表记录静态依赖；多版本启动已接入统一候选，未执行真实解密。

| 样本 | system release / SPL | vendor SPL | 私有 DSO 数 | 静态 ELF 结果 |
|---|---|---|---:|---|
| os2-final | 15/2025-08-01 | 2025-08-01 | 24 | S1 dependency/symbol checks passed |
| os2-initial | 15/2025-04-01 | 2025-03-01 | 24 | S1 dependency/symbol checks passed |
| os3-final | 16/2026-09-01 | 2026-09-01 | 24 | S1 dependency/symbol checks passed |
| os3-initial | 16/2025-09-01 | 2025-09-01 | 24 | S1 dependency/symbol checks passed |
| os4-current | 17/2026-09-01 | 2026-09-01 | 26 | S1 dependency/symbol checks passed |
| os4-stable | 17/2026-10-01 | 2026-09-01 | 26 | S1 dependency/symbol checks passed |

OS3 初末版的 41 个安全服务/TA/私有库资产中，40 个字节一致，但一个 TA 不同，系统与 vendor 的 SPL 也不同；仍保留独立档案。OS4 还更换了 tee-supplicant、KeyMint、libteecli 及多项 TA。

OS2 初版 system SPL 为 2025-04-01，vendor SPL 为 2025-03-01，必须分别保留。OS3 的 vendor/ODM 构建 release 仍为 Android 15，不能拿它替代 system 的 Android 16 身份。

DSO 依赖比较采用当前 recovery 配套的 libbinder/libbinder_ndk；其余优先匹配 vendor 私有库，再检查 recovery 共享库。每个进程闭包的强符号差集为零时只记 S1，实际 namespace/服务启动/硬件密钥仍待验证。

[机器报告](crypto-compatibility.json) 保留全部源路径、SHA-256、依赖与符号结果。
[档案清单](../dtsrc/O1_asic_dual/profiles/inventory.json) 下的 profiles 与 content-addressed blobs 已接入 PRODUCT_COPY_FILES；实际镜像脚本模拟见 [启动说明](PROFILE-SELECTION.md)，不等于真实 TEE 成功。

同名 firmware 不自动去重：原厂 ODM 的 cs40l26-a2h.bin、cs40l26-dbc.bin 与 vendor 内容不同，保留两份原路径。ODM 中的触摸固件保留原路径记录，并将其与优先的 ODM Cirrus 固件映射到稳定 RAM 目录 `/lib/firmware`；统一候选在加载匹配的额外模块之前发布该 profile 的固件。

六个档案的资源按内容去重后为 78 份、40,184,830 B；实际压缩镜像容量已单独检查，见 [模拟报告](../simulation-report.md)。

六份 system/build.prop 的 release/SPL 现已从经过分区哈希检查的原文件取得，与 OTA 元数据一致；报告保留文件哈希和全部属性。只读选择组件的 77 场景结果见 [预检说明](PROFILE-SELECTION.md)，HAL 激活和服务启动顺序已接入，实际镜像的 77 次阶段调用通过模拟；后续真实硬件密钥操作仍未验证。

正式版独立使用新 tee-supplicant 和一项 TA，26 个私有 DSO 与旧 OS4 相同。system/vendor SPL 分别为 2026-10-01/2026-09-01，保留原身份。完整差异见[正式版记录](OS4-STABLE-ADAPTATION.md)。
