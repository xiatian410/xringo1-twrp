# dijun 维护与离线验证

2026-11-12 NV与公开同步复核：当前普通GUI隐藏NVData/NVCFG/protect等目标，后台双向拒绝手动挂载/卸载（含规范化路径及解析别名），26项当前源码复核通过；保留原厂fstab和内部核心访问，不是特权访问控制。公开仓库https://github.com/xiatian410/xringo1-twrp已确认PUBLIC；后续每个连贯源码/配置/测试/文档修改批次均执行scripts/sync_github.py --push并核对远端HEAD，镜像、编译文件、原厂blob、私钥和原始设备日志不上传。详见AGENTS.md和docs/GITHUB-PUBLICATION.md。

2026-11-12 RTC原厂回调证据收尾：六份vendor_boot按OTA manifest核对镜像后重读原始模块，ARM64读/设与OS4刷新共56场景通过。PMIC设置失败返回-5但软件偏移已更新；OS4刷新PMIC失败使用计数回退，reset错误传播。MMIO/PMIC/日历转换为显式夹具，不是完整probe/hctosys或物理漂移验收；无新增校时偏移或生产修改。详见docs/RTC-DRIVER-EMULATION.md；候选仍mtp-directory（215914df…）/765来源，本轮无需构建。设置及OS4震动正常确认保持，完整12组继续进行中。

2026-11-12 安全服务实际namespace检查：在原始ARM64 linker构造函数前直接读取默认namespace字段，六profile各三个服务确认环境私有库优先、默认bootstrap/system搜索路径和不隔离配置。每profile删除配置及加入存在的标记目录各一项，实际搜索路径按预期变化；共42项通过，默认重定位30项回归通过。成员偏移从同执行字节linker的DWARF提取，库/服务原始CAS绑定；bootstrap插入和不存在路径忽略均保留原始语义，不改生产。见docs/PROFILE-SERVICE-NAMESPACE.md与logs/profile-service-namespace-audit.json。仍不证明真实init/mount namespace/APEX/属性区/proc、服务初始化或密钥/合成加密卷完成；完整12组继续进行中。生产mtp-directory镜像215914df…/765来源未变，本轮无构建，OS4震动正常确认保持，源码文档同步GitHub，编译文件不上传。

2026-11-12 安全服务本体ARM64重定位：六profile的原厂tee-supplicant/KeyMint/Gatekeeper共18个加载执行，通过当前镜像原始linker在call_pre_init_constructors调用前断点停止，核对PC、g_is_ldd=0及r_debug实际加载对象/来源。每profile额外缺库与等长缺符号私有副本对照各一项，共30项通过；正向服务与生产ELF均未修改。使用镜像ld.config及init绝对库路径，chroot无真实proc/属性区，仍不宣称精确init/APEX/namespace、服务构造函数/main/Binder/TEE/密钥操作或合成加密卷完成。详见docs/PROFILE-SERVICE-RELOCATION.md与logs/profile-service-relocation-audit.json。生产镜像仍为mtp-directory（215914df…）/765来源，本轮无生产修改或构建；完整12组继续进行中，OS4震动调用正常确认保留。测试审计文档按约定同步GitHub，编译文件不上传。

2026-11-12 MTP目录上传修正：补丁0059在SendObjectInfo创建/接纳目录后，通过目录fd应用有效修改时间（含epoch0、负秒和时区偏移），刷新数据库后结束，不再保留待SendObject状态；open/futimens/close失败返回错误，保留已有目录和内容以供重试。对象链路110项（新增16项）通过，旧实现同组16项有14失败，move/copy48项回归通过。installclean及make -j$(nproc)30并发构建recovery-dijun-unified-mtp-directory.img，SHA256 215914df1f8768bf00272f5c10c03b90fa8e624e9b1337fa6801a0ef3e5155b0，765来源/六profile封装通过。定向交付见logs/mtp-directory-delivery.json；实际USB/Windows、跨重启临时文件归属回收、子文件上传结束后的父目录日期恢复与断电仍未完成。NV/OTG/侧载修正继承，OS4震动及设置正常确认保留，完整12组继续进行中；源码文档同步GitHub，编译文件不上传。

2026-11-12 ARM64安装链证据：新增真正AArch64动态ELF无害updater，在原始主机ZIP安装链经签名/摘要、选择/提取、fork、协议管道和wait执行20场景通过；当前镜像linker/libc及固定QEMU在明确execve边界接入，构造函数/main参数、进度、缺库/缺符号拒绝、信号/退出状态与失败前写入均有核对。原主机36项回归通过，定向审计见logs/zip-arm64-chain-audit.json，范围见docs/ZIP-ARM64-EXECUTION.md。生产源码和764项镜像来源未变，沿用recovery-dijun-unified-sideload-reboot.img（022af2fc…），本轮无新构建。不是完整ARM64 Recovery、原厂OTA/update_engine、实际USB/FUSE或GUI验收，完整12组仍进行中。NV普通挂载隐藏/拒绝和OTG发现修正保留；设置与OS4震动用户正常确认保留。源码/文档/测试按约定同步GitHub，编译文件不上传。

2026-11-12 sideload重启交接：补丁0058将minadbd成功ACK且USB恢复成功后的system/bootloader/fastboot/recovery请求交给GUI统一退出/重启，等待启动流程、后台命令和侧载worker结束；ORS收到重启即停止脚本。修复完成状态先发布、running标志后清除导致析构可能取消待交接请求的竞态：状态发布与取消检查共用mutex。最终19场景通过，修复前同组15失败；生命周期33/实际ZIP侧载链27回归通过。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-sideload-reboot.img`，SHA256 `022af2fccb1040b7537b989c9c25d6c57ba844a27f11fae652d1f73bd93a7d2a`，764来源/六配置封装通过；同镜像脚本结果与交付审计见logs/sideload-reboot-delivery.json。Rescue/BCB未实现，真实minadbd/USB/FUSE、完整ORS和实机重启未验收。继承0054 NV普通挂载隐藏/双向拒绝、0048 OTG发现修正；设置和OS4震动用户确认保留。源码文档按每批次同步公开GitHub，镜像不上传；完整12组保持进行中。

## NV 分区与公开同步

NVData、NVCFG、protect_f/protect_s 属于设备维护区域，不作为普通挂载页上的用户操作目标。补丁0054隐藏GUI条目并拒绝GUI backend手动挂载/卸载（含解析别名）；原厂fstab和Recovery内部核心访问保留。此限制不等于对特权shell或备份恢复核心的访问控制。不要为清理界面而删除原厂分区声明。

用户要求每个连贯文件修改批次完成验证后同步公开仓库 `https://github.com/xiatian410/xringo1-twrp`，执行 `python3 scripts/sync_github.py --push --message "..."` 并确认远端main等于本地HEAD。公开同步只包含脚本允许的源码、补丁、配置、测试和文档；构建镜像不上传。原厂二进制、私钥、原始实机日志也不得上传。

2026-11-12 sideload安装收尾：补丁0057在minadbd install handler内接收每次TWinstall_zip的wipe_cache请求，并在该包状态回复前执行/cache清理；清理失败返回INSTALL_ERROR，使该包不能被报告成功。ORS原先在twrp_sideload核心已安装后又TWinstall_zip一次，已移除重复安装，使用核心安装结果并沿用其子进程唯一回收。GUI sideload单独的清缓存/Dalvik选项检查失败返回，更新操作失败状态。加入真实ORS分支及原始核心/backend→真实ZIP、digest、提取、fork/exec与minadbd 8字节socket接续，27场景通过；修复前同组19失败。测试覆盖多包逐包清理次数在minadbd状态ACK前可见、清理错误/后包失败、user选项与ORS不重复执行；cache/mount/USB属性/FUSE/环境为替身。installclean后make -j$(nproc)（30并发）构建`recovery-dijun-unified-sideload-completion.img`，SHA256 `f5231d7886615dbfe0a89063706178ed2120866085248e5c7aa47e27ceed2c74`，760来源/六配置封装通过；侧载生命周期33、同镜像profile9组/102阶段和module-state4组/24调用通过。定向审计logs/sideload-completion-delivery.json通过，实际USB/FUSE、ARM updater、物理清理与GUI点击未验收；完整12组保持进行中。源码文档按约定同步GitHub并核对远端HEAD，镜像不上传。

2026-11-12 sideload生命周期修正：维护补丁0056让核心统一终止/回收minadbd，USB失败等所有已fork出口收尾，waitpid处理中断，PID锁内清零；GUI取消仅请求所属token传输退出，fork前取消及跨会话隔离有覆盖。回复使用MSG_NOSIGNAL不改全进程SIGPIPE；命令要求8字节，EPOLLIN/HUP先消费缓冲。实际公开backend/worker与侧载核心接续33个私有进程/socket场景通过；旧源码可比31场景29失败（多数共享PID/SIGPIPE断言），新send专用零写/EIO两项不作旧路径对照。USB属性/FUSE/安装器/MTP/缓存为明确替身，完整USB包传输、同步安装中取消、缓存传播及脚本/重启收尾仍待完成。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-sideload-lifecycle.img`，SHA256 `a5e16b92da91202527714049200ae23c35d13ed2e2d79f6327d55ed2f8afbde3`，758份来源/六配置封装通过。定向交付审计logs/sideload-delivery.json，范围docs/SIDELOAD-LIFECYCLE.md。继承NV/OTG/ZIP修正，保留OS4震动调用正常与设置正常确认；完整12组目标及历史全量审计漂移继续进行中。源码按约定同步GitHub，镜像不上传。

2026-11-12 ZIP队列收尾修正：真实公开backend/后台线程→flash_zip→TWinstall_zip→ZIP/摘要/提取→fork/exec/wait接续23项通过；修复前同组5失败，固定时间戳后各包SHA256完全相同。补丁0055累计各包wipe_cache请求，后包成功/失败均不丢弃前包请求；缓存清理失败发布FAILED并保留已完成包数，不回滚已安装内容。缓存/挂载/解锁/进度/操作反馈为替身，镜像安装独立40项回归通过。installclean及make -j$(nproc)（30并发）构建`recovery-dijun-unified-zip-queue.img`，SHA256 `4425846118c018b9a87b40c9bb549c6f9aa13af2c724973104c53ea013324a7f`，753来源/六配置封装/85份Recovery补丁结果核对通过；同镜像profile9组/102阶段、module4组/24调用通过。交付审计logs/zip-queue-delivery.json，范围docs/INSTALL-CHAIN-VALIDATION.md。继承NV/OTG修正；OS4震动调用正常及设置正常的用户确认保留。完整GUI、ARM updater、AB payload、sideload及12组整体目标仍未完成；本轮源码/文档按约定同步GitHub，镜像不上传。

2026-11-12 GitHub交付已完成：公开仓库https://github.com/xiatian410/xringo1-twrp已使用用户CLI账户创建并推送，公开清单精确包含563个文本/元数据文件，无编译产物或原厂blob内容。权限规范化修正后的远端CI已通过（检查提交87101fa）。今后文件修改按AGENTS.md执行同步并核对远端HEAD；公开CI只检查来源/语法/补丁完整性。

2026-11-12 NV挂载与公开源码要求：用户明确NV不应在普通界面提供挂载操作，维护补丁0054隐藏NVData/NVCFG/protect及对应别名，并在backend拒绝挂载/卸载；保留原厂fstab和内部核心访问，不将其当作用户存储。26项后台策略检查通过，旧实现同组17失败；真实LVGL列表六场景通过，正常夹具20行减为16行。同镜像profile9组/102阶段、module4组/24阶段调用通过。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-nv-mount-policy.img`，SHA256 `0be46fb13091c4ebe663b5196ba22beadf5874990f7b811cb6d64c247195e5fe`，751来源/六配置封装/维护补丁核对通过；交付审计logs/nv-mount-policy-delivery.json。用户确认OS4震动调用正常，继续其他功能而非围绕震动排查。用户授权通过GitHub CLI账户xiatian410创建公开源码仓库`https://github.com/xiatian410/xringo1-twrp`；以后每个连贯文件修改批次完成后必须执行scripts/sync_github.py --push并核对远端HEAD。编译产物、原厂blob、私钥、原始实机日志不上传。流程见docs/GITHUB-PUBLICATION.md及AGENTS.md。完整12组目标仍进行中。

2026-11-12 用户更新：OS4的震动调用正常。保留这一用户确认，不再以震动调用链为当前排查主线；继续安装/侧载及其余任务文档要求。此确认不外推为所有版本、全部波形或物理效果已验收。

2026-11-12 ZIP安装接续与ABI选择修正：原始TWinstall_zip→真实ZIP映射/提取、签名/摘要验证→fork/exec/wait的36项主机检查通过；同一最终测试运行旧源码有6项失败。维护补丁0053让外层分派与提取共用通用优先/advertised ABI顺序选择，空abilist回退abi，无匹配明确失败；原22项updater协议sanitizer回归通过。installclean及make -j$(nproc)（30并发）构建`recovery-dijun-unified-zip-selection.img`，SHA256 `c6d2d09d50f3a1fda0f19164bc6204d4b911be6417efe18553af429bbfe3c3c6`，750来源/六配置封装/补丁重建核对通过，同镜像profile9组/102阶段调用、module4组/24调用通过。定向交付见logs/zip-selection-delivery.json，范围见docs/INSTALL-CHAIN-VALIDATION.md。继承截图对应的0048 OTG完整控制器匹配修正，保留用户对设置正常的确认。ABI后缀fixture为主机程序，未执行ARM updater、AB payload、完整backend/GUI队列、sideload或设备测试；完整12组目标与历史全量审计漂移仍未完成。

以下按时间倒序保留历史检查点，旧“当前”和“未执行ZIP”仅指当时。

