# MTP Reset检查点的交付与证据状态（历史）

此页保存046ab9e3检查点。本轮已由[摘要发布候选](DIGEST-PUBLICATION.md)替代：7f4c4293/736份生产来源、224项绑定126匹配/78漂移/20无充分绑定。下文“当前”均指当时检查点，不是要求使用旧镜像。完整任务继续进行中。

日期：2026-11-12。本页区分当前镜像、历史检查点与未满足的验收要求，不代替功能验收。

当前镜像为 `imgs/built/recovery-dijun-unified-mtp-reset.img`，SHA-256 为 `046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27`。本轮未修改生产代码、设备树或重建镜像。735份生产文件、固定仓库基线、生成设备树、构建日志和配置与原镜像一致，见[总审计本轮输出](../logs/unified-current-after-refresh.log)第一项。

## 本轮重新执行的检查

| 检查 | 当前镜像结果 | 边界 |
| --- | --- | --- |
| 固件/恢复进程二进制策略 | [12项通过](../logs/current-haptics-policy.json) | libsepol查询，不加载策略，不证明驱动或电机 |
| USB辅助进程二进制策略 | [53项通过](../logs/current-usb-policy.json) | 允许与拒绝决策，不证明UDC或MTP传输 |
| init文件 | [5份通过](../logs/current-profile-init.json) | 实际host_init_verifier语法与静态触发条件，不运行Android init |
| profile激活 | [9组、102次阶段调用通过](../logs/current-profile-runtime.json) | 从当前镜像提取脚本/资源；挂载、模块、属性、Binder为私有夹具 |
| 模块状态 | [4组、24次阶段调用通过](../logs/current-module-state-recheck.json) | live等待、依赖拒绝、避免重复插入；不执行内核module_init |
| 旧模块脚本负向对照 | [同一新夹具仍14项失败](../logs/current-module-state-before.json) | 检出旧状态判断缺陷，不是手机故障复现 |

首次对当前镜像重跑模块检查出现4项失败，保留[原始输出](../logs/current-module-state.log)。原因在测试夹具：共用sleep计数混入新增触摸报告等待；模拟insmod把触摸成功当成可选震动加载的必要条件。现已按父脚本区分等待计数，将顺序约束修正为“触摸已经尝试”，保留触摸优先并允许失败后的独立震动闭包继续。模块状态组的震动input注册由夹具显式立即提供，避免另一项轮询改变模块等待预算；不是实际input注册或震动恢复证据。

完整profile组也以同一镜像重跑，覆盖六份精确档案与两个槽位。未通过修改预期等待次数或放宽生产模块状态检查消除失败。旧脚本14项失败保留，生产脚本及镜像字节未改。

## 全量证据仍不满足当前绑定

修正索引前，[总审计](../logs/unified-current-diagnostic.log)在旧镜像激活报告处停止。simulation-report.json的五个主要当前镜像入口已指向本轮真实重跑结果，原入口保存在delivery_evidence_refresh.previous_check_bindings。总审计不再硬编码早期激活报告，而从该索引读取。

修正后，总审计通过当前生产来源与镜像绑定、当前profile/策略/init入口绑定，随后在历史module-state-review.json绑定的旧测试摘要处失败。**全量审计仍失败。**没有修改历史摘要、移除失败门槛，或将定向通过写成全量通过。

[完整索引绑定清单](../logs/evidence-freshness-current.json)扫描222项主/附加证据：124项所查摘要匹配、78项存在源码/测试/产物绑定漂移，20项没有足够结构化绑定。历史报告可以是当时有效的证据；这些数字表示不能将其直接移作当前镜像证明，不表示78个功能发生回归。缺失现场文件保持为缺失，不伪造或重建为手机证据。主任务/模拟报告/震动记录中的7处失效链接已保留原路径并明确标注缺失，包括早期module-state镜像及来源文件和原始用户日志包；没有把旧文件重命名为当前产物。

清单核对索引文件摘要、报告image_sha256及支持的源码/测试/头文件/模拟器/LVGL依赖映射。它不重算用例断言、不检查所有独立摘要字段、无法证明报告覆盖全部依赖，也不评价测试是否足以证明功能。matched仅表示所查绑定匹配；文本日志、未知映射或缺少依赖保持unbound。存在漂移/无绑定时返回非零。10项私有目录回归覆盖内容篡改、替换镜像、缺文件、嵌套依赖、文本日志和错误映射，见[回归日志](../logs/evidence-freshness-test.log)。

## 仍需解决的功能

震动、OS4自动触摸/唤醒和设置现场故障均未解决；原任务12组未完成项不变。尚未收到设置点击现象与既有震动只读采集结果，不重复索取同批采集。确认原厂存在设备校准恢复而Recovery缺少该步骤，但实际persist值/读回未知、不同芯片q支持不同，暂不新增校准写入或切换波形、增益、PCM。已有43次真实播放日志不能替代电机输出证明。

下一步按清单核对当前必需证据与历史范围，补足完整启动/GUI/存储流程缺口；有设备自身校准/寄存器读回后再判断恢复流程对现场故障的意义。不得通过更换旧镜像、只更新摘要或删除验收要求处理审计失败。

可复现命令：

```bash
python3 tests/profile_runtime_test.py --image imgs/built/recovery-dijun-unified-mtp-reset.img --output logs/current-profile-runtime.json
python3 tests/module_state_test.py --image imgs/built/recovery-dijun-unified-mtp-reset.img --output logs/current-module-state-recheck.json
python3 tests/module_state_test.py --script backups/module-state-pre-fix/dijun-runtime.sh --output logs/current-module-state-before.json
python3 tests/evidence_freshness_test.py
python3 scripts/audit_evidence_freshness.py --output logs/evidence-freshness-current.json
python3 scripts/audit_unified_delivery.py
```

后两项当前应非零；旧脚本负向对照也应非零。失败不能当成工具执行成功。
