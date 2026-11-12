# dijun / Xiaomi 15S Pro TWRP 维护树

本目录是配置与原厂组件的维护入口。范围以
[ADAPTATION-GOALS.md](../../ADAPTATION-GOALS.md) 为准：OS3/OS4 优先、争取单镜像兼容，
本轮只做离线适配。violin/jinghu 的遗留文件保持隔离，不属于此次支持承诺。

## 当前状态

| 范围 | 证据与限制 |
|---|---|
| OS4 历史基线 | `twrp-recovery-mitee-bootfix.img` 的启动、显示、触摸事件、用户 0 解密有历史证据；不转移为其他镜像的实机结论 |
| 当前统一候选 | 最新镜像、哈希和分层测试范围见 [模拟报告](../../simulation-report.md)。五套档案共用同一镜像；完整功能验收尚未完成，物理震动、Windows MTP 与唤醒延迟未验证 |
| 五个固件样本 | 同为无内核 v4 recovery；启动镜像及模块分区已提取并校验，五包 vendor/ODM/模块分区已齐；system/system_ext 身份资源已核对；全部所需分区和选定系统配置资源已齐 |
| OS2/OS3 档案 | 五套档案已进入同一候选并完成选择/启动脚本模拟；全功能验收未完成。相同 6.6 下仍存在 ABI 冲突，旧目录已排除 |
| 解密选择 | 五版 MiTEE 分别选择；预检 60 场景、实际镜像激活 56 次阶段调用通过；真实 TEE 与多用户仍待验证 |

详见 [固件比较](../../docs/firmware-compatibility.md)、
[震动适配记录](../../docs/HAPTICS-ADAPTATION.md)、
[功能矩阵](../../compatibility-matrix.md)。旧的通用功能勾选表已移至
[历史存档](../../docs/archive/device-tree-readme-before-profile-audit.md)，不作为验收依据。

## 构建与补丁

在工作目录执行：

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

第一条检查固定源码基线与补丁重建结果。第二条同步维护树，保留旧生成目录，
执行 `make -j$(nproc) installclean` 和 `make -j$(nproc) recoveryimage`。
构建输出为 `/root/AAA/twrp/out/target/product/O1_asic/recovery.img`。

[patches/series.json](patches/series.json) 固定每个源码仓库的 commit、补丁顺序、
补丁 SHA-256 与结果文件 SHA-256。`0006` 应用于 `system/sepolicy`；其余应用于
`bootable/recovery`。脚本遇到不认识的源码改动时会停止，不覆盖它们。

当前 recovery 不携带 kernel，沿用对应系统的 boot/vendor_boot。维护树不得新增
自定义 `modules.load` / `modules.load.recovery` 去覆盖原厂首阶段加载。
`prebuilt/kernel*` 与旧模块目录暂存为来源资料，不能据此声明统一 ABI。

使用与增补固件流程见 [MAINTENANCE.md](../../MAINTENANCE.md)。

状态读数：五份固件共同的 battery sysfs 节点用于状态栏，缺失/非法读数不伪造 100%；实际 0% 可显示。温度数据接口按 thermal class 的有符号毫摄氏度解析。24 组主机测试通过，具体范围见仓库 docs/STATUS-ADAPTATION.md；RTC 漂移及真实传感器保持 U。

震动调用链：0013 补丁让 GUI2 按运行时能力显示入口，统一 FF 优先路由，检查 LED/timed_output 写入结果，限制各反馈通道时长；22 组实际生产调用链主机用例通过。五包原厂属性与模块/固件哈希可用 `scripts/audit_haptics_profiles.py` 复核；物理电机仍为 U。

界面事件：0014 移除五个点击回调的重复反馈，键盘沿用取消检查且保持 KEYBOARD 通道；确认滑块忽略无拖动的松手事件，拖动期间禁用会取消并复位。实际 LVGL 组件回放与绘制证据见仓库 docs/UI-FEEDBACK-ADAPTATION.md；业务操作和电机仍由替身隔离。

归档管道：0020 固定 tar/pigz/OAES 的进程收尾、短读、线程缓冲区和分卷处理修改；实际文件往返与故障测试范围见 [归档编解码记录](../../docs/ARCHIVE-PIPELINE-ADAPTATION.md)。完整管理器会话、断电完整性和真实加密卷仍需独立验收。

MTP 对象与会话：0021 修正跨存储/递归枚举、移除后的数据库清理、失败删除/改名和重连状态，主机实际协议回放范围见仓库 docs/MTP-OBJECTS-ADAPTATION.md；FunctionFS/configfs 调度与 Windows 物理枚举仍单独验收。

MTP 移动/复制与重建：0022 将文件操作和目录数据库作为一次同步操作，保持移动句柄、拒绝覆盖并处理跨文件系统失败；rescan、inotify 溢出与根目录变化已有生产回放。范围见仓库 docs/MTP-TRANSFERS-ADAPTATION.md；FunctionFS 事件线程退出由后续 0023 覆盖；configfs 仍需独立验证。

MTP 事件退出：0023 将每事件线程改成单工作线程、128 项有界队列和独立可取消 AIO；关闭时撤销队列并回收请求，重连不重发旧事件；提交与完成阶段的临时错误均有期限重试。主机管道与取消故障回放见仓库 docs/MTP-EVENTS-ADAPTATION.md；USB 控制请求/configfs 调度仍单独验收。

USB 切换：0024 为 dijun 使用独立的 dijun-usb-config 程序串行处理 configfs 与服务所有权，检查写入及读回后发布状态；MTP 就绪状态丢失时退回 ADB。程序从构建属性保留 ADB/fastboot 标识，拥有专用 SELinux 域。实际 init 解析/调度回放与硬件边界见仓库 docs/USB-CONFIGFS-ADAPTATION.md；调用者 UI、控制请求与物理枚举仍单独验收。