2026-11-12 安装链路推进：原始后台线程→PartitionManager目标查找/槽位覆盖→TWPartition→真实libsparse的40项主机检查通过，含双槽顺序、失败恢复原槽位与实际文件内容；路径解析/容量/挂载仍为夹具。真实fork/exec updater协议22项通过，旧实现同组14断言失败；维护补丁0052校验进度字段/有限数值/范围，非法输入排空并等待子进程后返回失败，空log及pipe/fork/fdopen错误安全收尾。未执行完整ZIP解压/签名/摘要、OTA payload、sideload或GUI点击。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-updater-protocol.img`，SHA256 `9875f7e53ab1eb3a7347cd538097c82ea4c81ac31c5569cc446120e0eb1d7912`，749来源和六配置封装核对通过。同镜像profile9组/102阶段调用、module4组/24阶段调用通过。详见docs/INSTALL-CHAIN-VALIDATION.md，定向交付为logs/updater-protocol-delivery.json；继承OTG/sparse/MTP/CE修正，设置正常确认保留，完整12组仍进行中。


2026-11-12 sparse刷写容量与完成修正：维护补丁0051在真实libsparse解析后检查展开长度及已打开块目标BLKGETSIZE64容量，拒绝零长度/越界/未知容量；写后fsync及close错误返回失败，容量查询/同步EINTR可重试，可选discard推迟至校验后。真实三个生产方法与AOSP libsparse在私有文件40项通过、旧实现同组27断言失败，raw传输65项回归通过。中途写失败可能已改变前部数据，不承诺回滚。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-sparse-flash.img`，SHA256 `93aea3b2b22f387c79c42899c78152d8bf2b33f86f1ac2683796a97a340552c6`，747来源/六配置封装核对通过。同镜像profile9组/102阶段调用、module4组/24阶段调用通过，定向交付审计为logs/sparse-flash-delivery.json。继承0048 OTG、0049 MTP日期与0050 CE失败清理；设置正常的用户确认保留。详见docs/SPARSE-IMAGE-FLASH.md；ZIP/sideload完整链路、槽位/GUI、真实性/CRC及物理断电仍未验收，完整12组继续进行中。


2026-11-12 多用户CE失败收尾修正：原始Decrypt_CE_storage先安装CE后prepare，prepare失败可留s_ce_policies；补丁0050在Recovery的provider失败出口请求驱逐本次用户，失败记录诊断，其他用户隔离。原始Recovery/vold八个方法接续15场景通过，旧实现同组3断言失败；用户枚举/控制18项回归通过。失败后错误secret仍失败、正确secret重新read/install；原始MarkDataLocked→lock/evict→再解锁及adoptable清理均执行，install/evict ioctl和prepare/mount仍是夹具，不等于物理已锁。vold基线e7e26ed2及FsCrypt/Decrypt/Android.bp纳入维护来源记录，未改其密钥协议。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-ce-cleanup.img`，SHA256 `9861830824b5a34bb5782bdbd6704bbc7c4b33374e20fe0fb87ffa23fae498cf`，746来源/六配置封装通过；同镜像回放和定向审计见logs/ce-lifecycle-delivery.json。父绑定工作资料协议、同步Binder安全中止和真实CE重挂载继续未完成；完整12组目标保持进行中，未操作设备。


2026-11-12 MTP文件上传时间修正：维护补丁0049将有效time_t（包括0和-1）与缺失/非法日期分开，接收失败后不尝试设置时间；futimens失败在rename发布前中止，保留原目标。真实server/database/私有文件链路94项通过，新增新建/覆盖各8项共16日期场景、旧实现同组10失败；移动复制48项通过。首次测试中部分bulk失败后重试暴露USB替身未排残余数据，保存logs/mtp-upload-time-first-attempt.json，不把该边界冒充完整端点恢复；该场景改为已完整读入payload后的接收失败。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-mtp-upload-time.img`，SHA256 `57798214bab0d211aa53e5036e46e45c528483aebb3cc16286da86406928484a`，742份来源/六配置封装通过；同镜像profile/module回放与定向审计见logs/mtp-upload-time-delivery.json。继承0048 OTG修正，列表证据仍明确绑定此前031497e5镜像；设置用户确认保留。目录日期、媒体完整元数据、临时文件崩溃残留、USB/断电和其余完整12组保持未完成，不以震动为当前主线。


2026-11-12 实机截图后的优先项：设置在9a1b057d backup-manifest版本正常，按用户要求停止围绕震动持续展开。本次截图明确显示真实内部共享存储673GB，以及大量0B的`/storage/usbotg-sda/sdb/sdc/sdd-*`。已复现OTG发现层把完整sysfs通配式截为`/devices/platform/soc/`，进而接纳内置UFS的缺陷；维护补丁0048让热插拔/重扫描/冷启动使用完整控制器模式与祖先路径匹配，并识别GUI实际`/storage/usbotg-*`路径。隔离发现12场景通过、旧实现同组8项失败；真实LVGL列表六场景包含已发布路径与OTG命名排序。installclean及make -j$(nproc)（30并发）构建完成，新候选`recovery-dijun-unified-otg-discovery.img`，SHA256 `031497e53bf500805a2ba6d74b4bc0a9315fbdbc5e6740ec028df33059d27561`；741份生产来源/六配置封装核对通过，设置保存22项、存储选择15项通过。同镜像回放与定向交付审计见logs/otg-discovery-delivery.json。NV原厂fstab声明保留；这不等于普通用户存储。此前列表夹具只覆盖分类后的输入，漏掉发现层，不能再作为排除现场问题的依据。完整12组目标仍在进行中，不宣称实机恢复。


2026-11-12 模块review来源更新：scripts/review_module_state_reference.py按固定上游源码摘要检查七项顺序并执行原始show_initstate三状态，复核六内核原始字节与现有同镜像4/24、旧脚本14失败报告依赖。logs/module-state-review.json未改，新报告module-state-reference-current.json替代当前总审计入口；无生产修改/构建。总审计越过模块检查后在历史settings报告data.cpp绑定停止，不能据此重启设置修复。logs/module-state-reference-freshness.json为124匹配/95漂移/20无充分绑定，完整审计未通过；当前设置正常的用户观察与未解决震动均保持。

2026-11-12 NV原厂声明复核：scripts/audit_stock_nv_fstab.py对六包recovery/vendor_boot尺寸/SHA256与OTA manifest核对，重读12份ramdisk fstab，NV六条五列字段与维护树一致，现有提取文件逐字节一致。来源证据logs/stock-nv-fstab-audit.json，不推断实际分区用途/存在或GUI应开放权限。加入当前定向审计，无生产修改/构建；设置正常反馈有效，震动和现场重复标签未解决。

2026-11-12 挂载展示主机接续：运行tests/mount_list_chain_test.py五场景，真实分支/快照/backend/LVGL处理分类与存在夹具，正常20行mount/3行storage，30次刷新不累加；注入同名输入会原样保留，不能当成现场根因。原始块分区不进入mount，维护NV不进入storage，移除/恢复场景通过。sources/报告已纳入simulation-report.json，scripts/audit_current_offline_paths.py通过当前9a1b057d/738份来源核对及45/5/7项边界检查。没有生产变更、镜像构建或硬件执行。完整总审计历史漂移仍存在，震动/挂载现场仍未定位，用户设置已正常结论保留。

2026-11-12 用户确认9a1b057d backup-manifest镜像设置功能已正常：停止把旧症状作为当前故障持续修复或索取重复采集。当前挂载页反馈另查，`python3 scripts/inspect_mount_inventory.py`从实际交付镜像提取32行/22挂载点/10组格式候选/19个非原始声明，不是运行GUI列表。NVData/NVCFG按现有mount条件显示，emmc NVRAM不应进入mount；没有现场列表，不推测标签根因、不改生产。详见docs/MOUNT-LIST-EXPLANATION.md。上一项独立工作`python3 tests/repair_tool_chain_test.py`七场景通过：真实repair wrapper/lookup/Repair/输出ExecCmd接当前镜像ARM64 e2fsck，原始文件映像/私有chroot/QEMU执行；不含真实卸载/块设备或GUI。报告logs/repair-tool-chain.json，完整硬件目标仍未完成。

2026-11-12 设置首页点击补查：`python3 tests/settings_navigation_test.py`执行真实LVGL/page_host过渡清理、scaffold、action/settings builder、卡片与原样分发回调，九入口×五种输入共45项通过，报告`logs/settings-navigation.json`。目的页路由为记录边界，尺寸/字体为主机夹具，未运行完整Android shell、真实input或persist。没有复现统一点击拦截，没有新增生产修正或镜像；现场“全部设置不能改”仍未定位。当前震动证据入口的13项来源核对通过，但全量审计在历史module-state-review来源漂移处失败；完整新鲜度为119匹配/95漂移/20无充分绑定，不是功能通过率。详见docs/SETTINGS-ADAPTATION.md与logs/current-haptics-evidence-freshness.json。

2026-11-12 整份备份完成性修正：补丁0047为新备份写入同步的INCOMPLETE标记，并在所有payload稳定、sync后原子发布COMPLETE文件清单；恢复选择和RunRestore在列出/写入前检查文件集合与大小，保留无清单旧备份兼容。17项manifest、RunBackup55、RunRestore56用例通过；后两者执行生产管理器，archive编码/mount为边界替身。installclean/30并发构建新候选`recovery-dijun-unified-backup-manifest.img`，SHA256 `9a1b057d001821b0d9a908c003c3810f5295e6fa500e1716f59ae50364126123`，738来源、六样本包装和新二进制核对通过；同镜像profile9/module4/haptics policy12/USB policy53/init6通过。进程退出夹具不证明真实断电/文件系统持久性，manifest不校验内容且删除后回退legacy。震动仍未修复；设置与触摸现场、完整12组工作仍进行中。详见[备份范围](docs/BACKUP-SESSION-ADAPTATION.md)。

2026-11-12 备份摘要发布修正：维护补丁0046改为同目录临时写入、文件同步/关闭、rename及目录同步，避免失败或中断截断正式摘要。真实hash/文件与BackupPartition调用54项通过，旧实现同组44项失败；恢复54项/备份会话55项回归通过。installclean后make -j$(nproc)30并发构建`recovery-dijun-unified-digest-atomic.img`，SHA256 `7f4c42935ff34c01ce85cec049c94b60ebd072400255cf299aedaca10dacafff`，736份生产来源/封装通过；同镜像profile9组/102调用、模块4组/24调用、策略12+53/init5通过。目录同步失败时完整新摘要可能已可见，分卷逐文件提交不等于整份备份事务。详见[摘要发布范围](docs/DIGEST-PUBLICATION.md)。当前224项绑定清单126匹配/78漂移/20无充分绑定，全量审计仍未通过；震动、自动触摸、设置现场与原12组任务仍未完成。

2026-11-12 交付证据刷新：当前仍为`recovery-dijun-unified-mtp-reset.img`，SHA256 `046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27`，735份生产来源一致。模块夹具区分模块/触摸报告等待，将可选震动顺序约束改为触摸已尝试；同镜像模块4组/24调用、profile9组/102调用、策略12+53项和init5份通过，旧模块脚本同夹具仍14项失败。主要当前索引已更新为实际重跑报告；222项索引绑定清单124匹配/78漂移/20无充分绑定，总审计仍在历史review摘要处失败，这不是功能通过率。详见[当前交付与证据状态](docs/DELIVERY-EVIDENCE-STATUS.md)。生产代码与镜像未改，震动、设置现场、自动触摸及原12组目标仍未完成。下文早期“当前”及下一步属于各历史检查点。

2026-11-12 codec/PCM与FF原始接续：[两份OS4共12场景](logs/haptics-pcm-ff-join-review.json)执行codec probe、Mode1/Slot1 put、hw_params/sysclk与参数/时钟/RX widget，再接生产80ms SINE/IRQ。原始回调生成slots2/3、24bit word/32bit slot及单声道1.536MHz/双声道3.072MHz夹具缓存；不代表真实backend协商。四次参数寄存器更新全失败仍返回0；RX首/末写失败返回-5，后续FF仍发相同参数和命令。指针/分配/字符串/格式/寄存器/PM/ACK/调度/IRQ为显式边界，无真实ALSA/DSP/电机。详见[范围](docs/HAPTICS-PCM-FF-STATE.md)。生产046ab9e3/735来源保持，未改增益、校准或路由；共享软件路径仍不能选定物理原因，后续重点每设备校准/寄存器读回与输出通路，已有采集不重复索取。设置现场、自动触摸、震动及完整12组未完成。

2026-11-12 ASP与FF同上下文接续：[两份OS4共14场景](logs/haptics-asp-ff-join-review.json)从原厂A1 probe执行clk_en/asp_start/时钟切换，再提交生产80ms SINE和显式提供的开始/完成IRQ。未开ASP、已开及开启失败均请求相同五次FF写入与0x01800081命令；没有发现纯软件ASP前置门控。ASP标志在尝试前已置1且失败不回退，完成时重启ASP失败可留下state1/count0/completion已饱和；13jiffy STOP超时也可能最终回调返回0。codec/BCLK3.072MHz/PLL0/寄存器/PM/锁/ACK/队列/IRQ仍为显式边界，不证明实际时钟或电机。详见[范围](docs/HAPTICS-ASP-FF-STATE.md)。生产未变，046ab9e3镜像/735来源保持；下一步ASP参数/PCM寄存器与每设备校准读回，震动、设置现场、自动触摸及完整12组保持未完成。

2026-11-12 音频socket对端接续：[两份OS4共34场景](logs/haptics-audio-peer-review.json)执行原始socket handler→ResourceManager→ModulePrimary→updateA2HMode及串行原子release，使用前轮捕获的72字节启动消息。编号42通知震动流活动并协调已有流A2H；未知编号/短读/EOF/read=-1也请求相同0100回复，不能当成硬件就绪。合成许可流不活动时请求Haptics Source2，app拒绝时0，活动时不请求设置。socket/stream/usecase/app策略/setA2HParameter仍为显式边界，无真实ALSA/DSP/电机。详见[范围](docs/HAPTICS-AUDIO-SOCKET-PEER.md)。没有生产修改或新构建，046ab9e3镜像/735来源保持；下一步ASP与独立FF状态关联，物理震动、设置现场、自动触摸及完整12组未完成。

2026-11-12 服务线程/XML：运行`python3 tests/haptics_service_tail_review.py`及`python3 scripts/audit_haptics_service_tail_review.py`。14场景绑定原厂压缩重定位解码、XML/属性、服务/AAC/tinyalsa及模拟器：执行原始线程构造、XML hash消费者、显式调度的首次worker到timedwait，并后接普通on。发现后台会初始化PCM路由，更新此前仅构造/on范围的结论；不盲加Source/ASP控制。libxml节点、Android Thread/ALSA/socket仍是夹具，原厂tinyalsa转换叶函数实际执行；完整服务并发/硬件未覆盖。无生产修改/构建，046ab9e3/735来源保持，详见docs/HAPTICS-SERVICE-THREAD-XML.md。

