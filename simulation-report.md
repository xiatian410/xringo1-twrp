# 当前交付与验证范围

状态：**适配进行中**。本文只汇总当前交付，不重复历史测试流水账。详细机器索引为 [simulation-report.json](simulation-report.json)，公开结果摘要为 [CURRENT-VALIDATION.json](docs/CURRENT-VALIDATION.json)。本地 `logs/` 与 `imgs/` 不在公开仓库中。

## 当前候选

此前目录时间五项证据沿用其运行时来源；本批没有重做目录时间设计。当前对象回归也覆盖该路径，真实客户端是否发送收尾请求仍未验证，见[目录收尾范围](docs/MTP-ATOMIC-UPLOAD.md#directory-finalization)。

| 项目 | 值 |
| --- | --- |
| 文件 | `recovery-dijun-unified-ors-input.img` |
| SHA-256 | `37a742613b87b818dd150cf32d5ef6c4c72eb969b20cac5d2fc060957d229f9f` |
| 生产来源绑定 | 870 份 |
| 固件档案 | 六份 OS2 / OS3 / OS4 profile |
| 构建 | `installclean` 后 `make -j$(nproc)`，30 并发 |
| 发布方式 | 仅本地保存镜像，GitHub 发布维护源码 |

## 本批生产修正：ORS 读取失败与超长命令边界

0134将脚本读取/关闭失败传回失败，防止误报成功及启动自动重启；超长命令在执行截断前缀之前被拒绝。合法511字节边界、EOF无换行、空文件/空行保留。原解析器/action读取边界28项通过，旧版16个故障场景失败、12项正常控制通过；相关命令58/缺参20/启动顺序9回归通过。

清理构建绑定870份来源及六profile，核对入口`python3 scripts/audit_ors_results.py --input`，见[读取边界](docs/PARTITION-ACTIONS.md#ors-input-boundaries)。私有文件/目录及stdio EIO注入，关闭返回为注入；manager/shell/UI/重启为替身。未验收完整GUI/FIFO状态、物理I/O时限、并发路径或ORS关机准入。完整OTA沿用已有结果。

## 沿用的 ORS 缺少参数不再崩溃

0133在`backup`选项、`set`名称复制前检查空参数，并识别空白分隔。缺少参数返回失败，停止后续命令及启动自动重启；正常备份/命名/设置空值与普通值保留。20项原解析器/action检查通过；旧版12项失败（8次空指针崩溃，4项误判成功）。因解析器变更，原命令58项和启动顺序9项回归通过。

清理构建绑定869份来源及六profile，核对入口`python3 scripts/audit_ors_results.py --arguments`，见[参数解析范围](docs/PARTITION-ACTIONS.md#ors-missing-arguments)。备份/manager、配置、console、sleep和最终重启为替身；未完成实际备份、完整GUI/FIFO退出码或直接ORS关机准入。完整OTA沿用历史结果，震动不例行检查。

## 沿用的电池统计与 Android Secure 清除错误传播

0132直接检查电池统计文件删除结果（不存在仍算成功），Android Secure 多目标清除在首个失败处停止，失败传回原后台FAILED状态。私有chroot文件及实际权限错误15项通过，同夹具旧版7项失败：5项误报成功、2项失败后仍继续下一目标。成功/缺失/链接控制路径保留，已删除内容不回滚。

清理构建绑定868份来源及六profile，核对入口`python3 scripts/audit_aux_wipe.py`，见[清除结果范围](docs/PARTITION-ACTIONS.md#aux-wipe-results)。挂载、配置、UI和executor为替身，未完成完整GUI/线程启动、真实挂载/fscrypt、并发及物理I/O生命周期。完整OTA沿用历史结果；本批没有重跑震动或无关功能。

## 沿用的恢复列表先验证归档再读取文件头

0131修正旧格式备份目录中`.win` FIFO使恢复列表等待的问题；先验证已知分区的整个单文件/分卷集合，再读取文件头。目录、链接、空文件及缺卷使本次列表失败并清空，不发布部分选项。正常旧备份继续支持。

原manager/digest/文件头探测及私有文件75项通过；同夹具旧版九项中六项失败，含两个FIFO超时，正常三个控制场景原本通过。清理构建绑定867份来源及六profile，核对入口为`python3 scripts/audit_digest_preflight.py --enumeration`，见[恢复列表验证](docs/RESTORE-SESSION-ADAPTATION.md#restore-list-validation)。挂载、UI、归档解压等为替身；没有完整恢复/GUI/解密或并发稳定性验收。完整OTA沿用已有结果。

## 沿用的脚本暂存失败保留源文件

0130检查ORS暂存复制和源删除的结果；失败保留原脚本、尝试清理临时副本，并传回失败。缓存暂存失败会停止启动action，不执行副本或自动重启，即使前一个脚本已成功。源已位于临时路径和正常成功路径保留。

23项原检查/复制/解析器/action及原CopyFile私有文件场景通过，同夹具旧版11项失败；顺序九项与单脚本58项通过。清理构建绑定866份生产来源及六profile，核对入口为`python3 scripts/audit_ors_results.py --staging`，见[暂存失败](docs/PARTITION-ACTIONS.md#ors-staging-errors)。挂载/故障/shell/重启为替身；不承诺断电、并发路径替换、完整关机准入或真实启动。未重复完整OTA。

## 沿用的多份启动脚本保留失败

0129修正启动action分别记录临时/缓存脚本成功、从而掩盖失败的问题。任一脚本失败立即进入结束状态并返回失败；第一份失败时缓存脚本不被消费，第一份成功但第二份失败时不再自动重启。已完成操作不回滚。

临时/缓存脚本各取不存在、成功、失败，九种组合通过；同夹具旧版四项失败。原单脚本58项回归通过。清理构建绑定865份来源及六profile，核对入口为`python3 scripts/audit_ors_results.py --sequence`，见[多份启动脚本](docs/PARTITION-ACTIONS.md#ors-startup-sequence)。缓存发现、manager/shell及最终重启为替身；没有完成ORS关机准入或真实启动验收，不重复完整OTA。

## 沿用的 ORS 操作失败停止脚本

0128将清除、格式化、挂载/卸载及shell命令的失败结果传回ORS解析器，失败即停止后续命令；启动脚本入口不再因误判成功而自动重启。System清除失败也不执行后续详情刷新。成功路径与命令别名保留，不回滚此前完成的操作。

完整原解析器/启动action在私有脚本中58项通过，相同夹具旧版30项失败；manager、shell和最终重启为替身。清理构建、864份生产来源及六profile封装核对见`python3 scripts/audit_ors_results.py`，具体范围见[ORS错误传播](docs/PARTITION-ACTIONS.md#ors-command-results)。不宣称完整GUI、FIFO退出码、ORS关机准入或实机操作完成；完整OTA复用历史原包模型结果，没有重跑。

## 沿用的终端重启入口与最终回收

0127将PTY启动/写入接入短期任务准入，重启预约后拒绝新shell或命令输入，并把启动失败传回完整engine/GUI adapter。GUI最终退出及adapter析构等待直接shell后台回收；普通stop保持非阻塞。准入五项、完整engine/adapter五项和原回收七项通过，同夹具旧owner四/五项失败。

清理构建、863份来源及六profile打包核对通过，详见[终端最终退出](docs/OPERATION-FEEDBACK-ADAPTATION.md#terminal-shutdown-boundary)，核对为`python3 scripts/audit_terminal_shutdown.py`。不保证所有后台后代、直接ORS/USB停止、物理I/O时限或完整页面/Android shell；无关完整OTA沿用历史结果。

## 沿用的恢复摘要读取限制

0126修正旧备份摘要被替换为FIFO时恢复预检阻塞的问题。摘要使用非阻塞打开，核对已打开对象为普通文件，限制文件大小和实际读取总量为64KiB；非法摘要明确失败。缺少摘要的旧备份仍警告后兼容，指向普通摘要文件的链接仍可读取。

恢复链66项通过；同夹具旧版七个新增故障场景全部失败，其中五项FIFO读取超时。第二分区预检失败时，所有目标文件保持未写入。清理构建及六profile打包通过；详见[摘要读取范围](docs/RESTORE-SESSION-ADAPTATION.md#bounded-digest-sidecars)，核对为`python3 scripts/audit_digest_preflight.py`。不宣称内容真实性、并发源一致性或物理I/O超时已解决；完整OTA沿用历史模型结果。

## 沿用的终端子进程回收

0125修正PTY关闭后丢弃未回收shell的问题：GUI非阻塞关闭，由后台线程回收直接子进程并重试EINTR，回收前拒绝重开；同时关闭unlockpt/fork失败的master，子进程setup失败退出。七个私有PTY场景通过，同夹具旧版六项失败。清理构建及六profile核对通过，范围见[终端回收](docs/OPERATION-FEEDBACK-ADAPTATION.md#terminal-child-reaping)，核对为`python3 scripts/audit_terminal_reap.py`。

不宣称终端所有后代停止、完整任务准入或Android shell/真实重启完成。原整包OTA等无关路径不重跑。

## 沿用的重启交接任务准入

0124补齐后台任务已接收但尚未取得存储锁的空窗。GUI后台任务/槽位切换与FIFO CLI参与准入计数；无已接收任务时重启可预约停止接收，目标写入失败回滚，成功后保持至退出。取消/收尾保留，等待线程不持有存储锁。

启动29项通过，旧接线18/29失败；CLI16、入口21、侧载23、生命周期33、解密后台12、收尾4通过。含128次真实双线程预约竞争；任务内容、HAL/DM/USB及最终重启有明确替身。清理构建及六profile打包通过。核对为`python3 scripts/audit_shutdown_admission.py`，范围见[任务准入](docs/MULTIUSER-ADAPTATION.md#shutdown-admission)。终端/直接ORS、完整MTP/USB关闭及同步TEE安全取消仍未验收；完整OTA沿用历史结果。

## 沿用的接收失败后数据边界

0123补齐receiveFile内部普通错误及分段编辑首段写入失败后的边界处理：仍可能有文件数据或终止包未读时结束连接，避免尾部被继续当作命令。成功及ECANCELED/Reset保留原行为；小文件已完整缓冲的普通错误仍正常响应。分段编辑已写入内容不回滚。

主机生产对象链ASan/UBSan285项通过。同夹具旧版14个新增场景全部执行尾部删除命令并删除测试文件；修正后保留测试文件，清理临时文件/编辑fd，显式重连后可上传。覆盖新建/覆盖/分段编辑的ENOSPC、EIO、中途失败与终止包边界，以及分段首段零写/写入失败。历史11个接收失败场景改为期望断开，首次预期冲突报告保留。

清理构建绑定852来源及六profile；交付核对为`python3 scripts/audit_mtp_receive_tail.py`。USB/属性/取消排空和重连是替身，未执行真实端点、Windows或ARM64 MTP。详见[接收错误边界](docs/MTP-ATOMIC-UPLOAD.md#receive-error-boundary)。完整OTA沿用历史模型结果，未重跑。

## 沿用的上传提前失败后不解析未读数据

0122在SendObject本地准备或首段写入失败、未调用receiveFile且仍有数据/终止包未读时，关闭当前会话并清理上传，不将文件尾部继续当命令。小文件完全缓冲的错误仍返回普通错误。此修正不改变已经调用receiveFile后的传输错误处理。

主机生产server/database/storage、真实私有文件/inotify/线程及ASan/UBSan271项通过。新增八项在文件尾部放入合法删除命令，覆盖新建/覆盖各自chown/chmod/create/write失败；旧版八项均实际删除已有文件，修复版保留文件、尾部和排队命令未执行、清理临时文件，显式重连后可上传。四个历史原子失败场景更新为期望断开；首次预期冲突保留。

清理构建绑定851来源及六profile；核对为`python3 scripts/audit_mtp_upload_tail.py`。USB重连/属性为替身，不宣称真实Windows/ARM64 MTP、receiveFile内部错误、完整端点恢复或路径竞争已完成。详见[未读尾部隔离](docs/MTP-ATOMIC-UPLOAD.md#upload-unread-tail)。未重放未变整包OTA。

## 沿用的上传权限错误传播

0121检查MTP上传临时文件的fchown/fchmod结果，失败时停止接收和发布，关闭并清理本次临时文件，保留已有目标；删除不必要的全局umask切换。此前这两个系统调用失败仍可能返回成功并覆盖目标。

原server/database/storage及真实私有文件/inotify/线程在ASan/UBSan下263项通过，新增六项包含新建/覆盖的正常权限、属主设置失败、权限设置失败以及后续重试。同夹具旧实现四项错误均返回OK并发布新内容。清理构建绑定850来源与六profile，交付核对为`python3 scripts/audit_mtp_upload_permissions.py`。

USB/属性为替身，权限错误在系统调用边界注入；不代表ARM64 MTP、Windows或大数据流失败后的USB恢复已通过。临时名称检查后竞争及跨重启回收仍未完成。详见[上传权限](docs/MTP-ATOMIC-UPLOAD.md#upload-permissions)。未变OTA及其他功能复用证据。

## 沿用的侧载重启交接重试

0120让待处理的minadbd重启请求仅在GUI成功接收后被消费；目标写入失败或能力暂不可用时保留原请求及取消归属，后续可重试。此前先取走请求再发布目标，失败后请求丢失。

原侧载核心/GUI backend在私有主机进程、socket和epoll中23项通过，同夹具旧实现四项全部失败；相关生命周期33项通过。清理构建绑定849来源及六profile，交付核对为`python3 scripts/audit_reboot_handoff.py`，详见[重启交接重试](docs/INSTALL-CHAIN-VALIDATION.md#reboot-handoff-retry)。镜像变化仅构建属性、文件摘要及recovery程序。

USB、属性、FUSE、MTP、DataManager、能力和最终重启为替身；不提供从请求到最终关机的停止新任务预约，也未验收真实USB/BCB/完整GUI。历史完整4.0.4包运行沿用，不重复整包。

## 沿用的嵌套挂载根单卷路径

0119将单卷条目相对完整备份根保存，修正`/mnt/vendor/persist`等嵌套目录恢复后多出`vendor/persist`子目录的问题；分卷/加密原约定不变。24项路径场景及九项相关控制通过，同夹具旧版两项失败，其他八项原本正常。清理构建绑定848来源及六profile，核对入口为`python3 scripts/audit_backup_root.py --nested-paths`。

这是离线私有普通文件与真实host codec结果，真实挂载/fscrypt/完整manager/GUI及断电仍未验证。详见[嵌套根路径](docs/BACKUP-SESSION-ADAPTATION.md#nested-root-paths)。0118与完整OTA保留历史运行证据，不重复执行。

## 沿用的备份根目录元数据

0118补齐此前未归档的挂载根，空目录亦保留权限、属主、时间与user扩展属性。根条目只进入一个流；跨分卷和加密线程完成后沿用目录时间收尾，读取/写入属性失败传回父进程。根元数据24项及相关控制15项通过，同夹具旧10/10失败。清理构建绑定847来源及六profile，交付核对见`python3 scripts/audit_backup_root.py`。

原始tar/libtar/pigz/OAES及私有普通文件在ASan/UBSan下执行；UI/进度/fscrypt/安全提供者为替身。真实根fscrypt策略、特权属性/ACL、完整manager/GUI及断电未验证。详见[根元数据](docs/BACKUP-SESSION-ADAPTATION.md#root-metadata)。历史完整OTA结果复用，没有重跑整包。

## 沿用的容量扫描错误传播

0117为递归容量扫描增加完成状态，拒绝目录打开/读取/关闭、属性查询和取消后的部分结果；不存在的可选排除根仍正常计零。后台失败保留临时估算值；同步Data/secure扫描返回失败，加密线程规划与最终备份容量统计也传播失败，不发布完成摘要。

原扫描16项、容量策略19项、原同步/后台调用14项、备份会话5项、编解码18项及存储选择15项通过。旧扫描12/16、旧调用11/14失败；加密规划四项旧版仅关闭错误一项失败，其他错误原本已在后续阶段拒绝，不计作新增修复。清理构建、846来源及六profile核对通过。详见[容量错误传播](docs/BACKUP-SESSION-ADAPTATION.md#size-scan-errors)。这不解释DRM刷新画面等待；真实挂载/fscrypt、分配块估算、完整并发源一致性仍未完成，不重复整包OTA。

## 沿用的临时文件在原目录内创建

0116将已持有的父目录fd传至存储层，以openat排他创建随机临时文件；父路径在创建前被替换也不会重定向创建。随机读取错误安全失败，短读/EINTR有限重试，名称冲突最多32次且保留已有文件或链接。

原对象链ASan/UBSan257项通过；四个创建前父目录替换场景旧实现全部失败，新实现拒绝发布并清理原目录临时文件。另六项覆盖随机读取中断/短读/错误/零返回及单次/持续名称冲突。清理构建、844来源及六profile核对通过，详见[目录内创建](docs/MTP-ATOMIC-UPLOAD.md#staging-create-at)。名称身份检查后竞争、就地修改、跨重启回收及实际USB/Windows仍有边界；不重复未变整包OTA。

## 沿用的上传收尾绑定原父目录

0115在上传前持有父目录fd，发布前核对可见父路径身份；临时身份检查、发布/清理/同步使用原目录描述符，避免父路径被替换后重定向。原对象链ASan/UBSan247项通过，新六项父目录替换场景旧实现全部失败；清理构建、843来源及六profile核对通过。

详见[上传父目录](docs/MTP-ATOMIC-UPLOAD.md#upload-parent-directory)。0115当时保留的按路径创建问题已由0116修正；临时名称检查后竞争、就地修改及跨重启回收仍有边界。未改移动/复制48项沿用；未重复整包OTA、已解决功能或未变套件。

## 沿用的活跃上传文件身份修正

0114在MTP发布/清理前核对临时路径仍指向接收inode；发现外部替换时失败并保留原目标与替换文件。传输结束后重新协调父目录，让事件曾被忽略的普通替换文件恢复可见。原对象链ASan/UBSan241项及移动/复制48项通过；旧实现新增十二项中八项失败，四项路径消失控制本来正确。清理构建、842来源及六profile核对通过。

详见[活跃上传路径身份](docs/MTP-ATOMIC-UPLOAD.md#active-staging-identity)。这不是原子所有权或跨重启回收：检查后的竞争、父目录替换、就地改写和inode复用仍有边界。USB/属性为替身，未执行ARM64 MTP或Windows。本批没有重跑完整OTA或已解决功能。

## 沿用的锁定用户备份排除修正

0113将锁定次用户的排除目录限制在本次备份副本内，避免先前尝试或失败重试污染持久基础策略，导致解锁后仍漏备用户数据。执行原BackupTar/排除方法、私有文件及ASan/UBSan，八项通过；同夹具旧实现五项失败。清理构建后841来源及六profile核对通过。

详见[按次隔离用户策略](docs/BACKUP-SESSION-ADAPTATION.md#user-attempt-policy)。tar创建、挂载及用户状态是替身；真实解密/归档/完整manager与GUI仍有边界。检查了同步tar/Wait的副本生命周期；没有重跑未改OTA或已解决功能。

## 沿用的重叠排除容量修正

0112修正Data初始化重复登记及父子排除目录重复扣除容量：在局部列表去重，已计量目录覆盖的子路径不再累加，按路径组件边界区分相似前缀；原备份/清除排除策略不变。真实私有文件/完整exclude源码在ASan/UBSan下19项通过；同夹具旧实现7/19失败，相关codec八项往返通过。清理构建后840来源及六profile核对通过。

详见[重叠排除计量](docs/BACKUP-SESSION-ADAPTATION.md#exclusion-union)。这仍是逻辑字节估计，I/O错误、路径别名和并发源一致性等边界保留，不解释此前DRM刷新等待。不重复完整OTA或已解决功能。

## 沿用的MTP上传数据头与连接收尾

0111补齐SendObject/SendPartialObject数据头的声明长度校验，用64位加法处理32位长度饱和；类型/操作/事务错、短头、超额初始payload等协议错误在写入前拒绝，终止连接后由resetSession释放登记与编辑fd，不解析不可信尾部命令。正常I/O错误与取消仍按原路径处理，不把协议错误混作取消。

原server/packet/database/storage、真实私有文件/inotify/线程在ASan/UBSan下229项通过；同夹具旧实现新增31项中27项失败。另四项正常控制覆盖空文件及大/未知长度头，但大传输停在显式transport错误，不宣称完整GB传输通过。清理构建后839来源与六profile核对通过。详见[流式数据边界](docs/MTP-CONTROL-ADAPTATION.md#streaming-data-boundary)。真实USB、Windows自动恢复、ARM64 MTP和跨重启临时文件回收仍未验收；本批不按前缀删除用户文件，不重复OTA或已解决功能。

## 沿用的排除文件备份容量修正

0110修正容量扫描只排除目录的问题：`/data/adb/ksu/modules.img`等普通文件现在按排除策略跳过，绝对排除项的容量统计可计量文件及链接自身，不跟随目录链接或悬空链接目标。真实私有文件、完整exclude源码与ASan/UBSan下11项通过，同夹具旧实现6/11失败；普通/gzip/AES/组合编码及分卷八项往返通过。清理构建后838来源及六profile核对通过。

这项修正改善逻辑字节估计；I/O错误、重叠排除项、实际分配块和并发源一致性仍有边界，也不解释此前刷新页DRM等待。详见[容量排除策略](docs/BACKUP-SESSION-ADAPTATION.md#exclusion-capacity)。没有重跑未改的整包OTA或已解决功能。

## 沿用的最终重启前等待后台任务退出

0109调整GUI后台生命周期：已接收任务的析构/线程等待先完成，再执行最终intent及重启；background stop即使没有热插拔线程，也等待CLI退出。原作用域/七个析构函数及stop在真实主机线程与锁、ASan/UBSan下四场景通过；旧main在两个正常退出场景失败，旧background四场景全部失败。CLI十二项、重启入口二十一项通过，清理构建后836来源及六profile核对通过。

构造、任务内容、GUI、控制器及最终重启仍是替身；不提供同步Binder/TEE安全取消、停止新任务预约或完整MTP/USB关闭保证。详见[任务收尾顺序](docs/MULTIUSER-ADAPTATION.md#reboot-worker-drain)。没有重复执行完整OTA；原始OS4.0.4整包的4933操作/42分区哈希及父安装成功属于历史snapshot-cow-init镜像的软件模型，不能替代当前候选或实际启动/合并验收，见[整包运行范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success)。

## 沿用的未知目录条目类型与属性读取失败修正

0108将普通递归及加密路径的两次顶层收集改为检查lstat后的类型/大小。DT_UNKNOWN不再静默漏文件或目录；符号链接不跟随目标，属性读取EIO/ENOENT立即传回父进程且不发布data.info。排除项先于属性访问，现有设备节点/特殊类型筛选保持。

扩展现有ASan/UBSan编解码链至216项全部通过；同夹具旧源码新增32项全部失败。成功往返检查文件内容/权限、目录、悬空及目录链接、排除路径；错误检查父失败和目录关闭。清理构建后835来源及六profile核对通过。目录类型及属性故障在私有文件夹具注入；容量估计、完整源一致性/manager/GUI、ARM64 codec和断电仍未完成。详见[源类型分类](docs/BACKUP-SESSION-ADAPTATION.md#source-type-classification)。沿用完整OTA与其他未改路径证据，不例行重跑。

## 沿用的目录读取错误修正


0107区分目录读取结束与错误，每次读取前清除errno；普通递归、加密两次顶层扫描和libtar递归均传播读取/关闭失败，递归失败关闭上层目录。父进程拒绝部分结果且不发布data.info，正常EOF不受前一操作残留errno影响。

现有ASan/UBSan套件libtar111、完整tar/pigz/OAES/fork链184项通过；同夹具旧实现分别3/4、21/32项失败。清理构建后834生产来源与六profile核对通过。系统调用故障限私有目录夹具，非真实文件系统损坏或ARM64 codec验证；容量估计、DT_UNKNOWN、完整源一致性/manager/GUI与断电仍有边界。详见[目录遍历错误](docs/BACKUP-SESSION-ADAPTATION.md#directory-enumeration-errors)。本批不重跑OTA、触摸或震动检查。

## 沿用的缺密钥漏备份修正


0106移除libtar的多余打开探测：此前遇到ENOKEY会直接跳过条目并返回成功，可能发布缺文件的备份。现在普通文件（含空文件）由实际内容读取函数打开，缺密钥/密钥撤销/权限错误传回父进程且不发布.info；符号链接与硬链接只归档元数据，不再因目标打开失败而漏掉。

现有ASan/UBSan套件libtar107、完整tar/pigz/OAES/fork编码链152项通过；旧实现新增六项中四项失败，编码链十二项中四项失败。打开错误在私有指定源路径注入；核对原errno、父进程失败和链接恢复inode/内容，不代表实际fscrypt/TEE验证。清理构建后833生产来源与六profile核对通过。完整manager/GUI、ARM64 codec、并发源一致性和断电仍未验证。

详见[源密钥失败](docs/BACKUP-SESSION-ADAPTATION.md#source-key-failure)。此前源短读、MTP和完整4.0.4 OTA模型按各自来源复用，本批不重新运行这些独立套件。

## 沿用的槽位切换前 Vendor 卸载失败

0102在Vendor普通卸载和MNT_DETACH都失败时结束操作并返回false，不再调用Boot HAL或发布新槽位。沿用0101的备份页错误与输入保留、重启确认页失败分支。既有槽位套件扩展到21项全部通过；上一版在后台 / 备份 / 重启三个卸载失败场景中失败。正常卸载、延迟卸载成功和无Vendor路径保留。清理构建后827来源与六profile封装通过。

HAL / 卸载 / DataManager / 导航为测试替身，没有真实挂载或槽位切换；延迟卸载成功不代表所有旧引用已释放。详见[卸载失败边界](docs/MULTIUSER-ADAPTATION.md#slot-unmount)。其他未改功能沿用原证据，没有重复整包或震动检查。

## 沿用的槽位切换失败返回

0101修正核心在Boot HAL缺失或拒绝时仍发布新槽位的问题：SetActiveSlot现在返回失败，不改内存槽位、DataManager或刷新分区详情；后台传播结果及失败状态。备份页失败时记录本地化错误并保留输入，重启确认页不会继续请求重启。槽位14项通过，旧实现9项失败；相关入口21 / 侧载20项回归通过。最终清理构建、826来源与六profile封装通过，详见[槽位失败传播](docs/MULTIUSER-ADAPTATION.md#slot-result)。

测试使用原核心 / backend / 回调，HAL / 挂载 / DataManager / 导航为替身，没有真实切换槽位或完整GUI验收。不改OTA引擎、触摸或震动；不重复整包安装检查。

## 沿用的存储忙时重启与槽位入口

0100 在重启请求和切换槽位入口非阻塞尝试存储事务锁：其他线程持锁时立即返回失败，不等待、卸载分区或修改重启参数。侧载待处理重启在取得锁后才领取，忙时保留，下一轮空闲轮询可正常交接。原 backend / 真实 mutex 与线程21项通过，旧实现9项忙时检查失败；侧载原核心与轮询20项通过。清理构建后825来源、六profile封装核对通过。

这是入口冲突修正：未实现同步 Binder / TEE 安全取消，也没有在请求返回到最终重启间保留停止新任务的预约。HAL、分区、DataManager、USB和最终重启为测试替身，不代表完整ARM64 GUI或设备验收。详见[多用户与重启边界](docs/MULTIUSER-ADAPTATION.md#storage-reboot-guard)。完整卡刷包证据继续复用，无重复执行。

## 沿用的 MTP 分段编辑写入

0099 在首次写文件前校验数据报文的类型、操作码、事务及声明长度，避免超长报文导致剩余长度下溢；短写和 EINTR 重试，零写与永久错误返回失败。成功响应返回总接收字节数，错误路径清空入站数据，避免将其作为响应发送。对象160项通过；同夹具旧实现新增11项中10项失败，空写控制通过。最终清理构建、824来源与六profile封装核对通过，详见[分段编辑写入](docs/MTP-CONTROL-ADAPTATION.md#partial-edit-write)。

测试执行主机生产server/database/storage与普通文件，USB/属性/日志为替身；编辑就地写入，失败前已有写入不回滚。完整端点排空、持久提交、ARM64 MTP及Windows仍未验收。本批没有重复整包OTA及已解决功能。

## 沿用的 MTP 会话与编辑状态

0098 在统一请求入口补齐会话检查：未打开或已关闭会话时拒绝文件操作；GetDeviceInfo / OpenSession 保留。关闭会话或操作码 ResetDevice 释放编辑fd与状态，class Reset / 断开共用释放helper。数据库handle与已写内容保留，不提供回滚。对象149项、转移48项通过，同夹具旧实现22/23失败。清理构建后823来源 / 六profile核对，封装仅MTP库、构建属性及摘要变化，详见[会话边界](docs/MTP-CONTROL-ADAPTATION.md#session-file-boundary)。

测试执行主机生产server/database/storage及普通文件，USB/属性/日志为替身；不代表ARM64 MTP、Windows或完整真实端点验收。本批未重跑整包OTA与已解决功能。

## 新增证据：Data 格式化错误到后台终态

针对 metadata 密钥分区清除失败是否误报成功这一缺口，执行原 `FormatData → WipeEncryption → WipeByPath → wipe/run`，14项成功和拒绝场景通过。核对阶段顺序、格式化后的状态及后台结果；metadata清除或后置hook失败发布FAILED，不执行成功脚本，合并检查拒绝不进入格式化。工具、挂载、mapper、合并检查及hook为明确替身，同步调用run，没有完整GUI/start/thread或真实加密格式化，详见[Data结果接续](docs/FILESYSTEM-TOOLS-EXECUTION.md#format-data-terminal)。

没有发现生产缺陷，没有新补丁或构建；当前0099镜像、SHA-256及824份生产来源不变。既有ARM64工具证据独立保留，不拼接成完整生命周期验收；此项有限检查到此收尾。

## 沿用的特殊文件创建失败传播

0097 修正字符/块节点创建失败后仍返回成功的问题。原实现会继续向已有普通文件应用归档权限和时间；现在保留创建错误并停止，错误传到codec/fork恢复父进程。libtar89项及codec124项通过；旧实现新增场景分别8/10与8/8失败，FIFO成功/失败控制正常。已清理构建并核对六profile及来源，范围见[特殊文件错误](docs/BACKUP-DATA-PATHS.md#special-file-errors)。

测试完全拦截mknod，只检查调用参数和失败返回，不创建字符/块设备节点；不代表目标内核成功创建设备节点或完整GUI/manager恢复验收。已有部分恢复内容不回滚。本批未重复整包OTA及已解决功能。

## 沿用的恢复路径约束

0096 将所选恢复根传给全部分卷工作线程，拒绝 `..`、越界绝对路径、现有符号链接父路径及越界硬链接目标；覆盖已有多硬链接普通文件时先解除当前链接，避免截断目录外共享内容。正常分卷的包内绝对路径格式保留。libtar79项、codec/fork/分卷116项通过，同夹具旧实现分别11/15与12/12失败。已清理构建并核对六profile封装，详见[路径范围](docs/BACKUP-DATA-PATHS.md#restore-path-boundary)。

这是已观察路径缺陷的修正；尚非基于逐层目录描述符的并发隔离，祖先目录并发替换、bind mount、完整manager/ARM64恢复和断电仍无验收。失败保留部分恢复内容。本批没有重跑OTA整包或已解决功能。

## 沿用的应用 user 扩展属性往返

0095 补齐应用 `user.*` 属性的采集、二进制 PAX 保存、读取与恢复。原实现只维护专用安全属性与三种 Android 标记，其他应用属性丢失。属性列表 / 值读取失败阻止备份成功发布，写入失败传到恢复父进程；空值和多块值保留，不把 Android inode 引用按旧数值复制。归档64项（含 GNU tar 独立读回）和完整codec104项通过；旧实现分别10/14及20/20失败。最终清理构建、819来源与六profile封装核对通过，详见[应用属性](docs/BACKUP-DATA-PATHS.md#application-xattrs)。

大属性使用多块PAX头，旧Recovery可能拒绝新备份；专有Android引用仍由原逻辑重建。此项不覆盖trusted/ACL等命名空间、并发源快照一致性或完整GUI/manager/断电验收。失败保留部分恢复内容。本批未重跑OTA、触摸、震动或MTP。

## 沿用的分卷和并行恢复的目录时间收尾

0094 记录已归档目录的时间与设备号 / inode，在全部分卷、工作线程及解码验证成功后统一恢复时间。原先目录头先设置时间，后续创建子文件将其覆盖。最终写入失败、目录被符号链接或其他 inode 替换时返回恢复失败。编解码84项和 libtar50项通过；同一新增夹具旧实现22项中20项失败，另两项确认损坏解码流不进入最终收尾。清理构建、814来源 / 六profile封装核对通过。详见[目录时间](docs/BACKUP-DATA-PATHS.md#directory-times)。

仅恢复归档中存在的目录时间，沿用 tar 秒级精度和 atime=mtime；未归档的挂载根不凭空补元数据。直接 libtar 调用未安装回调时维持旧行为；实际恢复入口已接入。没有真实挂载、ARM64恢复、完整GUI/manager或断电验收，失败不回滚。本批未重跑OTA、触摸、震动或MTP。

## 沿用的安全元数据失败不再误报恢复成功

0093 在归档 SELinux 标签或 capability 写入失败后保存 errno 并返回失败，原 libtar / codec / fork 链向上传递；原先只打印错误却继续成功。恢复50项、编解码62项通过；旧实现同夹具分别4/10与8/12故障场景误报成功。最终清理构建、812来源 / 六profile核对通过，相对0092仅 recovery、构建属性和摘要变化。范围见[安全元数据](docs/BACKUP-DATA-PATHS.md#security-metadata-errors)。

安全系统调用在测试中重定向到 user xattr，不代表真实 SELinux / capability enforcement。失败不回滚已经提取的内容；ARM64恢复、完整GUI/manager和断电持久性仍未验收。本批没有重复OTA、MTP、触摸或震动检查。

## 沿用的稀疏恢复修正

0092 保持普通 tar 格式，在普通文件恢复时跳过全零数据块，末尾零区用 truncate 保持逻辑长度。seek / truncate 中断重试、其他错误传播，逻辑进度保持原语义。主机恢复40项、编解码50项通过；同夹具旧实现10项中9项失败。最终清理构建、811来源 / 六profile核对通过，ramdisk仅 recovery、构建属性和摘要变化。详见[归档恢复](docs/BACKUP-DATA-PATHS.md#archive-restore)。

这会重建零区，不保留原始extent拓扑，也不引入GNU sparse归档格式。实际文件系统、ARM64恢复、完整GUI/manager和断电持久性仍未验收。本批仅验证相关恢复与编解码范围，未重跑OTA、触摸或MTP。

## 沿用的 MTP 遗留路径身份修正

0091 在临时文件创建时记录设备号 / inode，结束时记录 ctime；遗留路径消失、被替换或 ctime 变化后撤销旧隐藏登记，修改 / 关闭事件可发布原先未登记的新对象。不会按前缀清理或删除用户文件。对象121项、移动复制48项通过；同一夹具对旧实现的5项检查复现3项隐藏错误。最终清理构建、810来源与六profile核对通过，打包变化仅 MTP 库、构建属性和 ramdisk 摘要。详见[MTP上传](docs/MTP-ATOMIC-UPLOAD.md#staging-identity)。

跨重启归属 / 回收仍未完成，ctime也不能辨别所有同时间戳并发修改；没有真实USB或Windows验收。本批未重跑整包OTA、触摸或其他未变功能。

## 沿用的 OS4 普通触摸报告启动策略

当前候选在 Synaptics 模块进入 live、Xiaomi input 注册后等待2秒，再请求 `enable_touch_raw=0` 并核对软件缓存读回。9项私有文件策略用例和镜像打包审计通过；该策略当时绑定809项生产来源与六个 profile；本批沿用其未变字节。等待2秒是有限启动策略，不代表目标设备时序已测量，也不代表控制器确认切换。

用户此前手动写 raw0 后观察到215条 Linux input 事件。当前自动启动候选没有新的硬件运行证据，不能据缓存读回或策略测试宣称触摸已修复。OS4震动由用户确认正常，退出例行检查；设置在 backup-manifest 基线正常，也不重复诊断。

## 页面生命周期补充：镜像刷入目标

补齐刷入目标测试的交接范围：既有25项覆盖真实 `page_router/page_host` 目标点击、确认页 `REPLACE`、返回安装入口 `POP` 和再次 `PUSH`。新增确认链25项中，20项通过真实 LVGL 滑块手势调用生产 `install_confirmed`，逐项核对 `start_image` 收到的镜像路径、所选目标与双槽标志，并路由到进度页；另5项拖出取消。没有发现生产缺陷，因此没有源码补丁或新镜像。安装 manager 和块设备写入继续由独立40项 worker 链覆盖，但本次没有重复运行该链。详细边界见[分区操作](docs/PARTITION-ACTIONS.md)。

对当前候选镜像另以镜像内提取的 `twrp.flags` 重跑上述25项目标交互，全部通过；因此该候选确实带有五个 raw 刷入目标。此结果确认交付配置与点击路径，不能证明实机触摸采样正常。

## 本批证据：分区工具页面与后台接续

分区选项、确认 / 文件系统选择、原工具 worker、进度页与返回详情在同次主机回放中接通，十项通过。涵盖修复 / 扩容 / 格式转换成功失败、未选择、启动被拒后重试、确认前返回与重复进入。manager、详情和显示提交有明确替身，未执行真实分区操作或完整 GUI 主循环；没有发现生产缺陷，没有新补丁或构建。镜像与 809 份生产来源不变，范围见[分区工具页面接续](docs/PARTITION-ACTIONS.md#tool-page-worker-lifecycle)。

## 已有证据：ext4 标签初始化

扩展既有工具接续，实际执行当前镜像 ARM64 e2fsdroid：`/data` 与 System 根标签经独立 debugfs 读回确认，Android 分离规则选择及缺失 / 无效规则的失败返回五项通过；共用测试工具的原六项场景回归通过。首次夹具漏复制镜像已有的分离规则，失败保留，没有据此修改生产代码。镜像及 809 来源不变，无新增构建；真实挂载 / 加密 / 完整 GUI 生命周期仍未完成。范围与结果见[文件系统标签初始化](docs/FILESYSTEM-TOOLS-EXECUTION.md#postformat-selinux)。

## 历史交付：0090 COW 初始化失败不再崩溃

真实 ARM64 快照初始化测试发现：COW 头部 `fsync` 返回 I/O 错误后，`CreateCowWriter` 返回空指针，旧 SnapshotManager 仍调用 `Finalize` 并触发 SIGSEGV。0090 补齐空判断，返回原有错误路径并执行清理。新候选已按要求清理构建，809 来源与六 profile 封装核对通过。

正常、路径查询失败、头部同步失败三项定向检查通过；使用同一夹具和镜像库、替换为旧 SnapshotManager 的负向检查仅同步失败项崩溃。正常项真实初始化并解析十份空 COW，发布目标 LP，重建 manager 后持久化 Unverified 状态；两种失败均清除临时映射 / 状态、保持 Initiated，不误报完成。内核映射由独立稀疏普通文件代替，源 LP 为合成 32 GiB，HAL / kernel / ImageManager 为明确边界；测试模式关闭 scratch 和 daemon 启动。**没有重跑整包，不代表真实映射 / 挂载 / 槽位 / 重启合并验收。** 见[初始化与故障范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-initialization)，本地交付核对 `logs/snapshot-cow-init-delivery.json`。

## 整包接入真实分配：模型内成功，设备边界仍未验收

修正测试模型在Cleanup阶段释放controller后，原始OS4.0.4整包单次运行完成真实控制器/十份COW分配、全部4933操作、payload哈希、42最终分区哈希、原厂Recovery脚本、真实Unverified发布、模型槽位与卸载清理；引擎退出0/wait0、父安装器INSTALL_SUCCESS=0。24项断言通过，约881秒，详见[成功运行范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-success)。

这是模型生命周期修正和接续证据，无生产修改或新镜像。源LP/DM视图/readonly/挂载/HAL/槽位/proc等仍为明确模型，scratch/daemon关闭；未证明实机启动合并。已完成的整包不再例行重复。

## 历史：整包接入真实分配后的模型退出失败

同次原始 4.0.4 完整 ZIP 运行已移除预置分配状态与独立 COW 创建，执行真实控制器 PreparePartitionsForUpdate / SnapshotManager 初始化十份 COW，再由原 controller writer 执行全部4933操作、payload哈希与42最终分区哈希；原厂脚本 Recovery 分支、真实完成状态及模型槽位接续。约876秒后，在成功回调 / 完成标记后进程SIGSEGV，实际退出1，父安装器INSTALL_ERROR，**本次安装为FAILED**。

精确保存的同一适配器另做两项分配后退出探针：进程静态 controller 在main返回后复现SIGSEGV，main结束前释放则退出0，定位为模型生命周期问题，尚无生产缺陷证据。后续已修正模型所有权并取得上文成功结果；固定路径 runner 当时覆盖了旧失败原始报告，只保留旧摘要、适配器与文字结论，不能声称旧原始报告完整留存。此后 runner 已拒绝覆盖既有运行输出。真实内核映射 / 挂载 / HAL / 槽位 / scratch / daemon / 启动合并仍有替身，见[历史失败与保存限制](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-allocated-failure)。

## 分配到 payload 片段的交接证据

同一执行中，真实 SnapshotManager 创建的 COW 已交给原 `DynamicPartitionControlAndroid::OpenCowWriter → OpenSnapshotWriter → VABCPartitionWriter`，执行原始 4.0.4 `mi_ext` 前两条操作（REPLACE_XZ / REPLACE），4 MiB 读回与独立原厂分区切片一致。重新创建 manager / controller / writer 后从 label1 续写通过；损坏头部时 Init 拒绝，显式卸载映射后保持 Initiated，不发布完成。共三项通过，见[交接边界](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-payload-handoff)。

这是新接续证据，无生产修改或新构建。DM 基础分区 / COW 由持久普通文件视图替代，基础映射和 procfs realpath 有明确边界，测试模式关闭 scratch / daemon。只执行两条操作，没有整分区 / 全量 payload / 完成状态，不把它与历史整包运行合并为完整 OTA 验收；镜像仍为上表 0090 候选。

## 历史阶段证据

以下条目保留各轮执行时的镜像与边界；“无新构建”仅指该轮，当前候选以上表为准。

原控制器分配失败到回退接续新增五项：真实 `PreparePartitionsForUpdate → SnapshotManager → CancelUpdate → 直接 LP 准备` 在原始 manifest / 普通文件布局中执行；映射失败或空间不足会在取消成功后发布目标 LP，取消 fsync 失败则停止，卸载 / 保存失败也返回 false。两项成功准备的源目标范围重叠，不能据源 metadata 保留宣称中断可回滚。共享布局夹具相关七项回归通过；无生产修改或新构建，见[回退与取消门控](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-preparation)。

分配入口新增有限证据：原始 4.0.4 manifest 接到真实 ARM64 `BeginUpdate / CreateUpdateSnapshots`、LP 更新器与 COW 规划器；合成普通文件 LP 中核对十个分区的快照尺寸 / COW 估算、拒绝映射后的清理，及空间不足、缺少内核能力 / 估算、版本越界、overlayfs、错误状态，共七项通过。检查失败不发布目标 LP、metadata 字节不变、临时状态清理。布局与空间为明确合成输入，不能用于判断设备实际容量；映射 / COW 初始化和控制器回退仍未贯通。无生产修正或新镜像，见[分配入口范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-snapshot-allocation)。

最新原始 4.0.4 整包模拟在模型内成功：一次运行完成整包验签、真实 ARM64 引擎 4933 操作 / payload 哈希 / 42 分区哈希，接到精确原厂 postinstall 的 Recovery 保护分支及真实 SnapshotManager 的 Unverified 状态发布，再记录模型目标槽。引擎退出 0，原父安装器返回 INSTALL_SUCCESS=0，21 项断言通过，约 861 秒。**结果为 MODEL_SUCCESS，完整设备 OTA 仍未验收**：块只读、挂载、快照分配、HAL / 槽位仍有模型，没有真实启动或合并。无生产修改或新构建；保留此前 FAILED63 记录。见[当前模型范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-model-finish)。以下为各阶段历史证据，不能把阶段边界当作最新队列。

原 ZIP 父进程到真实 ARM64 引擎已在一次运行中接续：当前固定信任库验证原始 4.0.4 整包签名后，原 A/B 命令 / fork / pipe 经显式 QEMU 桥接启动原主程序与下载队列，完成 4933 操作及 42 最终哈希。引擎在普通文件块只读设置处返回 63，父进程消费真实两阶段进度，观察 wait status16128，正确返回 INSTALL_ERROR=1 并清理 / 回收；没有误报成功。**安装仍为 FAILED**，postinstall 挂载 / 程序、SnapshotManager、槽位和合并未执行。父为主机编译，HAL / 文件映射等替身保留；无生产修正或新镜像。见[一次父子接续范围](docs/INSTALL-CHAIN-VALIDATION.md#stock-zip-engine-joined)。

原 ARM64 `update_engine_sideload` 主程序 / `ApplyPayload` / `DownloadAction` / `FileFetcher` 已在当前镜像 linker / libc 环境处理原始 OS4.0.4 ZIP，完成 4933 操作与 payload 哈希，并通过 42 个最终分区哈希校验。其后 postinstall 对普通文件设置块只读失败，**安装返回 63，不是安装成功**。10 个真实 COW 视图由文件映射模型物化；BootControl / Hardware / 清理动作 / proc 状态为明确夹具，没有 SnapshotManager 或实际挂载。ZIP 安装器父进程仍未与此运行接成同一链。本批是接续证据，无生产修改或重编；首版夹具判据错误的 FAIL 原样保留，复核报告只证明实际停止位置与哈希，不覆盖安装失败。见[引擎结果](docs/INSTALL-CHAIN-VALIDATION.md#stock-engine-entry)。

原始 `OS4.0.4.0.XODCNXM` 完整 ZIP 在旧 media-recreate 候选开启验证时被拒绝。本批生产修正为补齐固定小米 OTA 公钥：从六份哈希固定的原厂 recovery 提取，六份证书完全一致；保留原有三张证书，不修改运行时验证逻辑。清理构建后，原始完整 ZIP 开启签名验证通过，移除仅该公钥后拒绝，设备不匹配也拒绝；五项入口检查及普通 ZIP 36 项回归通过。808 来源、六 profile 和封装核对通过，与旧镜像相比仅构建属性、ramdisk 摘要与 otacerts.zip 改变。生产二进制未变。交付核对见本地 `logs/stock-ota-trust-delivery.json`。

这修正了原厂签名支持，**不表示完整卡刷通过**：入口子进程只核对原包 offset / headers / CrAU，不安装 payload。历史完整 payload 执行属于较早 snapshot-map 镜像，不能与当前入口测试拼成完整 OTA 验收，见[范围与结果](docs/INSTALL-CHAIN-VALIDATION.md#stock-os4-zip)。

容量刷新新增原 `gui2_loop_tick` / app 主循环接续证据：正常结束、建页前结束与人为提交等待三场景通过。等待期间 worker DONE 不会使阻塞中的 GUI 继续轮询，解除后下一轮更新完成；不证明现场 DRM 长期等待。扫描、提交及设备服务有明确替身，现场根因仍未解决。无生产修改或重编，不重复同类夹具，见[范围](docs/REFRESH-STUCK-INVESTIGATION.md#gui-loop)。

scratch保存后，在目标写入前/一块后/ordered块全写后及header提交两项后退出整个服务，再创建新client/server/handler的四项恢复通过：前三项走真实scratch重建，第四项沿进度2继续，重启后快照读取、最终全文件及进度4均核对。受影响ordered六项回归通过。没有生产修正或重编；进程退出恢复不等于手机断电，见[恢复范围](docs/OTA-OPERATION-COW.md#snapuserd-resume)。

有序COPY/XOR与实际ReadAhead已补六场景，覆盖双块依赖、XOR偏移21、混合操作、scratch区和写入/同步失败；整文件与重新打开COW进度核对通过，共享handler八项回归通过。无生产修改或重编，此检查点未验证进程死亡续合并（后续见上文），多窗口与内核接续仍未验证，见[有序合并范围](docs/OTA-OPERATION-COW.md#snapuserd-ordered)。

实际 client Connect/query、server、SnapshotHandlerManager、ReadWorker 与 replace/zero MergeWorker 已接续八场景。真实COW压缩数据/零块读取、64 KiB合并内容与未改尾部逐字节核对，写入/同步故障均保持失败；容量查询和dm-user端点为明确替身。没有发现新增生产缺陷，不重编0080镜像。该检查点未包含COPY/XOR/RA；后续有序合并见上文，进程退出后的局部续合并见上文，硬件断电、内核映射和完整OTA仍待完成，见[范围](docs/OTA-OPERATION-COW.md#snapuserd-handler)。

## 0089 交付时的定向验证

启动时的非 FBE 媒体目录恢复不再忽略目录查询 / 创建失败，media 根已存在时也补查用户目录；拒绝普通文件及符号链接，目录就绪后只恢复缺失绑定，不卸载整个 data 分区。FBE 跳过及缓存元数据 best-effort 策略保留，元数据失败记录日志。13 个原方法私有 chroot 场景通过，旧实现同组 10 项失败；16 项 manager 清除回归通过。真实普通目录 / uid65534 权限失败配合挂载、bind、元数据和呈现替身，不代表完整启动 / GUI / fscrypt 或设备验证。807 来源清理构建、六 profile 不变，`logs/media-recreate-delivery.json` 核对通过。见[启动媒体目录范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#media-recreation)。

## 0088 交付时的定向验证（历史）

Android Secure 目录重建改为返回结果，七种格式选择与 rm-rf 将创建 / 挂载 / bind 失败传回 manager/backend。目录在父分区挂载后创建，拒绝普通文件及符号链接，已有绑定不重复叠加；原调用不再创建后随意卸载父存储。37 项原 helper/manager/backend 场景通过，旧实现 34 项失败；25 项格式转换、11 项清除错误传播、六项同镜像 ARM64 工具回归通过。实际目录操作只涉及临时普通文件，挂载 / bind / 设备 / 命令有明确替身，不是物理设备或完整 GUI 验收。806 来源清理构建及六 profile 核对通过，证据 `logs/andsec-recreate-delivery.json`。见[目录重建范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#andsec-recreation)。

## 0087 交付时的定向验证（历史）

ext 格式化成功后立即记录新文件系统类型，避免后续临时挂载沿用旧类型；persist 后处理明确检查挂载、目录删除及卸载结果，仍挂载时拒绝执行离线 e2fsdroid。清理失败仍尝试卸载，失败不能伪装为格式化回滚。18 项原 helper / manager / backend 定向场景通过，旧实现 15 项失败；25 项格式转换及同镜像 ARM64 格式化 / 修复六项回归通过。挂载、设备、SELinux 与删除为明确替身，工具仅操作普通临时文件，不是设备 persist / 实际挂载或完整 GUI 验收。清理构建 805 来源、六 profile 不变，交付核对 `logs/format-persist-delivery.json` 通过。见[后处理范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#persist-postformat)。

## 0086 交付时的定向验证（历史）

六个离线格式化 helper 补齐卸载后仍挂载拒绝，避免保留 System 的成功返回导致 mkfs 误执行。十五个选择 / 挂载场景及可选 USE_EXT4 保留挂载分支通过，旧七个格式选择加内建分支一个场景失败；既有二十五项格式转换、同镜像 ARM64 格式化修复六项、原 Unmount / 修复九项回归通过。同格式 rm-rf 保持原分派。挂载观测与命令为明确替身，非实机或完整生命周期验收。804 来源清理构建、六份 profile 不变，仅 Recovery 主程序、构建属性和摘要变化，`logs/format-mounted-delivery.json` 审计通过。见[格式化前置条件](docs/FILESYSTEM-TOOLS-EXECUTION.md#format-mounted-guards)。

## 0085 交付时的定向验证（历史）

离线修复在 Unmount 成功请求后确认目标确实未挂载，拒绝保留 System 挂载时的 fsck 和 Resize 前置修复，不强制取消用户设置。九个挂载路径场景通过，旧两项误执行；146 返回码断言、同镜像 ARM64 修复七项和格式化 / 修复六项回归通过。挂载与设备是明确替身，工具仅运行于私有普通文件；并非实机 / 完整 GUI 验收。803 来源清理构建、六份 profile 不变，仅 Recovery 主程序、构建属性和摘要变化，`logs/repair-mounted-delivery.json` 审计通过。见[前置条件与限制](docs/FILESYSTEM-TOOLS-EXECUTION.md#repair-mounted-guard)。

## 0084 交付时的定向验证（历史）

兼容发送在前一批 USB 已失败、下一批排队磁盘读取再失败时保留先前 USB 错误；等待磁盘收尾的顺序不变。原生 / 兼容六个多批场景通过（含 7 MiB + 37 字节内容往返），旧兼容双故障一个场景失败，单批错误八项回归通过。802 来源清理构建，六份 profile 字节不变，仅 MTP 库、构建属性和摘要改变，审计 `logs/mtp-pipeline-delivery.json` 通过。指定重叠调度不证明完整 USB / Reset 取消，见[多批范围](docs/MTP-ADAPTATION.md#pipeline-first-error)。

## 0083 交付时的定向验证（历史）

修正原生负磁盘读取遗漏，以及原生 / 兼容尾批 USB 写入失败误报成功。八项定向检查通过，旧源码六项失败（含一个十秒超时）；正常传输往返与完成队列三项相关回归通过。磁盘取消保留原错误、短写明确返回 EIO；不承诺已送达数据回滚。清理构建仅改变 MTP 库、构建属性及 ramdisk 摘要，801 来源、六份 profile 不变，交付审计 `logs/mtp-send-delivery.json` 通过。只覆盖单批 body 与明确故障边界，不表示完整 USB / Reset 验收，见[发送失败范围](docs/MTP-ADAPTATION.md#send-errors)。

## 0082 交付时的定向验证（历史）

原生 bulk `waitEvents` 在完成队列报错时不再将 `-1` 转成数组循环上限。旧 EIO / EAGAIN 两项由 ASan 复现栈越界，修正后三项通过，含 EINTR 真实重试和内容检查；原生 / 兼容模式传输往返与故障回归通过。实际主机 AIO / 管道 / 普通文件配合单次完成错误注入，不是物理 FunctionFS / UDC 或完整取消复位验收。交付审计 `logs/mtp-aio-error-delivery.json` 通过；清理构建仅 MTP 库、构建属性和 ramdisk 摘要变化，未变证据复用。见[范围](docs/MTP-CONTROL-ADAPTATION.md#bulk-completion-error)。

## 0081 交付时的定向验证（历史）

上传失败且临时文件无法删除时，当前 handle 不再被遗留路径占用。覆盖 / 新建各连续两次失败后可成功上传，旧目标保持、两份遗留内容及用户同前缀文件均核对；116 项对象与 48 项移动 / 复制通过，旧覆盖对照失败、新建对照通过。清理构建相对 0080 仅改变 `libtwrpmtp-ffs.so`、构建属性和 ramdisk 摘要，六份 profile 保留；未变结果按原范围复用。交付审计 `logs/mtp-staging-retry-delivery.json` 通过。不是跨重启清理或 USB / Windows 验收，详见[范围](docs/MTP-ATOMIC-UPLOAD.md#staging-retry)。

## 0080 交付时的定向验证（历史）

实际 ARM64 snapuserd 服务端通过公开 Start / Run 与私有 Unix socket 执行八项检查。旧源码在三种客户端半关闭情形下 SIGSEGV，0080修正后八项通过；第二客户端仍可查询并停止服务。替换的只有 daemon main，没有 snapshot handlers、内核映射或完整 OTA。见[故障与范围](docs/OTA-OPERATION-COW.md#snapuserd-eof)。

最终镜像相比0079仅 snapuserd 二进制、构建属性及文件摘要变化。既有更新器、manager/client socket与设备清理结果按原范围复用，不把独立套件视为完整接续，也不重跑未变功能。

## 本次候选包含的修正

- **0089**：非 FBE 启动媒体目录创建失败立即停止，根存在时也恢复缺失用户目录，仅恢复缺失 bind，不卸载整个 data。
- **0088**：Android Secure 目录重建返回失败，格式化 / rm-rf 不再忽略创建和绑定错误，已存在绑定不叠加。
- **0087**：ext 格式化成功立即保留真实新类型；persist 临时挂载 / 删除 / 卸载失败传回调用者，仍挂载时不运行 e2fsdroid。
- **0086**：离线格式化 helpers 拒绝卸载请求后仍保持挂载的目标，同格式 rm-rf 分派保留。
- **0085**：离线 Repair 确认卸载后的实际状态，阻止保留 System 挂载时继续运行 fsck / Resize。
- **0084**：兼容多批发送先等待读取收尾，再返回先前 USB 错误，避免后续磁盘错误覆盖。
- **0083**：负磁盘读取先检查，原生 / 兼容尾批 USB 写入错误传回调用者，取消不覆盖原错误。
- **0082**：bulk 完成队列报错立即保留 errno 返回，避免负计数导致栈数组越界。
- **0081**：分离当前传输 handle 与遗留临时路径，修正删除失败后无法再次覆盖同对象；保留精确路径隐藏，不按前缀删除文件。
- **0080**：recv EOF 不再依赖 POLLHUP，解析器拒绝空命令，避免半关闭连接使服务端访问空 vector 崩溃。实际 ARM64 server八项 / 旧三项 SIGSEGV；清理构建798来源 / 六profile，交付核对通过。

- **0079**：解除映射结果汇总到控制器与校验器，失败阻止重映射及成功上报；空集合成功，metadata 不可用不调用 snapshot，原哈希错误保留。校验器9 / 控制器8通过，旧2 / 6失败；取消10 / postinstall6必要回归通过。清理构建796来源 / 六profile；仅更新器二进制变化，实际映射及完整安装仍未覆盖。见[范围](docs/OTA-OPERATION-COW.md#snapshot-unmap)。

- **0078**：快照必要清理失败向 CancelUpdate / 原始 ResetUpdate 返回失败，防止取消误成功。实际 ARM64 十场景通过、旧六场景误成功；共享代码收尾十六项 / postinstall 六项回归通过，清理构建794来源 / 六profile。实际映射、快照删除与合并仍未覆盖，不表示完整 OTA。见[范围](docs/OTA-OPERATION-COW.md#snapshot-cancel)。

- **0077**：CLI 输出 FIFO 握手与写入不再阻塞 GUI；读取端缺失时保留请求最多五秒，超时不执行并重建监听；按实际输入长度终止命令，重启监听清除旧请求。12 场景通过、旧七场景失败，清理构建 793 来源 / 六 profile。只有 Recovery 主程序、构建属性与 ramdisk 摘要相对0076改变；GUI库、工具worker、容量计算及profile字节不变。现场刷新根因未证明，见[边界](docs/REFRESH-STUCK-INVESTIGATION.md#cli-fifo)。

- **0076**：格式转换不受 rm-rf 设置覆盖；缺工具拒绝转换而非删除旧文件假成功；按请求别名分派，格式化成功及时更新类型。25 场景通过、旧 10 失败；命令/设备是替身，真实转换接续仍待覆盖。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#文件系统转换分派与状态0076)。

- **0075**：Dalvik 挂载/路径查询/删除失败传播；内部存储只清除媒体根目录内容，保留根 inode/元数据，恢复 MTP 登记后仍保留删除失败状态。16 场景通过、旧 9 失败；普通 user xattr 不是 fscrypt 验收。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#dalvik-与内部存储清除0075)。

- **0074**：保留媒体的数据清除传播类型读取、unlink / rmdir 与目录迭代错误；递归跟踪实际排除内容，只在预期保留时接受目录非空。13 场景通过、旧 3 失败，0073 与备份目录相关方法未变，复用原 11 / 12 项结果。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#保留媒体的数据清除0074)。

- **0073**：目录删除首个失败不再被后续成功覆盖；三个清除入口传播结果到 manager / backend FAILED。真实权限错误等 11 场景通过、旧 5 失败，备份目录管理必要回归 12 项通过。后续 0074 补齐保留媒体递归，其他调用方与完整生命周期仍待维护，见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#目录清除失败传播0073)。

- **0072**：备份、恢复、清除、侧载与 fastbootd 日志页补齐有界读取和页面首帧/删除门控；五入口 30 场景、共享工具页六项通过。backend 执行逻辑未改，不表示完整业务链或现场刷新验收。见[生命周期范围](docs/OPERATION-FEEDBACK-ADAPTATION.md#进度页日志生命周期补齐0072)。

- **0071**：MTP 文件格式在对象信息、属性、路径、枚举与筛选间统一；按常见扩展名分类，重命名刷新属性。对象链路 114 项 / 转移 48 项通过，旧实现四个格式场景失败。只识别文件名，不解析媒体标签或证明 USB 集成。见[格式一致性](docs/MTP-OBJECTS-ADAPTATION.md#文件格式与筛选一致性0071)。

- **0070**：工具进度页复用有界日志窗口，首帧匹配后读取，终态更新先于日志；六场景通过，旧实现六个入口均触发同一无界读取缺陷。修复软件响应路径，现场停留根因尚未证明。见[刷新调查](docs/REFRESH-STUCK-INVESTIGATION.md#工具日志分批渲染0070)。

- **0069**：SnapshotManager 的临时文件同步失败不再继续发布并误报成功；重试 `EINTR`。实际 ARM64 状态文件生命周期 16 场景通过，旧 helper 两项 I/O 错误误报成功、两项缺少实际 EINTR 重试。共享 libsnapshot 使 init / fastbootd / Recovery / OTA 更新器均重新链接；未变的界面与 profile 证据复用。见 [状态发布](docs/OTA-OPERATION-COW.md#快照状态文件同步失败0069)。这不是完整 OTA 或断电验收。

- **0068**：复制日志检查存储挂载、文件复制、内核 / logcat 获取和写入结果；任一已勾选导出失败会标为 FAILED，保留其他成功文件。13 场景通过、旧实现 11 失败，详见 [日志导出](docs/OPERATION-FEEDBACK-ADAPTATION.md#日志导出的失败状态0068)。

- **0067**：备份重命名 / 删除不再解释 shell 文本，校验当前父目录并拒绝覆盖已有目标。12 场景通过，旧版 8 场景失败；共用 worker 的三种刷新页面调度回归通过。详见 [备份会话与目录管理](docs/BACKUP-SESSION-ADAPTATION.md#备份目录重命名与删除0067)。

- **0066**：快照首次映射或重映射失败时立即拒绝最终校验，并尝试释放部分映射，避免读取可用旧文件后误报成功。完整 ARM64 校验器六场景通过，旧实现两处失败；映射接口仍是明确替身，不表示 SnapshotManager 已执行。

- **0065**：最后分区完成失败及分区关闭失败统一返回写入错误；最后一次关闭失败不再被忽略。实际 ARM64 `DeltaPerformer::Write` 八场景通过，旧实现三处失败。已清理构建并核对打包更新器；其他 ramdisk 变化仅构建属性和文件摘要清单。

- **0063**：温度紧接时间 / 录屏标记，限定在左半区，避开中央摄像头；ext 扩容预留长度和容量计算防溢出、下溢及无效尺寸。
- **0064**：A/B 更新器使用有效 Error 对象；同步拒绝立即返回错误，不进入无完成回调的循环。
- 继承此前 XRING O1 加载页、刷入目标、NV 普通界面限制、OTG 发现及安装 / MTP 收尾等修正。

完整范围见 [有限维护交付记录](docs/archive/BOUNDED-MAINTENANCE.md)。0077 重新编译 Recovery 主程序；相对 format-transition 候选只改变主程序、构建属性与 ramdisk 摘要，GUI / MTP / 更新器 / profile 字节不变。

## 本批与继承证据

后续独立F2FS内容读回补齐六个文件（含内联、多节点、嵌套和零数据），副本单字节破坏可检出，读取不改变镜像哈希。仅修正主机Debian读取器的extra_attr偏移；当前cli-fifo候选与793生产来源不变，没有生产修改或构建。见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#f2fs-readback)。

| 范围 | 结果 | 限制 |
| --- | --- | --- |
| 格式转换分派 | 25 场景 / 旧 10 失败 | 原 Wipe/helper/manager/backend；命令/卸载/容量/设备/metadata 替身 |
| Dalvik / 内部媒体 | 16 场景 / 旧 9 失败 | 真正文件删除、inode/user xattr；挂载/MTP/展示替身，非 fscrypt 或完整 GUI |
| 保留媒体递归 | 13 场景 / 旧 3 失败 | 原排除匹配与真实权限错误；Wipe 分派 / 挂载 / 设备 / 展示替身，非完整 GUI |
| 目录清除失败 | 11 场景 / 旧 5 失败，备份目录回归 12 项 | 普通文件真实权限错误；挂载 / 设备 / 展示替身，未覆盖保留媒体路径 |
| 五页日志生命周期 | 30 场景 / 旧 30 入口失败，工具页回归 6 项 | 原 poller / 呈现 / 清理语句；非目标 backend 或完整 GUI / DRM |
| MTP 格式 | 对象 114 项 / 转移 48 项；旧格式 4 项失败 | 文件名分类，非媒体解析或 USB / Windows 验收 |
| 工具进度日志 | 6 场景；旧实现 6 个入口失败 | 原 worker、日志轮询及 LVGL；生产端 / flush / 调度替身，非现场根因证明 |
| 日志导出 | 13 场景；修正前 11 失败 | 实际文件 / worker；采集、挂载与展示替身，无断电证明 |
| 备份目录管理 | 12 场景；修正前 8 失败 | 实际 worker / 文件操作，展示与配置替身；无断电或完整恢复 |
| 快照映射错误 | 6 场景；修正前 2 失败 | 完整 ARM64 verifier / ActionProcessor；设备映射为替身 |
| DeltaPerformer 收尾 | 8 场景；修正前 3 失败 | 原 ARM64 Write；已解析 manifest / writer I/O 为替身 |
| 温度布局 | 11 场景；修正前 10 失败 | LVGL 真实执行，字体 / 读数 / flush 有替身 |
| ext 扩容 | 16 场景；修正前 7 失败 | 命令参数边界，不执行真实 resize 工具 |
| OTA 同步拒绝 | 7 场景；修正前 4 失败 | 原解析 / 错误路径；服务与调度替身，无 payload 写入 |
| 刷新页面生命周期 | 3 种调度，含 8 次重入 | worker、PUSH / POP、动作与删除；未复现现场故障 |
| 状态读取 / 修复返回值 | 28 场景 / 146 断言 | 对应软件路径，不能替代实际传感器或挂载 |
| init / profile | 5 份 init、9 组 / 102 次阶段调用 | host verifier 与脚本回放，不是完整系统启动 |
| RTC / 视频 | 相关来源未变，复用既有结果 | 不为刷新日期重跑，不外推硬件和性能 |

格式转换分派为本批修复；Dalvik / 内部媒体、保留媒体递归、目录清除失败、五页日志生命周期、MTP 格式、工具进度日志、日志导出、备份目录、快照映射等行保留此前交付范围，未将旧报告重新绑定为新镜像执行结果。以上不是总功能通过率；历史全量审计仍有证据来源漂移，不能用定向通过代替全量通过。

## 此前新增证据（对应旧候选，范围保留）

当前构建 ARM64 快照库的 COW v3 / LZ4 / 64 KiB 真实文件往返及四类拒绝通过，六份原厂参数一致。使用交付 linker / 共享库；archive 在测试时绑定，未被旧镜像来源清单历史绑定。不是 update_engine / SnapshotManager / 合并或完整 OTA 验收，详见 [范围](docs/OTA-OPERATION-COW.md)。无生产修正或重新构建。

实际 ARM64 `InstallOperationExecutor → SnapshotExtentWriter → COW` 已接续 REPLACE / BZ / XZ，含分散目标与部分写入失败，共八场景。短输入可能返回true但目标不完整，该八场景当时未执行最终哈希；后续十场景已接通原异步校验器，短输入返回错误15，设备映射仍为普通文件替身，不等于OTA成功。见 [操作接续范围](docs/OTA-OPERATION-COW.md)。该证据批次当时没有改变生产镜像。当前新候选继承 0065，并新增 0066；VABC 的后续会话验证见同一主题文档。

同一 payload 测试入口已进一步接到原 PostinstallRunnerAction，五场景确认哈希失败不进入完成阶段、FinishUpdate 失败不切槽、切槽失败返回错误及明确不切槽的状态。完成 / 槽位 / 硬件接口仍为观察替身，实际 postinstall 脚本跳过；无新增生产修正或镜像。详见同一 [OTA 主题](docs/OTA-OPERATION-COW.md)。

两份 OS4 的真实 RAW / BZ / XZ 操作各一个，共六项已执行原 ARM64 操作到 COW / 读回，逐字节匹配独立校验的原分区切片。共用入口原八项回归通过，无生产修正或重编。后续已执行 OS4 旧样本完整原始 payload（7,821,653,872 B），4,903 操作、42 分区最终哈希通过。使用同镜像证书，保留 Recovery 签名编译边界；正式版完整 payload（7,883,589,123 B）亦已执行，4,933 操作与 42 目标哈希通过。设备映射和 Prepare 仍为替身，无实际 SnapshotManager / postinstall 或整包 OTA 验收。无生产修正或新镜像，见同一 OTA 主题。

实际工具证据补充：当前同镜像原 Wipe/helper/manager/changefilesystem/Repair/ExecCmd 已在私有 chroot 接到真实 ARM64 格式化/检查工具，六场景通过，ext4 独立 payload 读回一致，F2FS 填充后结构检查通过；设备解析/卸载/容量/属性与 metadata 是明确替身，父调用者为主机程序。无生产修改或重新构建，见[范围](docs/FILESYSTEM-TOOLS-EXECUTION.md#实际格式化工具与调用链接续)。

## 用户确认与未完成项

- **OS4 震动已修好，用户确认正常**；退出例行检查。
- backup-manifest 基线设置用户确认正常；结论仅限对应观察。
- 容量刷新日志约 5.15 秒已结束，但现场画面未结束原因未定位；不宣称修复。
- 自动触摸启动、完整 OTA / 快照写入与合并、真实 TEE / CE、完整 USB / MTP、全流程备份恢复等边界仍在 [工作队列](docs/WORK-QUEUE.md) 中。

代理没有执行手机或物理块设备操作。离线工具执行、主机替身、原始 ARM64 代码执行与历史用户设备结果分别记录，不互相替代。

## 本轮实现决定

Recovery metadata 不可用的直接回退执行了六个原 ARM64 控制器场景。调用方先检查 compression 模式，孤立映射失败不足以证明安装失败，因此撤回试验补丁，生产来源恢复为上述 log-export 候选。此处只有新增证据，无生产修复或新交付镜像；详见 [回退判断](docs/OTA-OPERATION-COW.md#recovery-缺失-metadata-时的回退判断)。实际 SnapshotManager 仍未执行，完整目标不据此关闭。

## 收尾失败后的实际重试接续

原始 ARM64 PostinstallRunnerAction 经原控制器调用实际 SnapshotManager，六场景确认同步 / 状态发布失败阻止切槽，重新创建控制器后沿用已有文件重试完成；切槽失败后的 Unverified 状态不会重复发布。详见 [接续范围](docs/OTA-OPERATION-COW.md#实际收尾调用链与失败后重试)。本批无生产修改或新构建，当前 snapshot-sync 候选与 784 来源保持不变；挂载 token、HAL / slot / hardware 仍为边界，真实 payload 到映射 / merge / postinstall 脚本全链仍未完成。

## postinstall 子进程接续

原始 ARM64 PostinstallRunnerAction / Subprocess / 进程回收器接实际无害 ARM64 程序，9 场景覆盖必选 / 可选退出、特殊错误、信号、缺程序、挂载拒绝和取消；验证失败阻止切槽及取消后无未回收子进程。六份原厂 manifest 确认两份 OS4 的 otapreopt 为可选，其余四份无该配置。见 [范围](docs/OTA-OPERATION-COW.md#postinstall-程序退出与取消接续)。无生产修改或新构建；实际挂载、原厂 otapreopt / namespace、payload 和 SnapshotManager 全链仍未完成。

## 原厂 OS4 postinstall 的 Recovery 出口

两份原厂 otapreopt 脚本字节一致，经当前候选的实际 ARM64 shell/getprop 执行，八个场景确认 `dev.bootcomplete` 非 1 时返回 0、没有 ART 调用。实际属性区缺失时原 getprop 返回空值；其他属性输入为显式夹具。无需因缺 ART 就补服务或改脚本。见 [范围](docs/OTA-OPERATION-COW.md#os4-原厂脚本的-recovery-退出条件)。本批无生产修改或构建；真实属性区、挂载、namespace 及原安装器到原厂脚本全链仍未完成。
