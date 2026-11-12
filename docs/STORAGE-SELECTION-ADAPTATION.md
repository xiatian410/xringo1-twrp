# 存储选择的失败处理

维护补丁 `0035-storage-selection-failure.patch` 修改真实 `select_storage`：目标必须存在、标记为存储并且路径等于发布的存储根；可移除存储即使已挂载也刷新容量。刷新禁止再次尝试挂载，避免 `UpdateSize` 通用观察路径把挂载失败返回为成功。容量失败、刷新时设备消失或设置值提交失败均返回失败；本次新挂载会尝试卸载，原先挂载的目标保留。卸载恢复失败单独记录，不能声称状态已恢复。

满盘但容量可读的目标仍可选择，后续写入任务负责空间检查。内部存储继承原有挂载逻辑。GUI 发布的 `storage_path_` 是选择入口接受的根路径，子目录不作为存储设备提交。

[测试](../tests/otg_selection_test.py)抽取生产选择方法和真实 `TWPartition::UpdateSize`，执行真实递归锁和作用域清理；底层挂载、设备存在、statfs/df、容量与 DataManager 是替身。ASan/UBSan 下 15 项通过；[旧实现同组](../logs/otg-selection-before.json)12 项失败，这是场景数而非独立缺陷数。覆盖新挂载、已有挂载、失败回退、拔除窗口、无目标、非存储、子目录、满盘、df 回退、恢复卸载失败、内部存储和提交失败。没有执行 USB 发现、真实挂载或读写中拔除。

复现：`python3 tests/otg_selection_test.py`；旧实现使用 `--backend logs/otg-selection-before/twrp_mount_backend.cpp --report logs/otg-selection-before.json`。改变选择方法时同时运行 mount_mode_test、settings_persistence_test、nested_partition_path_test 和 settings_row_test；各测试的替身边界仍然适用。

交付 `recovery-dijun-unified-otg-selection.img`，SHA256 `aaa4b25c1bd58a0b61508288a479d824f38701c38d2ed606530b39c503181ef7`。installclean 后 `make -j$(nproc)`，30 并发构建，718 来源与封装/新二进制核对通过。继承设置整行点击和 persist 路径修正；这些改动不能证明用户这次设置故障已经消失，也不是物理震动修复。

同镜像验证收尾：9组/102次profile阶段调用通过，718份构建来源仍一致，设置交互20/保存21/路径31与挂载模式15回归通过；当前交付审计见 `logs/otg-selection-delivery.json`。硬件与完整12组验收仍未完成。