2026-11-12 PCM/AAC 初始化：`python3 tests/haptics_pcm_init_review.py`运行两份OS4共26场景，`python3 scripts/audit_haptics_pcm_init_review.py`核对原始服务/属性/XML/AAC库、模拟器、错误传播与当前镜像来源。原始AAC本体已接入PCM/数据构造，但worker/服务线程未执行，原始库初始化错误不阻止外层继续。后接普通on使用显式long-id/恢复完成标志、空callback；不扩大为完整服务或电机验证。无需因这些软件证据修改PCM路由、校准或FF请求。无生产改动/新构建，046ab9e3候选保持；后续缺口为服务线程/XML/派发，设置现场日志仍未收到。详见docs/HAPTICS-PCM-INITIALIZATION.md。

MTP Reset交付收尾：同一046ab9e3镜像的profile脚本回放9组/102次阶段调用通过；735来源与完整维护补丁80+1+3文件核对一致，0待同步。交付核对见logs/mtp-reset-delivery.json；这属于离线软件证据，震动/设置及完整12组仍未完成。

2026-11-12 MTP Reset维护：0045独立Reset信号与server-thread会话释放，保留ESHUTDOWN退出优先级。recovery-dijun-unified-mtp-reset.img（046ab9e3…）已installclean后make -j$(nproc)30并发最终构建；源码735/封装核对通过，仅libtwrpmtp-ffs.so核心字节变化。python3 scripts/audit_mtp_reset_delivery.py核对控制80/旧3失败、server78/旧Reset9失败、移动复制48/事件62/传输/同镜像profile。固定来源和完整维护补丁可重建；历史总审计来源漂移不在本次清除。真实Reset端点/bulk/队列集成未验收，震动/设置故障保持未解决。详见docs/MTP-RESET-SESSION.md。

2026-11-12 服务初始化检查：`python3 tests/haptics_service_init_review.py`执行30项，`python3 scripts/audit_haptics_service_init_review.py`核对来源、错误/重试、原厂属性、当前镜像及生产来源。constructor前缀仅执行到0x13084；校准恢复记录调用后替换返回，不能称为本组执行了restore。FF后端constructor另行执行，global sysfs路径显式供给，不能称为由完整服务构造连接。原始读取custom_wave而无额外控制写入只限这两个范围；XML/线程/后续派发仍未覆盖。无生产改动或新构建；当前da614695候选不变，震动/设置现场未解决。详见docs/HAPTICS-ADAPTATION.md。

2026-11-12 旧版配置/input/selftest：`python3 tests/haptics_legacy_config_input_join.py`与`python3 scripts/audit_haptics_legacy_config_input_join.py`绑定44项、四份原始ELF/DT/固件及依赖。正常路径使用原始legacy布局（CTX input+0x50/DSP+0x58，input私有数据+0x2d8、FF effects+0x80），不借用OS4偏移。原始队列请求flags0xa0012/max_active1，运行器按FIFO在flush处保存/恢复上下文；无真实调度。9类配置/注册错误与2条自检路径/版本：ACK时probe0，start mailbox-5仍probe0；无completion调用。原始remove执行及MFD失败后的input注销服务有记录，不能当成真实内核资源释放。已修正前缀16/上传20报告中错误的remove未执行标注并重跑；下游历史证据若绑定旧测试hash仍只作历史证据。当前镜像不变，无生产修改/构建，不宣称物理震动恢复，见docs/HAPTICS-FIRMWARE-EMULATION.md。

2026-11-12 旧版probe/上传连接：运行`python3 tests/haptics_legacy_probe_upload_join.py`，再运行`python3 scripts/audit_haptics_legacy_probe_upload_join.py`。四份OS2/OS3模块各5路径，正常probe→原始firmware parse→5份参数load到MEM_RDY注入错误共68次raw写入，主bin缺失63次；PM状态3卡住和第一固件写错误分别阻止解析/后续参数。寄存器读表独立来自WMFW，DT来自已有merged-overlay清单，所有写地址/字节摘要与文件清单比对。原厂remove函数已执行，其内核teardown服务为边界，不宣称实际内核资源释放或probe成功；0x40a270/B2身份为夹具，不套用于现场OS4 A1。来源/依赖/状态均绑定报告；未修改生产或构建镜像。后续须接旧版完整配置/input/start/IRQ/自检，并保持物理震动未验证，见docs/HAPTICS-FIRMWARE-EMULATION.md。

2026-11-12 CUSTOM完整回调连接：`python3 tests/haptics_custom_callback_review.py`共12项，`python3 scripts/audit_haptics_custom_callback_review.py`核对来源与关键错误/cleanup/队列/mailbox。服务effect来自原始helper/XML，ID/指针显式重定位；原始probe/固件/上传回调与worker执行，copy_from_user、task/MMU、分配/PM/regmap/队列等仍为夹具，不能写成真实usercopy或DSP。无生产修改/构建；mtp-transaction候选不变。失败路径返回-12/-14/-22且清理临时数据；正常CUSTOM31只证明请求0x0100001f，不认定比SINE更能产生实际震动。详见docs/HAPTICS-ADAPTATION.md，物理震动与12组未完成项保留。

2026-11-12 Cancel事务匹配：新增0044补丁，80+1+3文件可从固定基线重建。服务器解析命令后beginTransaction，作用域退出endTransaction；FunctionFS只中断匹配活动ID的Cancel。运行mtp_control_test.py（73项）、同组--source backups/mtp-transaction-pre-fix（5项预期失败）、mtp_objects_test.py（68项生命周期）、mtp_transfers_test.py（48项）、mtp_events_test.py（62项）和run_mtp_transport.py；本次报告使用logs/mtp-transaction-*独立路径。installclean/30并发构建新mtp-transaction候选，734来源与封装检查通过；同镜像profile回放9组与定向审计入口scripts/audit_mtp_transaction_delivery.py。不要把控制边界与server peer两组测试称为真实USB端到端取消，也不扩大到Reset/DeviceBusy/compat ep0。两份备份/恢复当前源码重跑54/55通过并刷新索引；其他旧报告来源漂移仍阻止全量审计，无统一全量通过声明。震动/设置现场与完整12组继续进行中。

2026-11-12 mailbox错误边界：运行`python3 tests/haptics_mailbox_error_review.py`执行原始OS4 mailbox重试/pm_enter/stop worker，共32项；再运行`python3 scripts/audit_haptics_playback_observation.py`刷新现场顺序窗口，最后执行`python3 scripts/audit_haptics_mailbox_error_review.py`核对来源/索引与边界。测试只在regmap、PM core返回、锁/sleep/恢复helper/pm_exit提供夹具，mailbox本身不再被替换。mailbox失败后stop done仍会出现；PM入口失败则无done。现场五次NACK的最终事务返回不能由后续日志顺序推出，撤回此前“不能作为无震动原因”的排除结论。无生产修改/新镜像或硬件执行，当前候选与12组未完成项保持；详见docs/HAPTICS-ADAPTATION.md。

震动能力查询中断修正：补丁0043让已有FF描述符的只读能力查询遇EINTR/EAGAIN时保留描述符与缓存能力，等待下一轮查询；避免关闭触发input core清理效果，不做无限重试。ENODEV/EBADF仍关闭并重新探测。28项路由/6项后台FF通过，旧代码同组EINTR/EAGAIN两项失败；14项日志ABI通过，8种时长effect字节不变。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-haptics-probe.img，SHA256 `e64e796370ad7983d27692ce22827ab03f72999e68881a1b4fe507247ec48f73`，732来源/封装核对通过；同镜像回放另记。现场没有能力查询EINTR证据，不能认定持续无震动根因或物理修复；设置现场及完整12组继续进行中。

时区保存失败回退：补丁0042在页面提交前保留五项旧值，部分写入/生成时区/flush失败时恢复选项和精确旧tw_time_zone，刷新旧环境，保留待选项供重试；检查时区/偏移索引边界。backend生成时区传回读写错误，回退不从GUI选项重建自定义时区。17项真实LVGL回调+实际adapter/libc检查通过，旧回调同组11项失败；保存链22/点击20/语言主题9/震动路由24/owner16回归通过。存储/属性/页面路由为夹具，目录fsync失败后的磁盘发布不构成回滚。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-timezone-retry.img，SHA256 `f31bbe13f856d25c0080b26cac041366bb91c5f61b95f88f9f5136df83a47023`，731来源与封装核对通过，同镜像profile回归另记。不能以此解释所有设置失效，物理震动与完整12组仍未完成。

MTP上传原子发布：补丁0041以同目录唯一临时文件接收，接收/长度校验/fsync/close均成功才rename，失败只删除临时文件，保留旧目标。数据库在同一observer锁下创建并登记精确临时路径，inotify、ReadDir与overflow reconciliation均不发布传输中的临时文件。68项真实server/database/storage主机检查（含22项新原子发布场景）与48项move/copy回归通过；旧实现5项覆盖对照均失败。目录fsync在rename之后失败只警告，完整新文件已提交，不能声称可恢复旧inode；模拟进程中途退出保留旧目标但留下临时文件，跨重启清理未完成。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-mtp-atomic-upload.img，SHA256 `7ca65801af3a62b4970cf1ad12d05a8af49dd8e870992b45e40ad6192a06a23a`，727来源与封装核对通过，同镜像profile回放结果另记。震动、现场设置及完整12组仍未完成。

震动生产请求诊断补齐：维护补丁0040在后台owner记录begin/end/expired、请求序号/时长/队龄/替换计数/耗时，在FF层记录实际type/waveform/period/magnitude和擦除/上传/播放/close的开始结束、实际返回值、独立保存的errno、单调时间与PID/TID。提交入口不执行日志I/O；周期能力probe正常不打日志。GUI与FF序号是不同空间，只能结合线程/时间定位，不能认定跨调用者严格关联。日志可能拖慢worker，不提供阻塞输出的实时保证；accepted仅系统调用边界，不等于电机。24项路由/4项后台FF/16项owner/14项日志ABI核对通过，8种时长effect字节与旧捕获一致。新增擦除失败和短写模拟；短写不再误报旧errno。installclean后make -j$(nproc)30并发新候选recovery-dijun-unified-haptics-request-trace.img，SHA256 `610f4acc2534cbd3fdd95f6733257efa52329435569df5230c4ea1a9c3326a8d`，726来源与封装/新二进制核对通过；同镜像profile另记。未改波形、幅度、增益、校准或触发实机操作，震动与完整12组仍未完成。


震动诊断因素分离：独立工具新增--sine-gain100与--custom-existing-gain，与原--play/--stock-long组成波形SINE/CUSTOM×是否写gain100的四种请求。两个SINE的effect字节完全相同；两个CUSTOM除运行时指针外与原厂HAL捕获一致，数组{0,31}也核对。47项主机syscall替身和18项目标ARM64/QEMU启动/拒绝/普通文件失败检查通过；不等于真实播放。显式gain100在close后保留，“不写增益”不会恢复默认状态，必须记录执行顺序，不能把跨次请求视为独立初态；工具不自动播放四种模式。CUSTOM继续仅供已审核OS4，cross入口限1..1000ms，无任意波形/增益。重新构建独立工具并打包tools/haptics-diagnostic-os4.zip，未连接手机或修改生产镜像。当前MTP日期候选8c624d0e不变，物理震动、设置现场和完整12组仍未完成。


MTP上传日期修正：维护补丁0039按MTP格式校验年月日/时分秒、单个小数位、Z和±HHMM，显式偏移转UTC不依赖Recovery时区；保留无偏移的本地时区/DST行为，拒绝归一化后的非法日期和不存在的本地时间，失败不改变调用者输出。实际MtpUtils+独立Python日期oracle80项通过，旧实现79项中48失败（旧版空指针另未执行）；生产server/database/文件上传46项及移动复制48项通过，含4项新日期落盘检查。主机libc/USB替身非手机RTC/Windows枚举。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-mtp-datetime.img，SHA256 `8c624d0e1a4b9bbff1b99ce83dbcce2c3cdfc3013c2270d65c04e075a8a81ee3`，725来源及封装/新二进制核对通过；同镜像profile另记。没有修正震动、修改校准或改变FF；原子上传覆盖/输出日期格式化/完整元数据等仍待完成，全部12组保持进行中。


设置保存失败后重试修正：维护补丁0038让语言/主题在flush失败时恢复旧内存值，保留待选项；避免主题值先变而未重建、再次点击被同值判断阻断。真实回调/LVGL事件9项通过，旧实现同组4项失败；存储/路由/console为显式夹具，不是实际persist或完整GUI。设置整行20项、真实文件保存21项、嵌套路径31断言回归通过。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-settings-retry.img，SHA256 `e8adb7259265b4fa05a1057ba9141e09af805c7ff2240cb07a45bb009bbe2214`，724来源及封装/新二进制核对通过。同镜像profile回放结果另记。目录fsync失败可能已发布完整新文件，内存回退并不构成磁盘回滚；这一边界保持明确。尚无本次设置现场日志，不能解释全部设置不可修改；物理震动未解决，触摸P0和全部12组继续进行中。


温度GUI交付更新：维护补丁0037通过现有status backend/controller接入tw_cpu_temp，合法整数-273..1000°C独立于电量解析；缺失/非法/禁用时隐藏，后续读数恢复。状态栏按实际文本重新布局，窄屏优先时间/录屏/电量，空间不足隐藏温度；装饰不可点击。11组真实LVGL/provider/controller检查通过，含14种解析值、定时刷新、0/负温、晚到/禁用恢复、电量隐藏、Wi-Fi/录屏、四宽度与明暗主题；28项状态回归通过。已检查1440宽实际渲染图，host字体/settings/tick仍为夹具，未证明Android显示或物理温度。installclean后make -j$(nproc)30并发构建[新候选](imgs/built/recovery-dijun-unified-temperature-ui.img)，SHA256 `f2dea7dbf8ad58a9363f0906effa9ade627e7903bc45ee71e1b1fc1159994d84`，723来源及封装/新二进制核对通过。震动未改且仍未解决，设置现场采集未到，完整12组保持进行中。


