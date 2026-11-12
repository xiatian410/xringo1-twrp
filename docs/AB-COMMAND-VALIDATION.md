# A/B OTA 命令准备与失败收尾

维护补丁 0062 修正 `abupdate_binary_command` 在 `payload_properties.txt` 提取失败时返回 `false`（数值 0，即 `INSTALL_SUCCESS`）的错误。调用者之前可能因此使用空参数启动子进程。现在返回 `INSTALL_CORRUPT`，失败不发布残留命令；`Run_Update_Binary` 也在 fork 前拒绝成功码配空命令的生成器结果。

更新器使用 ZIP 文件与条目的原始偏移直接读取 payload，不做 ZIP 解压。因此命令准备必须确认 `payload.bin` 为 stored、长度非零、压缩长度等于原长度，且偏移/长度在包范围内。新增这些检查，偏移以明确的 64 位格式输出。properties 为空或含 NUL 时拒绝，避免 argv 截断 headers；正常 deflated properties 仍可解压并接受。不替代 update_engine 对 payload 格式、hash、签名、manifest 或设备更新策略的验证。

`tests/ab_command_chain_test.py` 执行原始 metadata 解析、设备/序列号/增量来源匹配、包映射、真实 AOSP ZIP 查询和解压、命令准备、`Run_Update_Binary` 的 pipe/fork/协议/wait。只在 execve 边界将 update_engine 可执行文件替换为无害主机程序，原 argv 保留；它按真实 ZIP 偏移读取并逐字节验证 2052 字节临时 payload，检查 headers、fd 和进度，返回成功、退出 7 或非法协议，不做更新。

21 场景通过：stored payload、deflated properties、压缩/空/缺失 payload、损坏/空/缺失/含 NUL properties、残留命令清除、metadata 缺失/设备/序列号/来源增量/指纹/OTA类型不匹配、无效/缺失 ZIP、子进程失败/非法进度及空生成命令。所有拒绝场景检查 fork 次数为零；已启动子进程核对回收。修正前同组 8 场景失败，其余拒绝行为沿用原策略，不把全部 21 项记作新缺陷。普通 ZIP 安装 36 项回归通过。

范围：测试父进程和无害更新器均为主机执行；属性和进度为明确替身。未调用真实 update_engine、未运行原厂 OTA payload、未写分区，未包含完整 GUI/ARM64 Recovery/USB/FUSE/快照更新生命周期。原厂 OS2/OS3/OS4 的完整安装兼容仍未验收，整体 12 组任务保持进行中。

最终候选 `recovery-dijun-unified-ab-command.img`，SHA256 `704b58f5e97563ba9747bbf3c8d0129b83e1233581dec2941d837dfb704aceeb`。最终 installclean 后以 `make -j$(nproc)` 30 并发编译，保留 `XRING O1` 加载页显示与 0060 分区操作限制；六 profile 封装通过。本地报告 `logs/ab-command-delivery.json`，公开仓库发布源码/测试/文档与摘要，镜像及原始日志不上传。
