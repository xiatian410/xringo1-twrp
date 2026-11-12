# 技术文档索引

面向使用和构建的入口见根目录 [README](../README.md)。本目录保留有独立技术内容的功能说明；历史文档中的旧候选和测试数字只代表当时的输入，不是当前验收状态。本地 `logs/`、`imgs/` 和原厂样本没有公开上传。

当前状态以 [验证报告](../simulation-report.md) 和 [工作队列](WORK-QUEUE.md) 为准。震动已解决，其旧调查只供追溯，不进入例行检查。

## 安装、分区与存储

- [OTA payload、VABC / COW 与最终校验](OTA-OPERATION-COW.md)
- [A/B OTA 命令准备与失败收尾](AB-COMMAND-VALIDATION.md)
- [镜像路由、ZIP 队列与 ARM64 updater](INSTALL-CHAIN-VALIDATION.md)
- [ADB sideload 子进程与取消生命周期](SIDELOAD-LIFECYCLE.md)
- [分区界面修正：镜像目标与 NV 操作](PARTITION-ACTIONS.md)
- [嵌套分区操作路径修正](PARTITION-OPERATION-PATHS.md)
- [实机截图后的 OTG 误枚举修正](MOUNT-LIST-EXPLANATION.md)
- [system/vendor 挂载模式事务](MOUNT-MODE-ADAPTATION.md)
- [存储选择的失败处理](STORAGE-SELECTION-ADAPTATION.md)
- [Sparse 镜像刷写的容量与完成检查](SPARSE-IMAGE-FLASH.md)
- [文件系统工具执行与修复结果](FILESYSTEM-TOOLS-EXECUTION.md)

## 启动、固件与安全服务

- [固件组合选择与启动激活](PROFILE-SELECTION.md)
- [模块初始化状态：依赖就绪判断修正](MODULE-STATE-ADAPTATION.md)
- [OS4.0.4.0 正式版增补记录](OS4-STABLE-ADAPTATION.md)
- [OS4 正式版无法触摸：反馈、离线排查与顺序修正候选](OS4-TOUCH-FAILURE.md)
- [六版本安全服务依赖与 ARM64 linker 执行](PROFILE-LINKER-ARM64.md)
- [六份固件安全服务本体的 ARM64 重定位](PROFILE-SERVICE-RELOCATION.md)
- [安全服务运行时库搜索配置](PROFILE-SERVICE-NAMESPACE.md)
- [多用户发现与解锁入口](MULTIUSER-ADAPTATION.md)
- [固件兼容性分析（离线阶段）](firmware-compatibility.md)
- [MiTEE 组合比较（静态候选）](crypto-compatibility.md)

## 备份与恢复

- [tar、压缩、加密与分卷管道适配](ARCHIVE-PIPELINE-ADAPTATION.md)
- [文件归档恢复：实际代码离线验证](ARCHIVE-RESTORE-ADAPTATION.md)
- [原始分区镜像备份与恢复的离线验证](RAW-IMAGE-ADAPTATION.md)
- [备份会话、取消和 tar 子进程](BACKUP-SESSION-ADAPTATION.md)
- [恢复会话预检与分卷校验](RESTORE-SESSION-ADAPTATION.md)
- [备份摘要文件的原子发布](DIGEST-PUBLICATION.md)

## USB 与 MTP

- [MTP 离线修正与传输验证](MTP-ADAPTATION.md)
- [MTP上传原子发布](MTP-ATOMIC-UPLOAD.md)
- [MTP 启停、状态与存储消息离线适配](MTP-CALLER-ADAPTATION.md)
- [MTP 控制报文与 FunctionFS 事件批处理](MTP-CONTROL-ADAPTATION.md)
- [MTP 上传日期解析](MTP-DATETIME-ADAPTATION.md)
- [MTP 目录上传时间与完成状态](MTP-DIRECTORY-METADATA.md)
- [MTP 事件请求、退出与重连](MTP-EVENTS-ADAPTATION.md)
- [MTP 对象数据库与会话适配](MTP-OBJECTS-ADAPTATION.md)
- [MTP class Reset 与服务器会话释放](MTP-RESET-SESSION.md)
- [MTP 取消请求与活动事务匹配](MTP-TRANSACTION-CANCEL.md)
- [MTP 移动、复制与目录重建](MTP-TRANSFERS-ADAPTATION.md)
- [USB configfs 切换与服务交接](USB-CONFIGFS-ADAPTATION.md)

## 界面、设置与状态

- [设置保存、点击与时区失败回退](SETTINGS-ADAPTATION.md)
- [电量、温度与时钟读取及失败处理](STATUS-ADAPTATION.md)
- [原厂 RTC 回调离线验证](RTC-DRIVER-EMULATION.md)
- [GUI2 反馈次数与取消操作的离线验证](UI-FEEDBACK-ADAPTATION.md)
- [操作完成反馈的离线验证](OPERATION-FEEDBACK-ADAPTATION.md)
- [录屏帧与时间轴离线验证](VIDEO-FRAMES-VALIDATION.md)
- [刷新容量页面不结束：现场分析](REFRESH-STUCK-INVESTIGATION.md)

## 维护与交付

- [工作队列](WORK-QUEUE.md)
- [第6、7、8、10、11、12组有限维护](BOUNDED-MAINTENANCE.md)
- [公开仓库维护约定](../MAINTENANCE.md#github-同步)

## 已解决项的历史参考

[震动适配记录](HAPTICS-ADAPTATION.md) 汇总实现要点和独立技术文档。OS4 震动已由用户确认正常，不作为当前待办或例行检查。