独立录屏读取：`python3 tests/video_ffmpeg_test.py`验证18份既有样片并执行72次准确输入跳转，显式使用FFmpeg原生vp8 decoder；复核入口`python3 scripts/audit_video_ffmpeg_delivery.py`。Debian ffmpeg/libavdevice只解压到tools/ffmpeg-host，未安装，依赖主机库指纹记录。先核对生产者报告与源码/样片hash；仅覆盖短单cluster文件。

录屏关闭错误交付：0032-recording-close-result.patch纳入series，72份recovery修改/1份sepolicy/3份tinyxml来源可重建；新候选recording-close（2773dec6…）714来源、installclean/make-j30。`python3 tests/video_failure_test.py`覆盖6类明确边界故障与同对象重录，修改前快照只有close失败；`python3 tests/video_frames_test.py`18项通过。最终检查入口`python3 scripts/audit_recording_close_delivery.py`；同镜像profile回归9组/102次阶段调用通过并纳入检查。旧clock-failure审计绑定旧源码，不应以当前源码重跑结果替代历史检查。

录屏队列回归现为18项：`python3 tests/video_frames_test.py`编译生产recorder/converter与真实libwebm/libvpx，编码门控填满两帧队列，解析/解码验证七帧丢弃、复制像素、时间缺口及stop排空。`python3 scripts/audit_video_frames_delivery.py`检查全部产物/source/index/当前镜像；旧全量审计的video分支同步18项，但没有宣称其余历史分支已通过。主机门控不是手机吞吐量证明。

真实SINE系数检查：`python3 tests/haptics_sine_coefficients_review.py`，随后`python3 scripts/audit_haptics_sine_coefficients_review.py`；46项使用生产FF捕获、原始固件parser/get_reg/get_coeff与SINE函数，同一空间执行，不替换系数查询。独立packed表Xbase+offset核对三地址；算法ID仅低16位比较，不能把0x1f202/0x4f202高位差异认定失败。PM/寄存器/分配为夹具，没有硬件输出验证或生产修改。

原厂音频路由/普通on核对：`python3 tests/haptics_service_route_review.py`运行20项原始ARM64服务场景，`python3 scripts/audit_haptics_service_route_review.py`核对来源/index/当前镜像。哈希表为XML派生布局夹具，mixer与FF是记录边界。原始普通on在已恢复校准、空callback条件下不调用mixer；算法缓存会在mixer set失败时更新并影响重试。不可用路由helper的尾调用日志返回寄存器断言成功，不可把缓存或模拟请求等同DSP状态。生产未改、物理震动未解决。

ARM64诊断启动检查：`python3 tests/haptics_diagnostic_arm64_test.py`，8项真实静态目标指令/bionic执行，使用提取的QEMU用户态和临时普通文件；目标SHA与QEMU来源固定在报告。没有连接设备、访问真实input或成功上传/播放。详见[工具说明](tools/haptics-diagnostic/README.md)。不要把这一静态工具启动检查当成任务中的动态ARM64 linker/加密卷验证。

录屏主机回归：`python3 tests/video_frames_test.py` 编译实际recorder/converter和仓库libwebm，链接主机libvpx.so.9，以真实文件解析及解码检查五档FPS/奇数尺寸/颜色和时长。报告 `logs/video-frames.json`；依赖主机ASan/UBSan，不连接设备，不引入Android decoder。限制与剩余检查见[录屏记录](docs/VIDEO-FRAMES-VALIDATION.md)。

独立震动诊断工具使用[维护说明](tools/haptics-diagnostic/README.md)构建，`python3 tests/haptics_diagnostic_test.py` 验证20项主机边界。产物不进入当前镜像，build.py 绑定现有 bionic/CRT/compiler 输入；静态 ARM64 格式并不证明运行兼容性。工具有显式 play 模式，当前仅完成构建与主机验证，没有运行设备命令。

校准系数检查：`python3 tests/haptics_calibration_coefficients_emulation.py` 共 36 项；结果 `logs/haptics-calibration-coefficients-emulation.json`。执行原始 parser/系数查询、三项 store 和 DT config；packed 表、PM/regmap 为边界。三项文件初值查无结果必须保留 null，不得填零；原厂 DT 的 130 Hz 默认频率可被 config 写入，不将缺 persist 恢复认定为基础频率缺失或本次根因。见[适配记录](docs/HAPTICS-ADAPTATION.md)。

维护入口为 `dtsrc/O1_asic_dual`。本轮只以 dijun 为适配对象，其他产品配置不能继承其支持结论。

2026-11-12 增益排查：`python3 tests/haptics_gain_emulation.py` 执行两份原厂 OS4 probe/FF_GAIN callback/worker，检查初值与实际固件中的 SOURCE_ATTENUATION，结果见 [12 场景报告](logs/haptics-gain-emulation.json)。驱动初值 100、固件衰减初值 0，0/50/100 写 400/24/0，101/65535 不入队。不要以缺少 FF_GAIN 认定默认静音或发送通用 65535；DSP/寄存器/PM 仍是显式夹具，不是电机验证。

`recovery-dijun-unified-module-state.img` 已从 Android 原始输出恢复，封装和当前编译二进制重新核对；707 份来源清单是明确标记的事后重建，不是构建时原始证明。完整审计须继续检查历史报告的源码指纹及文档依赖，不能用恢复文件替代功能验收。

## 固件与来源

原厂服务请求对比：运行 `python3 tests/haptics_service_request_emulation.py`。两包原始服务 FF helper 使用 XML long_vib_id=31，经 gain=100、CUSTOM `{0,31}`、replay=0、play=1，stop helper 删除效果。当前生产 FF 的 SINE 请求同时捕获对照；原始 driver worker 以明确的 RAM count=5/32 边界验证范围拒绝与 mailbox 分流。完整 Android 服务、原始 user-copy、PCM、校准和电机未执行，不把原厂 CUSTOM 路径当作自动修复方案。[结果](logs/haptics-service-request-emulation.json)需由统一审计核对服务/XML/属性、生产源码与模块指纹。

`scripts/acquire_firmware.py` 从 `logs/firmware-source-head-20261111.json` 读取四个远程来源，并读取本地 OS4 ZIP。
HTTP 读取固定 ETag、检查 Content-Range；不将 ETag 当作 ZIP 的 MD5。输出位于 `firmware/samples/<sample>`。
payload manifest 与元数据有独立记录；每个分区必须符合 manifest 的完整 SHA-256 才能从 `.partial` 发布为 `.img`。
目前没有完整远程 ZIP 哈希或 OTA 签名认证结论，这与分区完整性校验是不同的检查。

```bash
python3 scripts/acquire_firmware.py --partitions boot init_boot vendor_boot recovery dtbo vendor_dlkm system_dlkm odm_dlkm vendor odm --workers 4
python3 scripts/firmware_facts.py
python3 scripts/compare_firmware.py
python3 scripts/inspect_system_partitions.py
python3 scripts/crypto_inventory.py
python3 scripts/stage_profiles.py
python3 scripts/generate_profile_selection.py
python3 scripts/generate_profile_runtime.py
```

网络失败时只重试对应 `--samples os2-final` 等样本。已发布的分区重新校验后跳过，未完成的 `.partial` 目前从头重做。
每个样本的 `inventory.json` 是进度依据；顶层 `firmware-inventory.json` 在获取命令结束时汇总。
不要同时让两个获取进程写同一样本。

`firmware_facts.py` 在主机用 fsck.erofs 提取文件，不挂载分区、不执行原厂 ARM64 程序；CPIO 不创建设备节点或符号链接。
ELF 分析按节表读取完整 imports/exports，保留原路径、模式、哈希、属性、fstab 和模块清单。
分析结果中 `pending` 与 kernel exports unresolved 必须保留，不能把它们改写成通过。

新增版本需记录包内 system/vendor 身份及 SPL、实际 kernel release、模块符号 CRC、TEE/HAL/TA/库指纹、DT、fstab 与镜像容量。
相同 6.6 或相同 module_layout 不构成复用依据。选择、暂存、模块加载和 RAM 发布已接入维护树；选择预检 60 场景通过，实际启动仍受离线验证边界限制。未知版本不能靠猜测插入模块。

`crypto_inventory.py` 比较每份原厂服务及 DSO 与当前 recovery 的符号闭包。
`stage_profiles.py` 将通过这项检查的组合整理到 `profiles/<sample>/profile.json`，
原文件内容按 SHA-256 去重保存在 `prebuilt/common/profile-blobs`。同名而不同内容的 vendor/ODM firmware 保留独立路径。
这些档案状态为 `prepared-runtime-profile`，由 device.mk 打包；生成器只证明来源，实际镜像与激活结果单独检查。
`TARGET_RECOVERY_DEVICE_DIRS` 显式关闭默认整目录复制，防止 legacy 模块/其他产品资源绕过筛选重新进入镜像。

## 2026-11-12 OS4.0.4 现场证据

第二批现场文件已到达，`python3 scripts/audit_touch_action_observation.py`提取静置/划屏差值与早期启动事实。计数已足够把触摸排查转到v1报文路径，详见[触摸文档](docs/OS4-TOUCH-FAILURE.md)。后续PowerShell入口改为推送设备脚本，避免单行正则引号在adb传递中丢失。当前镜像文件在新linker测试读取时缺失，该测试未通过、未索引；未重新制作镜像或替换成另一份文件。

触摸定向工具：`scripts/collect-touch-no-events.sh/.ps1` 未集成镜像。设备脚本在窗口外读取精确的 `synaptics_tcm/info` 缓存节点，不遍历读取测试/复位节点；`python3 scripts/audit_touch_cached_info.py` 复核两份原始模块的只读属性及格式化/复制调用。`python3 tests/touch_window_analysis_test.py` 检查 10 项合成日志分流；`scripts/analyze_touch_window.py` 仅接受有窗口起止/正常超时的采集目录。没有新的现场窗口，当前仍不能确定触摸根因。范围与结果见 [触摸文档](docs/OS4-TOUCH-FAILURE.md)。

用户日志包位于 `imgs/built/1/os4-touch-20261112-000013.zip`。只读提取与断言由
`python3 scripts/audit_haptics_runtime_observation.py` 执行，机器报告为
`logs/os4-stable-haptics-runtime-observation.json`，SHA-256
`d91b04b1395c9a032250c0c9403501ac56ee2e87fdb3dbcd9398cbf306603397`。
它确认已验证的 `os4-stable` cache、模块阶段完成、`xring_audio_hw_third` live、
`cs40l26_input` event4、FF 能力、`root:input 0660` 及 Recovery 后端选择。

这只能证明输入节点和 Recovery 路由存在。日志没有 Cirrus probe/DSP 启动记录、
与用户效果请求相关的 `EVIOCSFF`/播放返回值或 IRQ 前后差值；累计 mailbox IRQ
无法归属到 GUI 自检还是用户请求。firmware rootfs 写入与属性读取 AVC 均为
`permissive=1`，不能作为复制或读取失败的结论。九个 ODM Cirrus 文件在六个
OS2/OS3/OS4 档案间哈希一致；模块和初始化路径差异仍需离线对照，但这本身不确定根因。
震动目标保持未解决，未改动驱动参数或重建镜像。

当前 `imgs/built/` 中没有历史记录引用的统一 module-state 镜像及其来源档案；
其历史 SHA 不代表当前可交付文件。后续构建后需同时保存镜像及来源清单，
再运行 `scripts/audit_unified_delivery.py`。

## 同步和构建

```bash
python3 scripts/sync_device_tree.py
bash scripts/compile_recovery.sh
```

`patches/series.json` 固定 recovery、sepolicy 和 tinyxml2 三份源码基线与全部结果哈希。同步前在临时目录从 git 原文件重建补丁，
若当前源码既不是原始文件也不是预期结果则停止。旧生成设备目录移动到 `backups/device-tree-*` 保留。
构建会自动同步，再执行 `make -j$(nproc) installclean` 和 `make -j$(nproc) recoveryimage`。
禁止构建脚本静默拉取浮动依赖或靠旧 ramdisk 文件填补缺失产物。

结果在 `/root/AAA/twrp/out/target/product/O1_asic/recovery.img`。
按明确用途复制到新的 `imgs/built/*.img`，保留历史基线。记录源仓库 commit、补丁与配置哈希、日志、产物 SHA-256、
总大小和压缩 ramdisk 大小。当前源码指纹只保证溯源，不代表构建时间戳等因素已经消除、实现逐字节可复现构建。

## 检查

独立ARM64 linker检查：`python3 tests/profile_linker_arm64_test.py --image /root/AAA/twrp/out/target/product/O1_asic/recovery.img`。报告绑定实际传入镜像与提取字节，18项服务依赖加载+6项缺库拒绝+4项小程序重定位对照；`--list`不执行服务重定位/构造/main，完整namespace与加密卷待验。详见[说明](docs/PROFILE-LINKER-ARM64.md)。触摸v1采集脚本的5条执行检查为`python3 tests/touch_debug_collector_test.py`，使用私有文件和替代命令，不操作设备。

当前候选的模块状态回放与旧脚本负向对照见[模块状态记录](docs/MODULE-STATE-ADAPTATION.md)。生产脚本修改后必须重新构建，从新镜像执行完整运行时与状态回放；不能只测试维护树脚本后宣称镜像已包含修改。

```bash
python3 tests/firmware_acquire_test.py
python3 tests/firmware_facts_test.py
python3 tests/devicefix_regression.py
python3 tests/system_resources_test.py
python3 tests/profile_selection_test.py
python3 tests/run_mtp_transport.py
python3 tests/mtp_objects_test.py
python3 tests/mtp_transfers_test.py
python3 tests/profile_core_test.py
python3 tests/wait_services_test.py
python3 tests/settings_persistence_test.py
python3 tests/multiuser_core_test.py
python3 tests/multiuser_backend_test.py
python3 tests/multiuser_routes_test.py
python3 tests/status_readings_test.py
python3 tests/haptics_route_test.py
python3 tests/haptics_ui_test.py
python3 tests/operation_feedback_test.py
python3 tests/archive_restore_test.py
python3 tests/raw_image_test.py
python3 tests/restore_session_test.py
python3 scripts/audit_haptics_profiles.py
python3 scripts/verify_unified_recovery.py imgs/built/recovery-dijun-unified-module-state.img
python3 tests/profile_runtime_test.py --image imgs/built/recovery-dijun-unified-module-state.img --output logs/module-state-profile-runtime.json
python3 tests/profile_runtime_test.py --image imgs/built/recovery-dijun-unified-module-state.img --output logs/haptics-input-profile-runtime-image.json
python3 tests/touch_priority_plan_test.py
python3 tests/haptics_policy_regression.py imgs/built/recovery-dijun-unified-module-state.img --output logs/module-state-policy-regression.json
```

