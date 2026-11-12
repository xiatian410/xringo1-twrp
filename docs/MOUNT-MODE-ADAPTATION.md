# system/vendor 挂载模式事务

2026-11-12，维护补丁 `0034-mount-mode-transaction.patch` 修正 `gui2/backend/twrp_mount_backend.cpp` 的 `mountsystemtoggle`。旧代码只卸载 system，直接修改仍挂载 vendor 的模式；忽略重新挂载失败，并用后续 vendor 分支覆盖前面的失败。无独立 vendor 也会误报失败。它是挂载模式切换缺陷，不是一般设置保存或物理震动故障的根因结论。

新实现由现有递归操作锁串行化，先查找必需 system 和可选 vendor，保存各自挂载状态及只读策略。所有原本挂载的目标先卸载，然后修改策略，并只重新挂载原本已挂载的目标。全部成功后才提交 `tw_mount_system_ro`；失败返回非零，并尝试恢复原策略与原挂载状态。失败不会被其他分区成功覆盖，operation_end 接收失败状态，返回前刷新分区快照。

回滚也可能失败：重新卸载失败时保留该目标当前策略标志，不能把仍以新模式挂载的目标伪装成旧模式；恢复挂载失败则保留未挂载状态。均有独立日志，并保持操作失败、全局设置不提交。这不是对真实 mount flags 的重新探测，也不是不可失败的原子内核操作。

[执行程序](../tests/mount_mode_test.py)提取真实生产函数，以分区与 DataManager 边界替身覆盖读写/只读、已卸载、只有 vendor 已挂载、可选 vendor 缺失、system 缺失、两个卸载失败、两个 remount 失败、两种回滚失败、非法参数、重复调用和混合原模式。真实递归锁、ASan/UBSan 和宿主编译执行；不访问设备、块设备或执行 mount。[新实现 15 项通过](../logs/mount-mode.json)，[相同用例旧实现 8 项失败](../logs/mount-mode-before.json)。不是 8 个独立缺陷。

交付候选 `recovery-dijun-unified-mount-mode.img`，SHA256 `848096d4b42b41926e2741ba4a34ef1ec4922aaa66036281724e7a2d65b652f1`。installclean + make -j$(nproc)（30并发）构建，717 个来源文件及打包/新二进制核对通过；同镜像 profile 回归结果单独记录。第一次目标编译发现替身错误接受 `UnMount` 名称，已按真实 `Unmount` API 更正并重跑清理构建，失败日志保留。

入口为“挂载”页的 system 读写切换，按现有只读警告确认；动态分区设备可能隐藏该控件，启动只读选择也复用此后端。真实启动选择对返回值的界面展示、完整页面异步体验、真实内核文件系统挂载及用户现场状态仍未验证。没有改 AVB、vbmeta、校准或震动参数。全部任务保持进行中。
