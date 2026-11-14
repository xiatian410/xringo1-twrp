# 当前交付与验证范围

状态：**本轮有限离线任务收尾，转入维护；完整设备功能仍未验收**。三个工作包的处置见[工作队列](docs/WORK-QUEUE.md)，六样本声明与限制见[兼容矩阵](compatibility-matrix.md)。旧十二组分类和逐批检查不是当前待办。

## 当前候选

| 项目 | 值 |
| --- | --- |
| 文件 | `recovery-dijun-unified-cli-results.img` |
| SHA-256 | `edbe45e627cc5582e36d210613b4eaf016721bfc77bcda9ac543290cec085f96` |
| 生产来源绑定 | 876 份 |
| 固件档案 | 六份 OS2 / OS3 / OS4 精确 profile |
| 镜像 / 压缩 ramdisk | 104857600 / 76679139 字节 |
| 构建 | `installclean` 后 `make -j$(nproc)`，30 并发 |
| 发布方式 | 镜像仅保留本地；GitHub 同步维护源码、补丁、测试和文档 |

最后生产修正为 0138：CLI 执行失败传到后台完成记录，修正空命令、缺回调及解密后缓存脚本路径。此后原客户端 / 私有 FIFO / 监听器 / ORS 解析器同次接续十场景通过，失败后同一 server 的第二个请求仍可执行。分区、解密、配置和完成 sink 为显式替身；客户端退出码仍不能表示远端命令失败。详见[接续范围](docs/OPERATION-FEEDBACK-ADAPTATION.md#cli-ors-joined)。

## 本轮收尾（2026-11-15）

| 工作包 | 处置 | 仍然成立的边界 |
| --- | --- | --- |
| OS4 触摸启动 | 已核对 cache → modules → 普通报告顺序，未确认新的软件修复点 | 当前候选控制器响应、真实事件进入 GUI、唤醒未验证；没有新补丁 |
| 容量刷新画面 | 原采集摘要一致；当前 DONE 发布/轮询和同步显示提交链已对照，调查结束 | 后台不超过 5147ms 已结束；采样有 DPU 配置等待，但持续时间、因果和现场根因未定位，未宣称修复 |
| 兼容与仓库 | 六样本的同镜像范围、依赖、功能限制和文档已整理；本批发布检查同步 GitHub | 文档整理不变更生产源码、原厂资产、固定补丁或镜像；不证明全部设备功能正常 |

当前候选一次定向收尾核对确认：876 项生产来源摘要一致，六仓库固定补丁可从各自基线重建，维护树与生成树相同；镜像中的六份 profile、78 个去重资源、运行脚本及 recovery/twrp/GUI/显示库与记录匹配，封装符合六份原厂 recovery 布局和容量。既有构建日志包含清理和两次成功的 make。结果在本地 `logs/maintenance-closeout-inspection.json`；公开摘要见 [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。这项来源/封装检查没有重跑功能套件、整包模型或构建。

历史六样本/两槽位激活回放只复用未改变的选择器和主运行脚本结论。触摸报告脚本后来改变，不能把旧回放改称当前镜像完整执行。既有 GUI 主循环报告也保留旧来源，仅辅助当前调用链判断；历史全量审计仍有来源漂移，不声明所有旧检查均对当前字节通过。

## OS4.0.4 完整 ZIP：已做过什么

用户提供的原始完整包已完成一次 **MODEL_SUCCESS**：整包签名、原安装父进程、真实 ARM64 更新引擎、十份 COW 的分配与初始化、4933 个 payload 操作、42 个最终分区哈希、原厂 Recovery postinstall 分支与完成状态，在同次文件模型执行中接通；引擎与父安装器均成功退出。

该报告绑定运行时的 0090 候选和来源，不是当前 0138 候选重新执行。后续文档/无关实现未触发重复整包运行。源 LP 是合成输入，内核映射、挂载、HAL、槽位、proc 和部分清理为明确替身，scratch/daemon 未运行；真实设备安装、启动及重启合并仍未验证。原报告与历史覆盖限制见[完整包模型](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success)。

## 已关闭与仍未验证

- OS4 震动由用户确认正常；backup-manifest 基线设置正常。结论不转移到所有版本，不例行重查。
- 温度避让中央摄像头、加载页 `XRING O1`、NV 普通界面限制、刷入目标点击/确认链和 UFS 被误认 OTG 的有限修正已交付；没有新回归不重开。
- MTP 保留已交付修正并冻结；暂停前未验证的目录同步实验未进入当前候选。Windows/真实端点、崩溃暂存回收等限制保留。
- 当前仍有一项未定位现场问题：容量刷新画面停留。自动触摸、TEE/RPMB/wrapped-key、真实 USB、完整启动/LP/快照合并、完整备份恢复与断电/性能等范围均未获完整验收。
- CLI 远端退出状态协议、并发暂存和完整进程/USB 停止等未实现或未验证边界见兼容矩阵，不改写为完成，也不由旧测试数量自动派生任务。

代理没有连接手机或操作物理块设备，不修改 AVB/vbmeta。离线代码执行、设备替身、历史用户观察和当前镜像来源核对分别记录。

## 证据与维护入口

| 内容 | 入口 |
| --- | --- |
| 六样本可声明范围 / 功能边界 | [兼容矩阵](compatibility-matrix.md) |
| 当前任务状态 / 重开规则 | [工作队列](docs/WORK-QUEUE.md) |
| 公开离线结果与本批摘要 | [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json) |
| 历史机器索引 | [simulation-report.json](simulation-report.json) |
| 逐批实现和历史候选 | [历史交付记录](docs/archive/DELIVERY-HISTORY.md) |
| 固定补丁 / 构建和维护 | [构建指南](docs/BUILDING.md) · [维护指南](MAINTENANCE.md) |

机器索引的历史 `status=in_progress`、十二组缺口和旧来源保留，用于表示长期完整功能未验收。当前有限执行状态读取 `execution_status` / `execution_queue`；历史“下一步”不覆盖当前队列。本地 `logs/`、`imgs/`、原始固件和私钥不公开上传。