`verify_unified_recovery.py` 按六套 profile 检查同一镜像，并把 OS4 的 HAL/TA/DSO 字节与已保存基线逐项比较。
统一镜像检查器现要求设置原子提交与多用户发现/选择的编译标记，并核对实际生成的 battery sysfs / RTC 构建参数；新增震动运行时路由诊断标记与通用 haptics 分支构建参数检查；并验证 GUI2 新点击接口的编译符号和归档恢复与原始镜像复制诊断标记；它用于最新源码产物。旧 `recovery-dijun-unified-candidate.img` 的检查结果保留在对应历史报告中。
旧 `verify_devicefix.py` 保留用于历史 OS4 候选，不能用于当前统一候选。运行时测试从指定镜像读取脚本、清单和资源；硬件调用由夹具替代。

`host_init_verifier` 检查最终 ramdisk 的相关 rc；`git diff --check` 检查平台改动。
所有回归用临时目录/镜像，不能把 `/dev/block` 或主机物理盘当作测试写入目标。
失败用例必须证明旧实现会失败；单纯复制实现写一个模型不算 S2。

init 检查可重复执行：

```bash
python3 tests/unified_init_test.py imgs/built/recovery-dijun-unified-module-state.img --output logs/module-state-init-verification.json
```

操作完成回放运行完整生命周期实现及备份/恢复/ZIP worker，时钟/分区/硬件边界替换；64 项及旧版 25 项失败见[范围说明](docs/OPERATION-FEEDBACK-ADAPTATION.md)。新的镜像检查还验证 recovery 二进制中的完成通知诊断。

## 交付状态更新

更新 `compatibility-matrix.md`、`simulation-report.md`、`FEATURE-USAGE.md` 与设备树 README。
只把已完成的任务勾选进 `ADAPTATION-GOALS.md`；保留其余阶段的未完成状态。
只有同一 SHA-256 镜像对目标样本的选择与功能检查都完成，才能扩大覆盖声明。

系统分区的 `inspect_system_partitions.py` 使用 dump.erofs 逐目录列出全部条目，只保存身份、init、VINTF、linker、fstab 资源字节，不解包应用 APK。`system-resources.json` 明确列出缺失分区与未读取的文件内容范围。详见 [选择预检](docs/PROFILE-SELECTION.md) 和 [MTP 回归](docs/MTP-ADAPTATION.md)。

归档层回放执行实际 libtar 源码，带 ASan/UBSan；扩展策略 provider 和写入故障为替身。30 项结果不覆盖压缩/分卷或真实加密卷，具体边界与负向对照见[归档恢复适配](docs/ARCHIVE-RESTORE-ADAPTATION.md)。

原始镜像回放执行实际备份/恢复入口和复制函数，普通临时文件模拟块设备；65 项中 6 项另行启用可选 discard，当前 dijun 镜像不启用它。故障/取消和提交后的边界见[原始镜像适配](docs/RAW-IMAGE-ADAPTATION.md)。

交付前执行 `python3 scripts/audit_unified_delivery.py`，核对镜像、707 份当前源码、已索引证据与回归源码绑定。此命令只检查一致性，不把尚未完成的目标或硬件项目改成通过。

震动 runtime 另检查匹配 `cs40l26_input` 名称是否注册，仅作为 input 注册观测，不代表 FF 能力、节点访问权限或实际输出；六包计划同时要求触摸硬依赖闭包先于震动专属依赖闭包。OS4 正式版触摸 P0 与电机输出仍未解决。

恢复会话回放执行实际 manager 预检、原始复制与完整 digest 源码，使用 BoringSSL 对临时文件计算哈希；54 项及旧版对照见[恢复会话记录](docs/RESTORE-SESSION-ADAPTATION.md)。

备份会话回放执行真实 fork/进程组/信号/管道以及 `.info` 写入，归档编码和挂载为替身。55 项及旧版 35 项失败见[备份会话记录](docs/BACKUP-SESSION-ADAPTATION.md)。负向对照预期返回非零；驱动只清理本次临时目录中的进程。补丁同步器支持补丁新建文件，并验证它不存在于固定基线后再应用。

```bash
python3 tests/backup_session_test.py --report logs/backup-session.json
python3 tests/backup_session_test.py --source backups/backup-session-pre-fix --report logs/backup-session-before.json
```

编解码管道回放在私有 chroot 中运行实际 tar/pigz/OAES 与 BoringSSL；46 项用例包含文件往返、短读/信号、损坏流与并发缓冲区。范围见[归档编解码记录](docs/ARCHIVE-PIPELINE-ADAPTATION.md)。

```bash
python3 tests/archive_pipeline_test.py
python3 tests/archive_pipeline_test.py --source backups/archive-pipeline-pre-fix --report logs/archive-pipeline-before.json
```

第二条为负向对照，预期非零。镜像检查新增编解码失败传播的编译标记；生产源码和测试哈希必须绑定同一交付。

MTP 对象测试运行生产 server/packet/database/storage，真实文件、inotify 与线程在私有 chroot 中执行，USB 收发为内存对端；42 项及旧版 28 项失败见[范围](docs/MTP-OBJECTS-ADAPTATION.md)。镜像检查从 `libtwrpmtp-ffs.so` 核对新编译标记，而不是从 recovery 主程序查找它们。

```bash
python3 tests/mtp_objects_test.py
python3 tests/mtp_objects_test.py --source backups/mtp-objects-pre-fix --report logs/mtp-objects-before.json
```

负向对照预期非零；configfs、物理 USB 和 Windows 枚举仍在本组覆盖之外。

MTP 转移与重建采用同一实际协议入口的 48 项回放，含复制/移动内容、句柄保持、I/O 故障、模拟 EXDEV 和队列溢出。范围见[MTP 转移记录](docs/MTP-TRANSFERS-ADAPTATION.md)。

```bash
python3 tests/mtp_transfers_test.py
python3 tests/mtp_transfers_test.py --source backups/mtp-transfers-pre-fix --report logs/mtp-transfers-before.json
```

第二条预期非零。旧对象测试的删除故障注入同时包装 unlink/unlinkat；其 42 项及旧版 28 项失败在当前测试源码下重跑。镜像检查新增 MTP 转移失败与 inotify 重建的共享库编译标记。

MTP 事件生命周期编译原生/兼容生产传输，管道执行普通 AIO；在途取消与错误在 AIO 边界注入，62 项通过。细节见[事件记录](docs/MTP-EVENTS-ADAPTATION.md)。

```bash
python3 tests/mtp_events_test.py
python3 tests/mtp_events_test.py --source backups/mtp-events-pre-fix --report logs/mtp-events-before.json
python3 tests/run_mtp_transport.py
```

第二条为负向对照，当前 56 项失败。传输 runner 现在自动记录实际生产/共享/测试源码哈希；退出测试通过不等于 configfs 切换已验收。

USB 调度与镜像策略：

```bash
python3 tests/usb_init_test.py
python3 tests/usb_init_test.py --baseline --report logs/usb-init-before.json
python3 tests/usb_policy_test.py imgs/built/recovery-dijun-unified-module-state.img --output logs/module-state-helper-policy.json
```

第二条为负向对照，当前 33/42 项失败。新 helper 为静态程序，在专用 enforcing 域运行，遵循平台 recovery 的 rootfs 显式域切换；系统属性策略放在 `sepolicy/system_ext`。没有关闭 vendor 属性前缀或 neverallow 检查。完整边界见 [USB 配置适配](docs/USB-CONFIGFS-ADAPTATION.md)。

MTP 控制报文回放：

```bash
python3 tests/mtp_control_test.py
python3 tests/mtp_control_test.py --source backups/mtp-control-pre-fix --report logs/mtp-control-before.json
```

第二条是同组负向对照，预期 60/66 项失败。修改任何 MTP 顶层源码后需重新运行 transport、objects、transfers、events 及 control 报告以更新源码绑定；完整范围见[控制请求适配](docs/MTP-CONTROL-ADAPTATION.md)。

MTP 启停与消息回放、负向对照及进程夹具清理见[调用层维护记录](docs/MTP-CALLER-ADAPTATION.md)。修改管理器或 MTP 进程代码后，应重跑受影响的多用户/备份/恢复与 MTP 源码绑定回归。

震动协议复核可按[原厂驱动函数模拟](docs/HAPTICS-DRIVER-EMULATION.md)执行。新增模块哈希必须先检查结构布局；不能直接允许未知哈希沿用旧偏移。依赖仅在主机隔离目录，报告绑定原始模块、生产源码、测试及模拟器文件。

注册/上传/擦除及原始 DTBO 合并的复现见[生命周期记录](docs/HAPTICS-LIFECYCLE-EMULATION.md)：`python3 tests/haptics_lifecycle_emulation.py` 为 90 项，`python3 scripts/audit_haptics_devicetree.py` 为六包 48 次合并。后者把基础 DTB 绑定到原始 vendor_boot 字节，并绑定主机 libfdt 源码；不模拟 bootloader 板型选择或真实设备 probe。修改报告或脚本后同步更新 `simulation-report.json` 的证据哈希，再执行交付审计。

生命周期报告逐样本记录原始 `cs40l26_input_init` 的 input 名称、四项 EV_FF capability、96 个效果槽和 callback 地址；运行 `python3 scripts/audit_haptics_lifecycle_report.py` 可独立核验六份 profile 的来源及契约。该证据止于原始驱动向 input core 提出的注册请求，不验证真实 `EVIOCGBIT`/`EVIOCGEFFECTS`、节点权限、IRQ 或电机。完整 `audit_unified_delivery.py` 还要求当前镜像及来源清单；若二者缺失，审计不能通过。

用户提供 OS4.0.4 现场包的可复核解析：`python3 scripts/audit_haptics_runtime_observation.py`。除 event4 震动信息外，还记录 Synaptics IRQ `xiaomi_tpsynaptics_tcm` 累计 3003；该值未和触摸动作关联。延迟 dmesg 仅有一条 Synaptics 温度日志，不能代表启动/probe 日志。当前下一步是同步抓 event3 与一次触摸期间 IRQ 前后值，不需再次收集完整启动包。解析器不声称触摸事件或电机输出已验证。原包位于 `imgs/built/1/os4-touch-20261112-000013.zip`，详细字段在 `logs/os4-stable-haptics-runtime-observation.json`。

GUI 震动后台控制器通过 `python3 tests/haptics_worker_test.py` 复现 16 项并发用例；范围与退出限制见[后台执行记录](docs/HAPTICS-WORKER-ADAPTATION.md)。0027 补丁覆盖控制器、GUI owner 注入、错误轮询与 FF 释放；修改相关文件后必须重新构建并更新受影响证据，不能只改报告摘要。

生产 FF 阻塞联调：`python3 tests/haptics_route_test.py --worker-io --report logs/haptics-worker-ff.json`，4 项通过。该夹具更新后须同时重跑原 22 项路由与其负向对照，以保留同夹具来源绑定。

原厂 start/stop worker 与早期初始化复现：`python3 tests/haptics_playback_emulation.py`（120 项）及 `python3 tests/haptics_probe_emulation.py`（54 项）。后者重新合并六包第 5 条 DTBO，绑定原始属性和零子节点证据，在 PLL 失败边界终止；范围见[播放与初始化记录](docs/HAPTICS-PLAYBACK-EMULATION.md)。两份 JSON 加入交付审计，生产代码未变时无需重复构建。

OS4 原始触摸模块的连接、报告切换、后台固件、ISR 与 parser：`python3 tests/touch_startup_emulation.py`，两包各 44 项，共 88 项。报告为 `logs/touch-startup-emulation.json`，使用固定哈希布局、显式内核/硬件边界和合成报文配置；不能把结果替代用户正式版触摸失效状态。新增驱动哈希应重新分析布局后才加入，范围见[触摸排查](docs/OS4-TOUCH-FAILURE.md)。生产代码未变，无需为这批模拟重新编译镜像。

原始配置/probe 接续：`python3 tests/touch_configuration_emulation.py`，两包共 62 项；运行原始配置复制和应用信息解码，`0x20/0x25` 响应为合成，含配置缺失时已注册 input 却没有事件的链路。`python3 scripts/audit_touch_devicetree.py` 重建 host libfdt，核对两包第 5 条 overlay、原始 DTB、直接 phandle 目标和 ODM 固件→profile blob。两份报告已加入交付审计；物理 SPI/IRQ、电源和实际板型选择仍未验证。

SPI/供电接续：先运行 `python3 scripts/audit_touch_devicetree.py`，再运行 `python3 tests/touch_spi_emulation.py`，两包共 58 项。前者同时保存原始触摸配置子节点，后者实际运行 SPI probe、Xiaomi DT 解析、GPIO 请求、供电和复位；平台注册调度、物理电源/引脚与延时为边界；接续用例显式执行原始平台 probe 与硬件回调。报告纳入交付审计，不能以模块或平台设备存在宣称触摸就绪；详细返回路径见[触摸排查](docs/OS4-TOUCH-FAILURE.md)。

传输/panel：`python3 tests/touch_transport_emulation.py` 执行两包 86 项原厂 SPI 缓冲、传输、休眠等待与识别入口场景；`python3 tests/touch_panel_emulation.py` 执行 22 项原厂 panel setup 场景。全零 lockdown 的预算耗尽是专门验证的重复路径，不能推广为其他超时自动成功。两份报告绑定原始模块、DT、测试及模拟器依赖，纳入交付审计；控制器响应、flash、panel 包装注册与内核调度为显式边界。当前镜像不变，尚不能声明触摸恢复。

包装层与 PLL：`python3 tests/touch_wrapper_emulation.py` 执行两包 50 项原厂 panel/input/raw 入口场景，callback 通过显式 host bridge 执行另一个 Synaptics 实例中的原始切换函数；不等同于完整内核链接。`python3 tests/haptics_pll_emulation.py` 执行六包 80 项 PLL 寄存器与 OS4 芯片识别场景。生产镜像不变，完整协议/firmware/DSP/IRQ 与硬件仍待验证；报告绑定全部输入并纳入交付审计。

