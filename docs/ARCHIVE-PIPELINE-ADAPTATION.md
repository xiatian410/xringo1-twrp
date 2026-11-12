# tar、压缩、加密与分卷管道适配

日期：2026-11-11。修改固定在设备树补丁 [0020](../dtsrc/O1_asic_dual/0020-archive-codec-pipelines.patch)，当前镜像和哈希见[模拟报告](../simulation-report.md)。本轮只执行主机夹具，没有连接手机。

## 修改与原因

| 原行为 | 当前行为 |
|---|---|
| AES fork 后没有 exec，继承其他归档线程的管道写端，解密/编码等待 EOF 不能结束 | AES 子进程重定向标准输入输出后关闭其他描述符；支持 close_range 和有限 fd 遍历后备 |
| libtar 将管道单次短读当成块损坏 | 读取回调累计到请求长度，重试 EINTR；全部恢复入口使用该回调，真实 EOF/错误仍返回失败 |
| tar 结束后未等待解码器，gzip 尾部 CRC 错误可能被忽略 | 消费结束块后的流，检查零填充和编码器最终退出结果；失败终止并回收相关 helper |
| OAES 流函数没有结果，子进程可能把失败报告成成功 | 检查随机数、读取、写入和 EVP 调用，返回 bool 并成为子进程退出码 |
| 多线程共享 tar 写缓冲区、位置和进度 fd | 状态改为 thread_local，归档线程各自拥有缓冲区 |
| 加密列表遗漏顶层目录，只收录其子项 | 先收录目录，保留 Android 目录标记；混合备份的明文计数累加 |
| 未使用线程生成的空 tar 被当成错误密码；遇到空缺线程号就终止扫描 | 接受有效空 tar，扫描并等待实际存在的线程组 |
| 分卷允许超出两位序号，路径中的 `%` 被当成格式串 | 每线程最多 00–99，共 100 卷；超过范围失败。路径作为格式参数处理 |
| waitpid 被信号打断或目标不是子进程时可能误报 | 重试 EINTR，核对 PID、退出状态与信号；无效/已回收子进程返回失败 |

tar 写出结束后会检查 close、编码器退出和输出文件 fsync；失败不会由上层发布成功 `.info`。恢复中途失败可能已经修改目标文件，不能回滚已写内容。恢复的子进程组归属复用 `BackupProcess`，但没有据此宣称完整恢复界面取消流程已完成。

## 实际执行范围

[测试驱动](../tests/archive_pipeline_test.py)编译完整生产 `twrpTar.cpp`、`tarWrite.cpp`、OAES、InfoManager、排除列表和 15 份 libtar C 源；编译仓库 pigz，链接实际 BoringSSL。TWFunc 的类型识别、密码探测、AES 包装及 wait 函数体也来自生产源码。

[46 项报告](../logs/archive-pipeline.json)全部通过。测试在独立临时 chroot 内创建源文件、归档，再删除源目录并恢复，逐字节比较内容，同时检查模式、相对符号链接和目录 `user.default` 标记。ASan/UBSan 启用；已有 libtar 扩展元数据分配清理问题另列待办，LSan 未启用。

- 普通 tar、gzip、AES、gzip+AES，分别覆盖正常文件、空归档和分卷。
- 混合明文/加密、多线程组及线程号间隙；路径含 `%`；分卷序号溢出拒绝。
- gzip CRC 损坏与截断、AES 截断、错误密码、tar 结束块后非零数据、缺失 pigz、随机源缺失或不足、源目录不存在。
- 真实子进程退出/信号/EINTR/非子进程错误；两线程交错写缓冲区；管道分段、读取中断、真实截断和无效 fd。

[旧代码对照](../logs/archive-pipeline-before.json)使用同一测试源码，46 项中 31 项失败。加密路径超时和并发缓冲区错误均作为失败保留；超时清理只通过 pidfd 定位 cwd 属于当前私有夹具的进程，不向任意主机 PID 发信号。失败用例数量不等于独立缺陷数量。

实际混合分卷回放曾暴露[短读失败](../logs/archive-pipeline-short-read-failure.json)。新增回调独立测试通过后，完整回放又发现恢复入口尚未连接回调，[失败记录](../logs/archive-pipeline-unwired-read-failure.json)保留；最终 46 项报告对应全部恢复入口已修正的源码。

## 夹具替代与尚未完成

| 边界 | 本组做法与限制 |
|---|---|
| 分区与 GUI | 临时主机目录；挂载、UI、进度接收、默认标签设置是替身，没有完整 RunBackup/RunRestore 管理器会话 |
| 分卷尺寸 | 测试阈值 64 KiB；正式配置仍为 1.5 GiB，本组未写满真实大卷 |
| 加密 | OAES/BoringSSL 在主机真实执行；不涉及 ARM64、MiTEE、FBE、RPMB 或 UFS wrapped-key |
| fscrypt | provider 返回无策略，不证明合成加密卷或实际 fscrypt 映射 |
| 随机源 | 夹具文件装入主机随机字节；缺失和短输入专门注入，不是手机熵源验证 |
| 文件属性 | 检查内容、mode、链接及 Android 目录标记；任意应用 xattr、最终目录时间、SELinux/capability 错误和稀疏空洞仍待补 |

旧 OAES CBC 格式没有认证标签。本次错误检测不等于能检测所有密文篡改，也不能证明最后一个完整分卷及其 sidecar 一同消失时仍可发现；需要另外的可信完整清单/校验设计。不能把“错误密码用例被拒绝”说成格式已经获得完整认证。

仍待补：完整管理器与 GUI 端到端、真实进度、digest sidecar 原子发布、进程死亡/断电后的整份备份完整性、完整归档路径约束、FlashImage/repacker 独立取消路径。其他分层证据见[备份会话](BACKUP-SESSION-ADAPTATION.md)、[恢复预检](RESTORE-SESSION-ADAPTATION.md)和[元数据恢复](ARCHIVE-RESTORE-ADAPTATION.md)。

复现：

```bash
python3 tests/archive_pipeline_test.py
python3 tests/archive_pipeline_test.py --source backups/archive-pipeline-pre-fix --report logs/archive-pipeline-before.json
```

第二条是负向对照，预期返回非零。不得将其用作刷机或物理盘操作。

短读修正后另外重复四类加密分卷回放五轮，共 20 次通过：[第 1 轮](../logs/archive-pipeline-repeat-1.json)、[第 2 轮](../logs/archive-pipeline-repeat-2.json)、[第 3 轮](../logs/archive-pipeline-repeat-3.json)、[第 4 轮](../logs/archive-pipeline-repeat-4.json)、[第 5 轮](../logs/archive-pipeline-repeat-5.json)。
