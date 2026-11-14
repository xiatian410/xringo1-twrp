# 工作队列

本文只记录当前优先级和未完成边界；历史测试流水账不再作为执行队列。目标见 [ADAPTATION-GOALS.md](../ADAPTATION-GOALS.md)，候选与交付见 [simulation-report.md](../simulation-report.md)。

## 执行规则

- 工作范围不限于此前六组，按具体故障与实现决定排序，不因此开始全量重复检查。
- **OS4 震动已修好、用户确认正常，退出例行检查。** 仅新报故障或直接回归证据可重新打开。
- backup-manifest 基线设置正常的用户确认保留，没有新故障不重复诊断。
- 相同源码、输入和范围直接复用结果。必要检查通过就结束本批；不反复增加等价夹具或重编未改镜像。
- 只在离线环境操作普通临时文件；不连接手机或操作物理块设备。
- 每个连贯修改批次完成后同步 GitHub，镜像、原厂 blob、私钥和原始日志不公开。

## 优先事项

| 优先事项 | 已知情况 | 下一步与边界 |
| --- | --- | --- |
| 容量刷新页面停留 | 后台约 5.15 秒成功结束；338.12 秒采样时 `disp_commit_0` 在 `D` 状态等待 `dpu_kms_wait_for_hw_cfg_done`，Recovery 主线程另一个快照位于 DRM atomic commit | 现存采集没有第二个等待采样，也没有匹配的 DPU 配置超时 / 恢复事件，暂待新证据。仅收到新的相邻栈、提交 / 完成时间线或直接软件缺陷证据时继续；不再次扫描同一采集、不重跑 worker / DONE 夹具、不据单点修改 DRM。见[现场采样分析](REFRESH-STUCK-INVESTIGATION.md#现场采样)及[主循环范围](REFRESH-STUCK-INVESTIGATION.md#gui-loop) |
| OTA / A/B 安装入口与快照生命周期 | 修正模型 Cleanup 生命周期后，同次原始4.0.4整包真实分配十份COW、4933操作/42哈希、脚本/状态及父进程成功，24项断言通过 | 该命名软件接续缺口已关闭，不再重复整包。真实源LP/内核映射/挂载/HAL/scratch/daemon/槽位/启动合并仍为模型或未验证；后续按具体实现决定推进，见[成功运行范围](INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success) |
| 文件系统完整生命周期 | 清除错误传播、媒体保留、格式转换及 persist / and-sec / 非 FBE 媒体目录恢复已维护；标签初始化已有实际 ARM64 工具证据，分区工具页面 / 原 worker / 返回详情十个接续场景通过 | 这条页面交接缺口到此收尾，没有新增生产缺陷。manager / 挂载 / 加密 / I/O 与完整 GUI 仍有边界，不重复页面或工具检查。见[页面接续范围](PARTITION-ACTIONS.md#tool-page-worker-lifecycle)及[标签初始化范围](FILESYSTEM-TOOLS-EXECUTION.md#postformat-selinux) |
| 其他具体缺陷 | 触摸自动启动、安全服务、多用户、备份恢复和 USB 集成仍有缺口 | 按下表剩余边界及新证据排序，每批明确实现决定和结束条件，不启动全量重复审计 |

## 已维护事项的入口

这些事项不重新立项。生产修正、各阶段证据和剩余限制在所属主题维护；当前镜像以[交付报告](../simulation-report.md)为准。

| 事项 | 文档 |
| --- | --- |
| 刷入目标、NV 界面限制 | [分区操作](PARTITION-ACTIONS.md)：目标点击、确认滑块、`start_image` 参数与进度页路由已接合验证；manager 和实际写入仍按独立链路记录 |
| OTG / UFS 误识别、存储选择 | [挂载与存储](MOUNT-LIST-EXPLANATION.md) |
| 温度避让摄像头、状态显示 | [状态与 RTC](STATUS-ADAPTATION.md) |
| 加载页 XRING O1 名称 | [阶段交付记录](archive/BOUNDED-MAINTENANCE.md) |
| 离线格式化 / 修复挂载检查 | [文件系统工具](FILESYSTEM-TOOLS-EXECUTION.md) |
| 备份目录重命名 / 删除、摘要发布 | [备份会话](BACKUP-SESSION-ADAPTATION.md) |
| 日志导出错误传播、页面日志生命周期 | [操作反馈](OPERATION-FEEDBACK-ADAPTATION.md) |
| MTP 日期、原子上传、格式与会话 | [上传](MTP-ATOMIC-UPLOAD.md) · [对象](MTP-OBJECTS-ADAPTATION.md) · [控制与事件](MTP-CONTROL-ADAPTATION.md) |

## 仓库维护

README 只保留项目简介、状态、构建入口与导航；历史流水账在所属主题查询。重复说明合并后删除旧入口，无引用的一次性脚本删除，既有版本由 Git 历史追溯。保留固定补丁、构建依赖和独立技术记录；格式与同步规则见[维护指南](../MAINTENANCE.md#文档维护)。仓库整理不改变生产功能，不重编镜像。

## 完整目标的十二组剩余边界

这些是范围分类，不是重新启动十二轮检查。硬件 U 单独记录；不要为了关闭 U 无限制增加模拟。

| 组 | 剩余边界 |
| --- | --- |
| 1 触摸 | 最新候选已在模块/input就绪后请求普通报告；9项策略用例和镜像打包审计通过。用户此前手动 raw0 后观察到215条 input 事件；自动启动候选的控制器响应、事件、GUI及唤醒仍无证据，不标记修复 |
| 2 安全服务 / 解密 | 原厂服务初始化、真实 init / namespace / Binder / TEE、合成加密卷接续 |
| 3 多用户 | 0120修正侧载重启请求提前消费：GUI接收失败保留请求、支持重试及取消；23项及生命周期33项通过，旧四项失败，见[重启交接](INSTALL-CHAIN-VALIDATION.md#reboot-handoff-retry)。0124已预约GUI后台任务/FIFO CLI，见[任务准入](MULTIUSER-ADAPTATION.md#shutdown-admission)；0125已修正PTY直接shell后台回收及失败fd清理，见[终端回收](OPERATION-FEEDBACK-ADAPTATION.md#terminal-child-reaping)；终端后代/准入、直接ORS及完整USB停止仍未验收。0109已将GUI后台析构/线程等待移至最终intent/重启之前，并补齐无热插拔时CLI等待；四场景、CLI十二项及入口二十一项通过，此项收尾，见[任务收尾顺序](MULTIUSER-ADAPTATION.md#reboot-worker-drain)。0102双卸载失败、0101 HAL失败返回和0100存储忙入口保护沿用。父绑定工作资料协议、同步调用安全取消、终端/直接ORS及完整进程停止、完整MTP/USB关闭、真实 CE 驱逐 / 重挂载仍未完成 |
| 4 MTP | 0123补齐接收内部普通错误和分段首段写失败后的未读边界，285项通过，旧14项全部执行尾部删除命令；显式重连是替身、就地编辑不回滚，见[接收错误边界](MTP-ATOMIC-UPLOAD.md#receive-error-boundary)。0122修正上传提前失败后未读文件尾部被当作命令执行；271项通过，旧八项均删除了夹具文件。关闭会话后显式重连可上传，真实端点恢复仍未验证，见[未读尾部](MTP-ATOMIC-UPLOAD.md#upload-unread-tail)。0121已传播上传fchown/fchmod失败，停止接收/发布并保留原目标；对象263通过，旧四项均误报成功，见[上传权限](MTP-ATOMIC-UPLOAD.md#upload-permissions)。真实USB大流恢复仍未验证。0116已将创建也绑定原父目录fd，随机排他名称最多32次；对象257通过，旧四项创建前父目录替换全部失败，此项收尾，见[目录内创建](MTP-ATOMIC-UPLOAD.md#staging-create-at)。名称检查后竞争、就地修改与跨重启回收仍未完成。0115将上传发布/清理/同步绑定原父目录fd并拒绝已观察父目录替换；对象247通过，旧六项全部失败，此项收尾，创建前路径竞争已由0116修正，名称检查后竞争仍未完成，见[上传父目录](MTP-ATOMIC-UPLOAD.md#upload-parent-directory)。0114已拒绝活跃临时路径的已观察替换，发布/清理核对原inode并恢复外部普通文件可见性；对象241/移动复制48通过，旧8/12失败，此项收尾。检查后竞争、父目录替换及跨重启回收仍未完成，见[活跃路径身份](MTP-ATOMIC-UPLOAD.md#active-staging-identity)。0111已补齐文件/分段编辑数据头长度校验，协议错误关闭连接且不解析尾部，229项通过，旧27/31失败；此项收尾，不重复相同坏头检查，真实端点/客户端恢复及持久临时文件归属仍未完成，见[流式数据边界](MTP-CONTROL-ADAPTATION.md#streaming-data-boundary)。0104已修正元数据DATA类型/操作/事务/长度与短读EPROTO，198项通过，旧25/31失败；此项收尾，不重复同类报文检查，完整端点及客户端恢复仍未验证。0103已补齐命令声明长度与损坏EPROTO，167项 / 旧4/7失败，此项收尾；完整上传端点恢复仍未完成。0099已修正分段编辑的报文校验、短写/EINTR处理及响应计数，对象160通过，旧10/11失败；就地写入不提供回滚，完整错误端点排空未完成，此项有限修正收尾。0098 已补齐统一会话检查与关闭时编辑fd释放，对象149 / 转移48通过，旧实现22/23失败；此项收尾。0091遗留路径身份与目录显式日期收尾沿用，不重复。跨重启归属 / 回收、媒体元数据、客户端目录收尾及完整端点 / Reset / USB / Windows 集成仍未完成 |
| 5 备份恢复 | 0119修正嵌套挂载根普通/gzip单卷恢复多出祖先目录，路径24项及控制9项通过，旧2/10失败；分卷/加密原本正常，此项收尾，见[嵌套根路径](BACKUP-SESSION-ADAPTATION.md#nested-root-paths)。0118已将挂载根目录归档一次，保留mode/属主/时间/user属性并传播失败；根元数据24项及相关控制15项通过，旧10/10失败，此项收尾，见[根元数据](BACKUP-SESSION-ADAPTATION.md#root-metadata)。真实根fscrypt策略/特权属性/ACL及完整生命周期仍未完成。0117已传播容量扫描I/O错误，后台失败保留临时估算、同步与加密规划/最终统计拒绝不完整结果；扫描16/策略19/调用14/会话5/codec18/存储15通过，此项收尾，见[容量错误](BACKUP-SESSION-ADAPTATION.md#size-scan-errors)。真实挂载/fscrypt、分配块及完整并发源一致性仍未完成。0113已隔离每次BackupTar的锁定用户排除策略，解锁/失败重试不再污染基础列表；八项通过，旧五项失败，此项收尾，真实解密/归档/manager与GUI仍有边界，见[按次用户策略](BACKUP-SESSION-ADAPTATION.md#user-attempt-policy)。0112已修正重复/父子排除容量重复扣除，19项及codec8通过，旧7/19失败；此项收尾，I/O错误、路径别名/并发及分配块仍未完成，见[并集计量](BACKUP-SESSION-ADAPTATION.md#exclusion-union)。0110已修正排除普通文件/链接的逻辑容量，11项及codec8通过，旧6/11失败，此项收尾；读取错误、重叠排除、实际分配块和完整并发一致性仍未完成，见[容量范围](BACKUP-SESSION-ADAPTATION.md#exclusion-capacity)。0108已修正DT_UNKNOWN漏条目及属性失败继续成功，codec216通过，旧32/32失败；此项收尾，容量预估和完整并发源一致性仍未完成。0107已补齐目录读取/关闭错误与递归失败关闭，libtar111/codec184通过，旧3/4及21/32失败，此项收尾；容量估计/完整源一致性仍未完成。0106已修正缺密钥ENOKEY源被跳过仍报成功，保留普通文件打开错误传播且链接不打开目标；libtar107/codec152通过，旧4/6及4/12失败，此项收尾。0105已修正源文件最后一块读不足仍报成功，短读/EINTR重试及提前EOF/EIO传回父进程；libtar101/codec140通过，旧5/12及12/16失败，此项收尾，完整源一致性仍未完成。0092 已修正普通 tar 恢复时展开全零区的问题：恢复40 / codec50通过，旧实现9/10失败，此项收尾。0093 已补齐标签/capability错误到codec/fork的失败返回，恢复50 / codec62通过，停止重复该项。0094 已补齐跨分卷 / 工作线程 / codec 成功后的目录时间收尾及身份校验，codec84 / libtar50通过，旧20/22失败；此项收尾。0095已维护应用user属性往返与失败传播，libtar64/GNU读回和codec104通过；此项收尾。0096已修正恢复路径越界及已有链接风险，libtar79/codec116通过，旧11/15及12/12失败；此项收尾，不把并发路径替换或bind mount隔离记作完成。0097已修正字符/块节点创建失败后误报成功及修改已有文件元数据，libtar89/codec124通过，旧8/10和8/8失败；此项收尾，mknod为拦截边界。真实安全策略、特权命名空间/ACL、并发源一致性、真实根fscrypt策略、原始 extent 拓扑、完整 manager / GUI、内容真实性与断电持久性仍未完成 |
| 6 文件系统 | 分区工具页 / 原 worker / 返回详情交接已覆盖，manager 仍为替身；另以原 FormatData / WipeEncryption / metadata路由 / 后台run确认14项成功与失败终态，工具/挂载/合并/hook为替身，此接续收尾，无生产修改。GUI / manager / 工具同次完整格式化 / 写入 / 修复生命周期、真实挂载 / 加密与 I/O 收尾未完成。ext4 标签初始化及失败返回已有独立工具证据，见[Data结果接续](FILESYSTEM-TOOLS-EXECUTION.md#format-data-terminal) |
| 7 RTC | 完整 probe / hctosys、冷启动读失败、实际漂移；无证据不增加偏移 |
| 8 视频 | ARM64 codec / 显示影子帧接续、全分辨率与长期性能 |
| 9 OTG | 完整 manager / USB 接续、写入中移除；不重复 UFS 排除夹具 |
| 10 启动 / LP | 完整 ramdisk 合并、kernel / init / LP 启动；脚本回放不等同完整启动 |
| 11 温度 | 传感器精度 / Android 注册；温度已移至状态栏左侧避开中央摄像头，布局工作已交付，不重复同类布局检查 |
| 12 安装 / GUI / OTA | 0120已修正侧载重启交接失败后请求丢失，保留重试/取消；0124已完成GUI后台任务/FIFO CLI准入预约；终端/直接ORS、完整停止和真实USB仍未验收。原始 4.0.4 ZIP / 引擎 / 脚本 / 快照完成状态已在模型内接续；另有普通文件快照分配 / 初始化、两条原包操作写入 / 续写与失败清理证据；真实源布局 / 内核映射、完整接续 / 挂载 / 槽位与启动合并、完整页面及实际 USB / FUSE 侧载仍未验收 |

精确输入与历史结果保留在 `simulation-report.json`；当前简表见 [兼容状态](../compatibility-matrix.md)。