协议识别：`python3 tests/touch_identification_emulation.py` 执行两包共 62 项原始 v1/v2 detect、ID parser、长度协商和操作表安装。message/continued-read/command 边界明确提供合成响应；v2 CRC6 检查执行原始代码，但不代表完整帧或物理传输已验证。报告记录零长度字段、错误恢复、短缓冲、无效头及 command 9 失败的状态，详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)。生产代码未变时无需重编译镜像。

报文/ISR：`python3 tests/touch_message_emulation.py` 执行两包共 90 项。v1 原厂 read_message/continued-read 使用合成分段字节，接续原始事件复制/parser/ISR；v2 execute_cmd_request 仍是明确的 command 响应边界，不能宣称完整 v2 传输。包含错误标识重试、分配失败、空报告复用旧长度/旧坐标、pending command completion 和 status=4 分发抑制。新报告绑定导入脚本、模拟器和驱动指纹，交付审计检查关键结果；不将两包共有的故障机制认定为正式版特有回归，当前镜像 `recovery-dijun-unified-module-state.img` 未改。

静态加载时序：`python3 scripts/audit_touch_load_order.py` 重新解析两包 vendor_boot 与当前镜像的 ramdisk、init imports/模块动作，核对 C++ cache→modules 和 firmware 发布先后。检查通过仅说明所查文件符合该顺序，未执行合并/init/模块加载；报告绑定原始镜像和相关源码，由交付审计复核。

v2 帧：`python3 tests/touch_v2_command_emulation.py` 执行两包 78 项，原始 command/read/write/CRC6/CRC16、序号、分段、报告切换、parser/ISR 均执行，物理字节/内核服务为夹具。最后三项把原始配置/应用信息获取接入该帧回路；其余独立场景仍有合成配置命令边界。CRC 耗尽不一定返回负值，需同时检查 ID、配置/报告字节和事件；不能将该机制写为已证实实机根因。结果与反汇编输入指纹进入交付审计，当前 `recovery-dijun-unified-module-state.img` 不变。

v2 启动接续：`python3 tests/touch_v2_startup_emulation.py` 执行两包 44 项，从清空的协议/模式/操作表和尺寸开始，实际探测、协商、连接、配置与应用信息恢复、切换模式、后台及 ISR。应用信息失败会执行三次事件读取再重发；固件请求/更新失败可跳过配置重取仍注册 input。模式恢复和配置恢复必须分别检查，不能只断言连接返回 0 或 input 存在。panel、固件更新、IRQ 注册、内核服务和顺序调用后台仍为显式边界，范围见[触摸记录](docs/OS4-TOUCH-FAILURE.md)。新报告和关键分支纳入[交付审计](logs/touch-v2-startup-delivery-audit.log)，无生产改动无需重复构建。

v2 panel/flash 接续：`python3 tests/touch_v2_panel_startup_emulation.py` 执行两包 32 项；从原始 DT 属性解析到 panel、真实 v2 报告切换帧、后台和 ISR，另有六项运行原始 flash-area/boot-info/boot-config/read/模式返回。全零 lockdown 只在指定场景允许预算耗尽，并断言未到注册或后台；不能把其他超时当成功。报告开启写失败后的合法报文/status4 都是显式响应，不能当作真实控制器状态。报告绑定所有导入程序和 DT/驱动/模拟器来源，由[交付审计](logs/touch-v2-panel-startup-delivery-audit.log)复核，当前 module-state 镜像未改，无需重编译。

原厂触摸固件解析：`python3 tests/touch_firmware_emulation.py` 执行两包 26 项，使用原始固件字节与原始 ARM64 parser/ID 比较；CRC 服务独立计算。更新匹配返回之后仍须验证原始应用配置恢复及 ISR，不能只看 return=0。不同 ID/force 在原始 flash-access identify 超时处停止，未执行擦除/编程；错误 CRC 与已有配置/缺配置两种后台状态分别断言。worker 为 void，结果记为 null。报告和关键分支纳入[交付审计](logs/touch-firmware-delivery-audit.log)，当前镜像不变，无生产改动无需编译。

震动原厂 DSP 固件：`python3 tests/haptics_firmware_emulation.py` 执行两包正常/校准共 64 项，独立容器清单逐段核对原始 raw write 字节/地址，执行原始 parser、系数初始化和 get_reg。空算法表的 parser=0 不等于系数可用；匹配算法表为明确合成。正常/校准使用各自算法 ID，不共享假定布局。完整边界见[记录](docs/HAPTICS-FIRMWARE-EMULATION.md)，新证据及关键分支纳入[交付审计](logs/haptics-firmware-delivery-audit.log)；当前镜像未改。

震动上传接续：`python3 tests/haptics_upload_emulation.py` 执行两包 72 项，从原始芯片身份到 PM/shutdown、wmfw parser、系数初始化/版本检查及配置入口。最深场景在真实配置入口第一条 MEM_RDY 更新明确失败；原始 `.bin` parser 因合成算法版本拒绝时仍可继续，不能将请求/读取参数当作加载成功。预处理失败未释放已请求固件的原厂行为保留；完整上传预算显式设为 100 万指令/10 秒，超限失败。报告绑定 9 份实际 ODM 文件/样本和所有导入程序；[交付审计](logs/haptics-upload-delivery-audit.log)复核，当前镜像未改。

原厂 packed 参数接续：`python3 tests/haptics_coefficients_emulation.py` 执行两包 16 项，独立解码 wmfw packed X-memory 算法表并提供 regmap 读取值，实际执行原始 WMDR 参数 parser；独立计算所有参数写入地址/长度/摘要。正常/校准新增 34/28 次参数写入；主参数缺失/版本错/首写失败仍可到 config，必须核对完整写序列。最深仍终止于 MEM_RDY 注入失败，未执行 DSP；[交付审计](logs/haptics-coefficients-delivery-audit.log)核对来源，当前镜像未改。

震动 DSP 配置接续新增两包正常/校准共 [36 项原始代码模拟](logs/haptics-config-emulation.json)：执行 MEM_RDY、CALL_RAM_INIT、写序列解析/写入、HALO 检查及 IRQ mask，最深到 GPIO 读取注入失败。CALL_RAM_INIT 连续写失败尝试 20 次，返回 -62；其成功后原厂立即设 `fw_loaded=1`，之后序列读取/写入、HALO、IRQ 或 GPIO 失败仍保留 1，因此此标志不能作为配置完成或可震动的证据。序列为全 FF 立即结束的显式合成数据，PM/HALO/IRQ 状态及邮箱确认均为夹具，没有执行 DSP。生产树和当前镜像未改；触摸 P0、震动和全部 12 组未完成项保留。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/haptics-config-delivery-audit.log)。

触摸 P0 继续：新增两包 [32 项原始 flash 失败/后台接续](logs/touch-flash-failure-emulation.json)。原始块检查、擦除命令、首两段编程命令及复位实际执行，命令页范围/地址/固件字节逐项核对；传输响应与 flash 几何为夹具，全部场景以注入错误结束，没有真实写入或完整编程成功。更新失败仍清 pending 并通知完成；后台三次擦除失败后仍注册 input，缺配置时即使复位回 application 也没有坐标。已有配置可解析明确提供的合成报文，并不证明 bootloader 会真实发报告。两版一致，当前故障根因未定。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-flash-failure-delivery-audit.log)。生产树和当前镜像未改，触摸、震动及整体 12 组目标保持进行中。

触摸完整命令接续：两包新增 [26 项原厂完整编程/复位/后台配置模拟](logs/touch-flash-complete-emulation.json)，逐项核对全部 625 段编程请求与两条擦除命令，配置单独更新为 25 段。所有传输确认/boot-info/复位及配置响应均为显式夹具，未执行物理写入。原厂 update 可在 reset 响应仍为 bootloader 时返回 0，随后后台仍注册 input、配置为零且无事件；app 模式下配置获取超时/空配置也无坐标。成功重取配置可恢复合成 ISR，末段写失败后重试则核对 1250 段。测试预期曾错误假设 bootloader 会主动切回 app，已按原始分支纠正；不是生产修复。详见[范围](docs/OS4-TOUCH-FAILURE.md)与[交付审计](logs/touch-flash-complete-delivery-audit.log)。当前镜像未改，触摸 P0、震动及整体目标继续进行中。

震动 probe 接续新增两包 [16 项原始启动链模拟](logs/haptics-probe-upload-emulation.json)：清空设备上下文后由原始 DT 解析、供电/复位、PLL 与芯片识别接入实际固件/参数上传和配置，完整核对 68 次 raw write；最深到 GPIO、boost DCM/IPK 后的 `0x3804` 读取注入失败。所有错误均传播到 probe 并进入 remove 边界，未到 input 初始化；后期错误时 `fw_loaded=1` 仍存在，不能当作 probe 成功。原始合并 DT 属性有来源绑定，电源/寄存器/邮箱/序列与 remove 内部清理仍为夹具；完整 DSP、IRQ、电机和 OS2/OS3 此层接续待继续。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-probe-upload-delivery-audit.log)。生产与当前镜像未改，触摸 P0 和完整 12 组目标继续保留。


IRQ/PM 复现：`python3 tests/touch_irq_emulation.py > logs/touch-irq-emulation.log 2>&1`。两包 40 项，实际执行原厂 `syna_spi_enable_irq`、`syna_tcm_enable_irq`、系统 PM 回调及 parser/ISR。IRQ depth 在显式 kernel 服务夹具中更新；等待只记录请求，不测时延。必须保留 stale enabled/depth、150 次 pending 等待、wake 失败与 PM 标志不阻断所测坐标等断言。只有 `unchanged-depth-budget` 用例要求深度不变时预算耗尽；不得推广到其他超限场景。报告绑定原厂模块、反汇编、全部导入程序及模拟器，纳入[交付审计](logs/touch-irq-delivery-audit.log)。当前候选没有生产改动，无需重编译；显示休眠/恢复、包装层接续和真实 IRQ 并发仍未覆盖。


显示恢复复现：`python3 tests/touch_display_resume_emulation.py > logs/touch-display-resume-emulation.log 2>&1`。旧 OS4/正式版各 24 项，原始 `syna_dev_suspend/resume` 和 sensing、sleep/dynamic、app/config、报告切换及 ISR 实际执行；send-command、复位读报、无手势模式、温度/power/pinctrl 与 IRQ 仍是显式夹具。应用信息失败的 typed read-message callback 保留 CFI，返回 -110、每次排空单独计数，不能留空指针或伪造成功。报告必须保留恢复失败后 active/第二次跳过，以及新显示周期重新取配置恢复的配对断言。显示相关 pending 最多三次 20 ms，不得套用独立 `syna_tcm_enable_irq` 的 150 次。来源/关键状态纳入[交付审计](logs/touch-display-resume-delivery-audit.log)。无生产变化无需编译；真实通知调度、手势开启分支、硬件状态和包装层完整接续继续待验。


显示通知链复现：`python3 tests/touch_notifier_emulation.py > logs/touch-notifier-emulation.log 2>&1`。原始 wrapper panel 参数来自绑定 DT 的原始 Synaptics setup；回调经明确带 CFI 签名的 host bridge 接入独立原始 Synaptics 地址空间，不等于内核符号链接。两包各 15 项核对原始 notifier/调度/worker、dispatch 和恢复；必须保留失败瞬间的两层状态快照，不能被后续恢复覆盖。fixture `__flush_workqueue` 只接受空 pending；非空情况报错，不能用返回 0 假装任务已完成。队列拒绝不入 pending，所有 worker 为 void、不用遗留 x0 当成功。IPC、时间、IC-mode、温度和复位仍是边界。[交付审计](logs/touch-notifier-delivery-audit.log)绑定全部来源与状态。非空 flush、并发显示通知、手势、IRQ/硬件继续待验，无生产变化不重新编译。


震动 boost 后复现：`python3 tests/haptics_postboost_emulation.py > logs/haptics-postboost-emulation.log 2>&1`。两包 26 项继承完整原始 probe/upload，不改已有共用模拟器。独立 WMFW/WMDR 清单核对 68 次写入，记录 DT read-u32 目的偏移 `vbbr-thld=0x1b74`、`vpbr-thld=0x1b90`，核算 /55000、/47000 转换及高字节保留，避免复用原始乘法常量自证。高/低写序列失败精确注入第 19/20/21/22 次 bulk，核对 probe -5、remove 边界、未 input；没有真实清理成功结论。只给明确读取地址提供合成值，不对未知寄存器默认返回 0。范围见[记录](docs/HAPTICS-FIRMWARE-EMULATION.md)，[交付审计](logs/haptics-postboost-delivery-audit.log)绑定来源和关键状态；无生产变化无需编译。


震动 runtime PM/logger/ASP 接续：两包新增 [16 项原始 probe 故障模拟](logs/haptics-runtime-config-emulation.json)，核对 68 次原厂固件/参数 raw write，执行 PM setup/entry/error recovery/exit、logger 和 ASP。resume -5 的原始错误处理会 set-status(0) 并调用 PM exit；logger/ASP 读写/分配/写序列故障均传至 probe/remove，未到 input，fw_loaded=1 不能证明成功。COUNT/SOURCE 初始 0、PM 服务/定时器和序列等为显式夹具，没有 DSP/电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)与[交付审计](logs/haptics-runtime-config-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动和完整目标保留；后续为 B2 邮箱、波形计数及 probe/input 接续。

复现命令：`python3 tests/haptics_runtime_config_emulation.py > logs/haptics-runtime-config-emulation.log 2>&1`。保持 PM 错误恢复与 set-status/exit、logger 地址来源、ASP 原始 reg_sequence、分配失败和完整写序列断言；只扩展该子类显式服务边界，不修改已绑定的共用模拟器。无生产变更无需编译。


触摸 IC-mode 接续：两包新增 [22 项原始模式函数/通知恢复模拟](logs/touch-ic-mode-emulation.json)，移除整体 IC-mode 成功替身，核对模式 2 的 `0xc7 / 31 0a 00`。dispatch 返回显示 resume 的保存值，IC 命令超时/分配失败不向上传播；重复亮屏跳过回调。配置失败后该命令仍不补回报告配置，合成 ISR 无坐标。IC 函数遗留 x0 不作为成功返回，控制器响应/IRQ/调度仍是夹具。详见[范围](docs/OS4-TOUCH-FAILURE.md)、[审计](logs/touch-ic-mode-delivery-audit.log)。没有根因或硬件恢复结论，生产及当前镜像不变，触摸 P0、震动和全部 12 组继续进行中。

复现：`python3 tests/touch_ic_mode_emulation.py > logs/touch-ic-mode-emulation.log 2>&1`。保持原始命令字节/长度/CFI、无命令分支和 notifier 保存返回值断言；直接 IC 函数遗留 x0 不作为返回约定。无生产变化无需重编译。


震动波形/IRQ/input 接续：两包新增 [26 项原始 probe 模拟](logs/haptics-wave-irq-emulation.json)，从 B2 mailbox/波形诊断推进到 27 次 IRQ 请求、input/FF 回调与 sysfs 初始化、MFD 故障。计数读失败两次各重试 20 次，诊断错误未阻断后续 IRQ；B2/播放配置/IRQ/input 失败则传回 probe。input init 成功置注册标志后 MFD 失败，probe 仍失败。内核 IRQ/input/FF、合成计数 5/0、PM/HALO/mailbox 与序列均为明确夹具，全部场景以注入错误结束，没有完整 probe/DSP/电机成功结论。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[审计](logs/haptics-wave-irq-delivery-audit.log)。生产和镜像不变；后续接 probe 自带 upload/play/erase 自检，触摸 P0、震动与全部 12 组目标保留。

复现：`python3 tests/haptics_wave_irq_emulation.py > logs/haptics-wave-irq-emulation.log 2>&1`。保留 68 次 raw write 独立核对、计数 40 次错误读取、27 个 IRQ 请求与准确失败序号、原始 FF 能力及回调指针、MFD 失败时 input 标志已置位的断言；未知服务和有限执行预算耗尽仍失败。无生产变化无需编译。


震动 probe 自检接续：两包新增 [16 项原始 probe→上传/启动/擦除 worker 模拟](logs/haptics-probe-selftest-emulation.json)。原始 ordered 队列标志 0x20012/max_active1 与顺序模型核对，非法逆序被拒绝；七条执行场景/包实际到 probe 返回。PM、启动写入、mailbox 和上传参数失败均可被最终 probe=0 掩盖，erase PM 失败还留下效果链表。寄存器/PM/IRQ/input/mailbox 仍为明确夹具，没有 DSP/完成中断或电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[审计](logs/haptics-probe-selftest-delivery-audit.log)。生产与镜像不变；继续 IRQ/完成链、旧版初始化和完整 GUI，触摸 P0、震动及全部 12 组目标保留。

复现：`python3 tests/haptics_probe_selftest_emulation.py > logs/haptics-probe-selftest-emulation.log 2>&1`。保持 ordered/max_active 检查、非法模型拒绝、原始 worker 实际执行与参数/邮箱/结果/效果链表断言；上游 workqueue.h 是参照来源，不能标作设备内核源码。无生产改动无需编译。


非空通知队列与震动 IRQ 续接：新增两包 [16 项原始触摸 pending-work flush](logs/touch-pending-flush-emulation.json)和 [30 项原始 mailbox IRQ/状态/完成调用](logs/haptics-irq-completion-emulation.json)。触摸在原 notifier 的 flush 边界保存上下文，执行旧 worker 后继续排新任务；正常顺序不丢转换，配置失败后重复亮屏仍跳过下层、cfg=0，新的 off/on 才可恢复合成坐标。震动从实际注册 handler 接入可变合成环，核对 ACK 回绕、GPIO 触发/完成区别、锁门控及 complete 调用；读写失败仍可返回 IRQ_HANDLED。真实调度/物理 IRQ、内核 completion 等待和 DSP/电机仍未验证，不能据此认定当前实机根因或功能已修复。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)、[震动记录](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/pending-flush-irq-delivery-audit.log)。生产与 `recovery-dijun-unified-module-state.img` 未改，没有重编译；触摸 P0、震动和全部 12 组目标保持进行中。


触摸跨模块注册续接：新增两包共 [16 项原始 DT/panel/connect/后台→Xiaomi panel/input 注册](logs/touch-joined-registration-emulation.json)。参数直接来自原始 Synaptics setup，双 ARM64 空间显式桥接；callback 表和内核 input 服务仍为夹具。正常分支核对原始轴/slots 与合成 ISR；input 分配/注册失败则 wrapper 返回空，两版 Synaptics 均先写 input+0x2c0、后检查空指针，模拟捕获精确未映射写并终止，不继续 ISR。此为原厂错误路径证据，尚未绑定此次用户故障，不改写原厂模块。panel 队列失败不阻断后台独立 input 注册，配置超时则即使注册成功仍无合成坐标。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)、[交付审计](logs/touch-joined-registration-delivery-audit.log)。生产与当前 `recovery-dijun-unified-module-state.img` 不变，触摸 P0、震动和整体 12 组目标保持进行中。


震动主动擦除/完成等待续接：新增两包共 [30 项原始 probe→生产 FF 上传/播放→mailbox IRQ→erase 等待](logs/haptics-active-erase-emulation.json)。生产效果为 80 ms/8 ms/64，原始写入独立核对。正确 done 通过原始 handler 解除等待；停止消息通知不同 completion，读/ACK 错误或缺完成则请求 580 ms 后返回 -62、保留效果。超时后迟到 done 可再次 erase 释放；新 start 清除先前 complete_all，第二效果缺 done 仍超时。无启动 IRQ或启动命令失败时 erase=0 也不能证明播放发生。单等待者 completion/HZ/顺序调度是显式模型，上游 completion 源码仅作契约参照，物理 IRQ/DSP/电机未验证。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[交付审计](logs/haptics-active-erase-delivery-audit.log)。生产和当前 `recovery-dijun-unified-module-state.img` 未改，没有重编译；触摸 P0、震动及全部 12 组目标保持进行中。


震动 regmap IRQ 前置回调新增两包 [12 项原始执行](logs/haptics-pre-irq-emulation.json)：probe 取得原始 chip 指针，确认仅注册 pre、post=null、27 子 IRQ；pre 实际执行 PM resume→`0x10004` 状态读→PM suspend。状态读错误/PM 错误返回 -5；状态 bit0=0 会日志后返回 0。上游 v6.18 regmap 参照在调用 pre 时忽略其返回值，故显式安排子 handler 验证 pre 错误不必然阻断 mailbox done；kernel dispatcher/status-mask/nested IRQ 未执行，不能推断本机实际中断链。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-pre-irq-delivery-audit.log)。生产树和镜像未改；震动仍未解决，触摸 P0、全部 12 组保持进行中。


补充 recovery 震动执行检查点：离线核对发现 OS4 ODM 暴露 AIDL vibrator/vibratorfeature 服务，而 recovery 的实际调用链走 `/dev/input/event*` Force Feedback，不调用 Android 服务。OS4 module plan 包含原始 `xring_audio_hw_third` 与全部 CS40L26 固件，runtime 在缓存后按计划插入并检查 initstate；这仅证明候选设计和 host fixture 路径，不能证明启动时 `/dev/input` 已出现能力匹配的 `cs40l26_input` 节点或设备节点可访问。下一步聚焦建立模块插入→I2C probe→input 注册→节点权限→FF ioctl 的静态/主机证据，并覆盖 OS2/OS3 模块差异；不把 HAL manifest 或脚本 loaded 状态当作震动已用。当前产物不变，触摸 P0、震动与 12 组目标继续进行中。
# 校准恢复证据维护（2026-11-12）

分区操作0029：运行`python3 tests/partition_operation_path_test.py`验证真实入口路由/错误传播；底层分区操作为替身。旧源码保留在`logs/partitionmanager-before-operation-paths.cpp`，同组46断言20失败。补丁新增至series并更新partitionmanager结果哈希；生产变更已installclean/30并发重建partition-paths候选。涉及挂载owner变化时同时跑nested_partition_path_test、settings_persistence_test、backup_session_test、restore_session_test和profile_core_test。不要把路由成功写成格式化/fsck或数据删除已经验收。

A1现场分支：运行`python3 tests/haptics_a1_calibration_review.py`，原始probe→DT字段在fw_upload注入失败处停止，再显式转接至原始parser/config上下文。16项结果区分A1默认Q=0写入与B2跳过Q；寄存器/PM为夹具，不是完整A1 probe、实测Q或静音根因。新增默认值/恢复策略前，需设备自身校准值和原厂范围依据；禁止使用测试合成值或更改保护阈值来追求模拟通过。

`python3 tests/haptics_calibration_restore_emulation.py` 执行两份精确 OS4 原厂服务的校准恢复/读取/写 helper，共 16 项。结果 `logs/haptics-calibration-restore-emulation.json` 已索引；文件系统和 libc 等为夹具，禁止使用其中合成值作为设备校准。原始 B2 q_stored 拒绝、写失败未传播及调用方置标志的边界见 [震动记录](docs/HAPTICS-ADAPTATION.md)。本次无生产改动或构建；后续须核对系数默认值及播放依赖，再决定初始化适配。

2026-11-12 震动状态采集：`python3 tests/haptics_state_collector_test.py`执行11项私有文件场景，并从两份OS4原始ELF验证default/calibration七项属性名称/权限/show指针。修改采集allowlist时必须先审核原始show及其调用链；禁止递归cat sysfs/debugfs、读取触发校准/任意寄存器接口、将overprotection_gain称为通用FF增益。保存dmesg/IRQ baseline后才读可唤醒DSP的状态。缺节点/未挂载/读错误均记录partial，不清日志或自动运行播放。详细用法见[采集说明](docs/HAPTICS-STATE-COLLECTION.md)。工具不进入ramdisk，当前生产镜像不变，无须以此重新编译。


2026-11-12 嵌套分区路径：维护补丁`dtsrc/O1_asic_dual/patches/0028-nested-partition-paths.patch`追加到series，修复persist路径被截为/mnt。变更分区匹配时运行`python3 tests/nested_partition_path_test.py`，覆盖真实lookup/mount/InfoManager guard；单独settings_persistence_test使用布尔分区替身，无法验证分区匹配。新最终候选为`recovery-dijun-unified-touch-settings.img`；普通触摸报告脚本随profiles/runtime打包，requested只表示已请求，不是触摸ready。不要用旧镜像的同镜像证据代替新产物验证。

2026-11-12：`python3 tests/filesystem_tools_image_test.py`从当前fac3c815候选提取ARM64文件系统工具，在QEMU中对私有普通文件执行。输入镜像哈希固定，变更交付后须先复核再更新；15项结果与局限见[说明](docs/FILESYSTEM-TOOLS-EXECUTION.md)。这不是主机mount/loop或真实磁盘测试。

2026-11-12当前候选`recovery-dijun-unified-fsck-result.img`新增[ext修复结果处理](docs/FSCK-RESULT-ADAPTATION.md)：e2fsck退出1表示已修正，接受为成功；需重启/未修正/执行失败仍失败。`python3 tests/filesystem_tools_image_test.py`默认绑定此镜像，17项实际工具检查通过；完整GUI/内核/加密未验证。

2026-11-12：当前clock-failure候选增加0031时间读取失败处理，`python3 tests/status_readings_test.py --report logs/clock-failure-status-regression.json`共28组；`--data-source logs/data-before-clock-failure.cpp`可复现旧实现3失败。方法抽取和时钟边界替身不等于硬件RTC测试，见[说明](docs/CLOCK-FAILURE-ADAPTATION.md)。

2026-11-12：公共设置行0033修正文字/空白区域点击无效，保留toggle作为业务target，整行使用统一press cancel guard。运行 `python3 tests/settings_row_test.py`：20项真实LVGL输入与生产general回调；旧组件 `--component logs/settings-row-before/check_row.cpp --output logs/settings-row-before.json` 同组8项失败。存储/电机仍为替身，不能据此接受真实persist或物理震动。新settings-row候选已installclean/30并发构建及716来源/封装核对；详见[设置适配](docs/SETTINGS-ADAPTATION.md)。

2026-11-12：`python3 tests/haptics_dapm_route_review.py`执行20项原始PCM widget回调，并从两份OS4 ELF重定位还原DAPM routes/widgets/enum。固定结构布局96/320字节仅适用于审核模块哈希，所有名称/回调指针完整核对；Source1=PCM，不将其解释为通用FF使能。显式事件不替代内核DAPM调度/PCM流；regmap/mailbox/SVC值为夹具。`scripts/audit_haptics_dapm_route_review.py`绑定证据/来源/索引/当前镜像，生产未改。

2026-11-12：运行`python3 tests/video_timeline_test.py`生成并检查3份12.5秒多Cluster样片，实际encode回调同步，10灰度块逐帧编号，原生FFmpeg解码1313帧与30次输入seek。`scripts/audit_video_timeline_delivery.py`核对EBML长度、三Cluster、0/5/10秒关键帧、帧号/PTS/末尾空输出及依赖/工具/当前镜像来源。不是实时性能或长时间稳定性测试，无生产改动。

2026-11-12：`python3 tests/haptics_protection_irq_review.py`执行44项原始OS4保护IRQ函数，包括两类日志通知、四类故障及error_release的读/三次写失败。0x2034显式初值不随写更新；未执行硬件或IRQ dispatcher。`scripts/audit_haptics_protection_irq_review.py`核对bit/序列/短路/来源与镜像，禁止把IRQ_HANDLED或解除日志当作电机输出或实际解除保护。

2026-11-12：`python3 tests/haptics_firmware_publication_test.py`读取simulation-report当前镜像，提取实际脚本/profile/CAS并运行12次六版本双槽激活；624个insmod替身边界核对9份ODM文件。cache后删除fixture原厂firmware目录，仅模拟路径不可用，非内核unmount。原始parser/WMDR解码核对OS4 vendor/ODM参数差异，不解释DSP语义或改参数。`scripts/audit_haptics_firmware_publication.py`绑定镜像、脚本、全部边界哈希、原始ueventd顺序及来源。硬件/firmware loader未执行，不能用此验收物理震动。

震动现场 A1 接续：两份 OS4 共 16 项原始 probe→固件/配置→自检→生产 FF/IRQ/erase 检查通过。A1 原始 ROM 与 B2 不同，加载后 PM 状态需显式转换；过时状态、errata 序列/Q/固件写错误均阻止进入 input。A1 在同一上下文写默认 Q=0，仍不能推导静音；生产80ms/8ms/64请求在显式完成消息下擦除成功，缺 done 则580ms请求后-62。内核/PM/寄存器/邮箱/全FF序列/DSP仍有明确模拟边界，没有电机恢复结论。见[结果](logs/haptics-A1-joined-review.json)、[范围](docs/HAPTICS-ADAPTATION.md)。生产 settings-row 镜像未改，震动与完整12组继续进行中。

挂载模式确定修正：补丁0034把system/vendor切换改为操作锁内的检查/卸载/修改/重新挂载/失败恢复流程；检查两个目标的挂载返回值，全部成功才提交全局模式，保留回滚失败日志和实际未恢复状态。15项生产函数主机检查通过，旧实现同组8项失败。installclean后30并发新候选recovery-dijun-unified-mount-mode.img，SHA256 `848096d4b42b41926e2741ba4a34ef1ec4922aaa66036281724e7a2d65b652f1`，717来源及封装/新二进制核对通过。详见[范围](docs/MOUNT-MODE-ADAPTATION.md)。不是震动或一般设置故障修复结论；全部12组保持进行中。

mount-mode构建后验证：同镜像9组/102次profile阶段调用通过，717来源及新二进制核对完成；GUI/FF库字节与settings-row一致，生产挂载事务15项通过，旧实现同组8失败。未验证实际挂载/界面/震动，目标仍进行中。

震动FF core边界补齐：16项上游6.18原函数→原厂A1停止/擦除接续确认EVIOCRMFF先stop0，只有stop确认不能代替播放done，缺done可-62；flush忽略该错误仍返回0。随后现场43次stop/erase独立配对全部erase_ret0（最大10.491ms），因此该模拟风险不能解释已有无震动现场。上游不是本机vendor源码，PM/寄存器/队列/DSP仍有明确边界；不改生产，当前mount-mode候选保持不变。见[结果](logs/haptics-ff-core-review.json)、[现场](logs/haptics-erase-field-observation.json)、[范围](docs/HAPTICS-ADAPTATION.md)。震动/完整12组继续进行中。

震动六版本供电引用核实：原始DTB+overlay5重新合并并核对，VA均mldo8→常开mbuck10，reset为低有效GPIO_105，IRQ为GPIO_046/低电平。六个原厂模块supplies均VP/VA，但DT只声明VA，与现场VP dummy警告相符；不等于物理缺电或应添加VP。两份OS4提取init相关命令除通用LED trigger外没有Cirrus输出write，二进制服务/实际供电未覆盖。见[拓扑](logs/haptics-power-topology.json)及[范围](docs/HAPTICS-ADAPTATION.md)。不改生产/不重编译，震动与完整12组继续未完成。

最新交付：`recovery-dijun-unified-otg-selection.img`，SHA256 `aaa4b25c1bd58a0b61508288a479d824f38701c38d2ed606530b39c503181ef7`，718来源/封装及installclean后30并发构建通过。0035修正存储选择容量失败/设备消失/设置提交失败时仍提交或留下新挂载的问题，15项真实选择+UpdateSize方法检查通过，旧实现同组12场景失败；底层设备和I/O仍为替身，详见[范围](docs/STORAGE-SELECTION-ADAPTATION.md)。设置20项交互/21项保存/31项路径回归通过，不能替代用户设置操作前后日志。USB发现、写入中拔除、现场设置和物理震动未验证，全部12组保持进行中。

复现 `python3 tests/otg_selection_test.py`。选择修改须绑定真实UpdateSize而非纯布尔尺寸替身；不要将通用UpdateSize的可移除挂载失败返回true解释为选择成功。0035维护在series，源树同步后重建；同镜像runtime结果独立记录，不沿用旧镜像审计。

同镜像验证收尾：9组/102次profile阶段调用通过，718份构建来源仍一致，设置交互20/保存21/路径31与挂载模式15回归通过；当前交付审计见 `logs/otg-selection-delivery.json`。硬件与完整12组验收仍未完成。

震动校准恢复接续：新增[14项原厂服务→同一probe后A1/B2 sysfs store检查](logs/haptics-restore-joined-review.json)。A1接受合成z/f0/q，真实系数地址依次0x280212c/0x2802128/0x2802150；B2拒绝Q。越界F0、PM失败或Q写失败传回stdio错误，原服务仍继续，不能以恢复函数结束认定就绪。有效合成值恢复后生产SINE依然提交20/125/64并在显式done下擦除；这不是DSP/电机或校准必要性的证明。本机persist值与寄存器读回仍未知，未向生产加入未经现场值核对的恢复或校准。生产otg-selection候选不变、无需重编译；震动及完整12组保持进行中。

震动原厂波形核实：新增[10项WMDR波形表/原始parser/CUSTOM请求检查](logs/haptics-stock-wave-review.json)。从原厂cs40l26.bin独立解码43条记录，与同一A1 probe的原始解析输出逐条核对类型、flags、offset、length和数据SHA。原厂long_vib_id31对应type12、offset1916、length7words，数据SHA `a7a957218ddc595e63d4dc8097d5b7aa0b92f72f96104307a1d8bb4f41d4704e`。以文件解析数量43作为显式regmap读边界，原始CUSTOM31/42 worker成功，43越界-22、空表-61、20次读取失败最终-62。排除所查OS4参数包缺波形31的疑点；不证明DSP加载/电机输出，也不据此把生产SINE换成CUSTOM。当前otg-selection镜像未改，震动及完整12组仍进行中。

CPU温度身份核实：新增[六版本原厂DT/驱动注册证据](logs/thermal-topology.json)。匹配base+overlay5合并后，cpu-crg均引用已启用的tsensor@EB008000通道0，同控制器22个物理传感器、整树38个thermal区域。原始模块通过devm_thermal_of_zone_register注册；通道0不等于Linux thermal_zone0编号，当前固定路径仍未获运行时身份验证。GUI2没有温度字段，后续应按type=cpu-crg匹配并补显示、缺值/晚注册/编号变化检查。此为静态证据，无生产修改/重编译；震动与完整12组目标继续未完成。

最新交付更新：`recovery-dijun-unified-thermal-identity.img`，SHA256 `338a4bf6c4e4563a30e6d26eecfbf6ac0793d5158974753a107eb38674f455db`。0036修正CPU温度固定thermal_zone0的身份假设：dijun设置ro.twrp.cpu_temp_type=cpu-crg，每5秒刷新按type精确匹配；缺失/重复/非法值返回无效，晚注册保持可重试。12项实际文件枚举/真实方法检查通过，旧实现同组9场景失败；28项状态/21项保存回归通过。installclean后30并发构建、719来源及封装/新二进制核对通过。同镜像profile回归另记。GUI尚无温度控件，震动未改/仍未解决，完整12组保持进行中。

修改DataManager温度逻辑后运行thermal_identity_test和status_readings_test，后者的属性夹具为空，专测通用旧路径；前者使用私有目录枚举、真实初始化/读取方法和可控时钟。0036维护在series，dijun不再声明TW_CUSTOM_CPU_TEMP_PATH。verify_unified_recovery核对prop.default中的类型属性和新recovery字节；旧verifier固定zone0的断言已被替换。旧otg-selection交付审计属于旧树/旧镜像，不能转移为当前总验收。

thermal-identity构建后收尾：同镜像9组/102阶段profile回放通过，719来源保持一致；当前交付审计见 `logs/thermal-identity-delivery.json`。GUI和FF库与otg-selection一致，温度界面/物理震动/完整目标仍未完成。

temperature-ui构建后收尾：同镜像9组/102阶段profile回放通过；723来源/维护补丁76+1+3文件重建一致、0待更新。当前交付审计 `logs/temperature-ui-delivery.json`；硬件温度/震动及设置现场仍未完成，完整12组保持进行中。

震动OS2/OS3真实系数续接：新增[60项原始解析器→系数查找→FF上传检查](logs/haptics-legacy-firmware-join.json)。四份OS2/OS3的normal/calib固件均用原始parser解析实际字节；独立packed算法表供给regmap读取。normal固件接同一上下文的原始upload callback/worker，撤掉cl_dsp_get_coeff替身，80ms/8ms/64请求解析到0x280701c/14/18并写20/125/64，与OS4一致。首/次/三项写失败均停止并传-5，缺首项名称原始查找传-14；头错误/固件写错误不产生完整系数，table读失败仍保留解析metadata但返回-5。parser-only也能建立软件系数且不写固件，不能据此推断DSP已加载。此举补齐旧版“模拟系数地址”边界，没有执行完整probe/参数加载、真实PM/input/workqueue/start/IRQ/DSP或电机；不把结果解释为震动恢复。生产temperature-ui候选与FF库未改，无需重编译，全部12组继续进行中。

震动OS2/OS3参数加载续接：新增[48项原始wavetable创建/固件解析/参数loader和parser接续](logs/haptics-legacy-parameters-join.json)，四版normal均请求5文件/34次参数raw写，calib请求4文件/28次写。逐文件记录原始parser返回，独立解码WMDR核对全部地址/长度/数据SHA。主文件缺失、头错误(-22)、首写错误(-5)及SVC首写错误(-5)均警告后继续，loader最终仍返回0；首分配失败才返回-12。calib模式用原厂参数会有三条revision警告但接受对应区域，不能把警告当作全包拒绝。参数写仅被记录，未使DSP运行，亦未连通完整probe/config/start/IRQ；loader0不是参数完整或电机输出的证明。没有证据将该故障机制对应到用户当前OS4无震动，不改原厂模块或生产请求。temperature-ui镜像未改，全部12组保持进行中。

settings-retry交付收尾：新镜像内脚本回放9组/102次阶段调用通过；724来源及维护补丁76+1+3文件重建一致、0待更新。已有控件反馈21项通过，FF库与temperature-ui一致。交付审计见logs/settings-retry-delivery.json；设置现场、物理震动及完整12组仍未完成。

MTP日期复核入口：`python3 scripts/audit_mtp_datetime_delivery.py`。原日期套件baseline显式跳过null（旧sscanf可崩溃），因此79对80项，不能描述为完全同矩阵；旧48失败为偏移20、非法输入27、本地DST空档1。新对象套件46项包含原42项+4日期落盘；历史对象报告与旧测试指纹仍为历史证据，当前使用mtp-datetime-objects。后续需单独处理epoch0哨兵及输出日期，不用本次parser通过替代。

MTP日期交付收尾：同镜像9组/102次阶段回放通过，725来源及76+1+3维护文件重建一致、0待更新；新镜像仅MTP库字节改变，GUI/FF库与settings-retry一致。当前审计logs/mtp-datetime-delivery.json。物理震动未解决，设置现场原因未确认，全部12组保持进行中。

诊断矩阵复现：python3 tools/haptics-diagnostic/build.py；python3 tests/haptics_diagnostic_test.py；python3 tests/haptics_diagnostic_arm64_test.py；python3 scripts/audit_haptics_diagnostic_matrix.py。运行会更新独立工具证据，主机与QEMU边界分别保留。全量审计诊断分支同步47/18，未声称其他历史来源分支在当前树通过。


请求诊断候选交付收尾：同镜像六版本双槽回放9组/102次阶段调用通过，726份构建来源保持一致，维护文件重建76+1+3且0待更新。14项日志与ABI、24项路由、4项后台FF、16项owner检查通过；交付审计入口`python3 scripts/audit_haptics_request_trace_delivery.py`，结果`logs/haptics-request-trace-delivery.json`。这是诊断候选，未确认触摸、现场设置保存或物理震动恢复，完整12组继续进行中。


2026-11-12 设置完整保存链路续查：新增tests/settings_joined_test.py/.cpp，在私有chroot保留真实/mnt/vendor/persist/TWRP路径，执行真实LVGL文字点击/公共行/取消guard/general回调→twrp_settings_store→DataManager Get/Set/Flush/Save→分区lookup/mount入口→InfoManager文件保存与重新加载。checkbox/switch各11场景，共22项通过；只换回HEAD旧partitionmanager方法同22项均失败。已有挂载/保存时挂载、拒绝挂载、ENOSPC、短写、只读、rename失败、目录fsync失败、BackingFile未初始化、常量键拒绝、其他字段超长均覆盖，并在故障解除后再次点击验证重试。目录fsync失败会出现磁盘新值已发布但UI/内存回退，不声称磁盘回滚。底层Mount/IsMounted、属性/元数据、页面导航/电机为显式替身，不是完整Recovery或现场persist；不推导用户设置已恢复。无生产修改或新构建，当前610f4acc诊断候选不变，震动/设置现场和完整12组继续进行中。复现python3 tests/settings_joined_test.py；审核python3 scripts/audit_settings_joined.py，范围详见docs/SETTINGS-ADAPTATION.md。

0041维护注意：createSendObjectFile是IMtpDatabase新增的必需接口，当前唯一实现TwrpMtpDatabase转交所属storage；临时文件登记与inotify处理共享tree_mutex_。不得仅修改server为mkstemp而绕过登记，否则observer可能发布半成品。目录列举和overflow重建也必须保留精确路径过滤。


MTP原子上传交付收尾：同镜像六版本双槽9组/102次阶段调用通过，727来源保持一致、维护文件76+1+3重建且0待更新；与610f4acc候选仅MTP库字节改变。当前审计logs/mtp-atomic-delivery.json。进程退出临时残留、目标断电/USB和完整调用链仍未完成，震动与现场设置尚未解决，完整12组继续进行中。


时区回退交付收尾：同镜像六版本双槽9组/102次阶段调用通过；731来源、维护文件79+1+3重建一致且0待更新。当前审计logs/timezone-retry-delivery.json。MTP与FF库字节保持上一候选一致，物理无震动、现场设置原因及完整12组仍未完成。


FF查询中断交付收尾：同镜像六版本双槽9组/102次阶段调用通过，732来源、维护文件79+1+3重建一致且0待更新；与f31bbe13候选只有FF库字节改变。28路由/6后台FF/14日志ABI及旧查询2失败对照完成，当前审计logs/haptics-probe-delivery.json。没有实机查询中断或电机恢复证据，物理无震动、现场设置及完整12组仍未完成。
