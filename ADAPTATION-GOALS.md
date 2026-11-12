# 小米 15S Pro（dijun）TWRP 多版本适配目标与离线验收规范

2026-11-12 安全服务实际namespace检查：在原始ARM64 linker构造函数前直接读取默认namespace字段，六profile各三个服务确认环境私有库优先、默认bootstrap/system搜索路径和不隔离配置。每profile删除配置及加入存在的标记目录各一项，实际搜索路径按预期变化；共42项通过，默认重定位30项回归通过。成员偏移从同执行字节linker的DWARF提取，库/服务原始CAS绑定；bootstrap插入和不存在路径忽略均保留原始语义，不改生产。见docs/PROFILE-SERVICE-NAMESPACE.md与logs/profile-service-namespace-audit.json。仍不证明真实init/mount namespace/APEX/属性区/proc、服务初始化或密钥/合成加密卷完成；完整12组继续进行中。生产mtp-directory镜像215914df…/765来源未变，本轮无构建，OS4震动正常确认保持，源码文档同步GitHub，编译文件不上传。

2026-11-12 安全服务本体ARM64重定位：六profile的原厂tee-supplicant/KeyMint/Gatekeeper共18个加载执行，通过当前镜像原始linker在call_pre_init_constructors调用前断点停止，核对PC、g_is_ldd=0及r_debug实际加载对象/来源。每profile额外缺库与等长缺符号私有副本对照各一项，共30项通过；正向服务与生产ELF均未修改。使用镜像ld.config及init绝对库路径，chroot无真实proc/属性区，仍不宣称精确init/APEX/namespace、服务构造函数/main/Binder/TEE/密钥操作或合成加密卷完成。详见docs/PROFILE-SERVICE-RELOCATION.md与logs/profile-service-relocation-audit.json。生产镜像仍为mtp-directory（215914df…）/765来源，本轮无生产修改或构建；完整12组继续进行中，OS4震动调用正常确认保留。测试审计文档按约定同步GitHub，编译文件不上传。

2026-11-12 MTP目录上传修正：补丁0059在SendObjectInfo创建/接纳目录后，通过目录fd应用有效修改时间（含epoch0、负秒和时区偏移），刷新数据库后结束，不再保留待SendObject状态；open/futimens/close失败返回错误，保留已有目录和内容以供重试。对象链路110项（新增16项）通过，旧实现同组16项有14失败，move/copy48项回归通过。installclean及make -j$(nproc)30并发构建recovery-dijun-unified-mtp-directory.img，SHA256 215914df1f8768bf00272f5c10c03b90fa8e624e9b1337fa6801a0ef3e5155b0，765来源/六profile封装通过。定向交付见logs/mtp-directory-delivery.json；实际USB/Windows、跨重启临时文件归属回收、子文件上传结束后的父目录日期恢复与断电仍未完成。NV/OTG/侧载修正继承，OS4震动及设置正常确认保留，完整12组继续进行中；源码文档同步GitHub，编译文件不上传。

2026-11-12 ARM64安装链证据：新增真正AArch64动态ELF无害updater，在原始主机ZIP安装链经签名/摘要、选择/提取、fork、协议管道和wait执行20场景通过；当前镜像linker/libc及固定QEMU在明确execve边界接入，构造函数/main参数、进度、缺库/缺符号拒绝、信号/退出状态与失败前写入均有核对。原主机36项回归通过，定向审计见logs/zip-arm64-chain-audit.json，范围见docs/ZIP-ARM64-EXECUTION.md。生产源码和764项镜像来源未变，沿用recovery-dijun-unified-sideload-reboot.img（022af2fc…），本轮无新构建。不是完整ARM64 Recovery、原厂OTA/update_engine、实际USB/FUSE或GUI验收，完整12组仍进行中。NV普通挂载隐藏/拒绝和OTG发现修正保留；设置与OS4震动用户正常确认保留。源码/文档/测试按约定同步GitHub，编译文件不上传。

GitHub同步检查点：0058源码、补丁、测试与文档已推送提交`6404774b290a8a6a0046400b386a590c9ca21f53`，核对远端main一致，公开CI通过（run 43223343428）。公开的是审计脚本与`docs/CURRENT-VALIDATION.json`摘要；完整本地`logs/`报告和编译镜像不上传。本条进度记录随后另批同步，不将检查点提交号冒称始终为最新HEAD。

2026-11-12 sideload重启交接：补丁0058将minadbd成功ACK且USB恢复成功后的system/bootloader/fastboot/recovery请求交给GUI统一退出/重启，等待启动流程、后台命令和侧载worker结束；ORS收到重启即停止脚本。修复完成状态先发布、running标志后清除导致析构可能取消待交接请求的竞态：状态发布与取消检查共用mutex。最终19场景通过，修复前同组15失败；生命周期33/实际ZIP侧载链27回归通过。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-sideload-reboot.img`，SHA256 `022af2fccb1040b7537b989c9c25d6c57ba844a27f11fae652d1f73bd93a7d2a`，764来源/六配置封装通过；同镜像脚本结果与交付审计见logs/sideload-reboot-delivery.json。Rescue/BCB未实现，真实minadbd/USB/FUSE、完整ORS和实机重启未验收。继承0054 NV普通挂载隐藏/双向拒绝、0048 OTG发现修正；设置和OS4震动用户确认保留。源码文档按每批次同步公开GitHub，镜像不上传；完整12组保持进行中。

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


2026-11-12 模块状态参考证据复核：七项固定上游源码顺序、三种原始状态输出函数执行、六份原厂内核接口字符串核对与当前同镜像4/24、旧脚本14失败报告关联完成，见`logs/module-state-reference-current.json`。保留旧review，使用新复核入口而不是直接刷新旧摘要。总审计已越过该历史阻断，下一处为旧settings持久化报告绑定的data.cpp变化；这是来源漂移，不撤回用户对9a1b057d镜像设置正常的确认。索引新鲜度124匹配/95漂移/20无充分绑定、总审计仍未全过，未做生产修改/构建；真实震动及其余完整目标继续未完成。

2026-11-12 NV配置原厂来源核对完成：六份样本各自的recovery/vendor_boot镜像先按OTA manifest尺寸/SHA256验证，再重读ramdisk并比对提取文件。12份fstab的六个NV/protection条目全部与维护树五列字段一致，见`logs/stock-nv-fstab-audit.json`。据此排除“这些声明没有本机原厂来源”的疑点；不等于物理存在或普通GUI应暴露，不解决重复内部存储标签。未改生产/镜像，定向审计纳入12项来源核对，震动与其余原目标继续未完成。

2026-11-12 挂载列表链路检查：五场景执行原始mount/storage分支→快照→backend→实际LVGL builder，正常夹具20挂载行/3存储行、30次刷新不累加；原始emmc排除、NVData/NVCFG不进入storage，移除/恢复有对应变化。输入名称显式重复时页面保留重复，尚不能将此夹具当作现场根因。`logs/mount-list-chain.json`与定向来源审计`logs/current-offline-paths-audit.json`绑定当前9a1b057d/738来源；同时纳入既有设置入口45项和修复工具链七项。未改生产、未重编译，不把离线检查当作震动或现场挂载问题已恢复；全部原未完成项保留，设置正常的最新用户反馈不撤回。

2026-11-12 用户最新确认：使用`recovery-dijun-unified-backup-manifest.img`（9a1b057d…）时设置功能已经正常；结束对此前设置失效的持续推测和重复采集要求。此为用户现场观察，不扩展为全部设置逐项验收。新反馈为挂载页出现三十多个“内部存储”及NV选项：已从同镜像提取fstab核对32行、22个不同挂载点、10组ext4/EROFS候选、19个非原始分区声明（含OTG模板）；不能当成32个实际存储。NVData/NVCFG的ext4条目按当前挂载列表策略会出现，NVRAM/emmc不应进入mount列表；尚无当前页面截图或运行列表，未确定重复标签原因、不改生产过滤或镜像。见`docs/MOUNT-LIST-EXPLANATION.md`与`logs/shipped-mount-inventory.json`。震动及其余原目标保持未完成。

2026-11-12 设置首页补查：新增真实LVGL设置入口检查45项，通过标题/说明/箭头/空白点击及移出取消，覆盖PUSH动画结束后的page_host与滚动后段入口，见`logs/settings-navigation.json`及`docs/SETTINGS-ADAPTATION.md`。导航终点、字体和硬件是边界，不能证明现场输入、目的页或保存。没有复现公共入口故障，也未确定保存失败是本次根因；不生成无依据的修复镜像。设置故障、触摸、震动与完整12组继续未完成。

2026-11-12 当前震动与交付证据核对：重新执行生产路由28项、owner16项、owner→FF六项、LVGL反馈21项、操作反馈64项、六版驱动120项与请求trace/ABI14项，通过各自的主机边界检查；8种时长effect字节与保留的旧trace报告一致。没有形成物理无震动的根因或生产修正。五项当前镜像入口此前误指向7f4c4293的证据，现已逐项核对来源并改为已有9a1b057d镜像的profile9/module4/policy12+53/init6报告；旧绑定保留在logs/current-haptics-evidence-index-before.json，13项定向绑定见logs/current-haptics-evidence-bindings.json。全量审计仍失败于历史module-state-review.json绑定的tests/module_state_test.py摘要，见logs/current-haptics-unified-audit.log，未改旧摘要或放宽门槛。设置现场仍缺操作前后回执；震动、自动触摸及全部12组继续未完成。本轮无生产修改、新构建或设备操作。

2026-11-12 设置故障继续核对：raw-off 后 event3 的215条历史事件包含7组按下/抬起和变化坐标，证明该次启动的Linux input层有坐标；该轨迹集中在屏幕下部，不能证明设置控件被点中，也不能证明GUI保存。当前源码重新运行LVGL设置行20项、设置持久化完整链路22项及dijun坐标映射6组均通过，结果为`logs/settings-current-recheck-row.json`、`logs/settings-current-recheck-joined.json`、`logs/dijun-touch-regression.json`。旧的joined审计因`partitionmanager.cpp`哈希从报告记录的`f3d169...`变为当前`d8e43b...`而拒绝复用；因此旧报告不能作为当前源码来源审计。没有本次设置点击的Recovery回调或persist回执，现场设置问题仍未定位；没有设备操作或新镜像，全部12组继续未完成。

2026-11-12 整份备份中断一致性：维护补丁0047在新备份写入前同步INCOMPLETE标记，结束后同步数据并原子发布文件清单；SetRestoreFiles与RunRestore均在枚举/写分区前校验。17项真实私有文件清单检查、备份管理器55项、恢复管理器56项通过，未完成/大小不符清单确认没有触及目标写入；保留旧备份无清单兼容，不将其伪称有完整性证明。installclean及make -j$(nproc)（30并发）构建，738份来源/六配置封装核对通过；同镜像profile9、module4、policy12+53、init6检查通过。新候选SHA256 `9a1b057d001821b0d9a908c003c3810f5295e6fa500e1716f59ae50364126123`。进程退出不是断电/真实文件系统试验，manifest不是内容摘要；物理震动仍未修复且本轮生产代码不涉及震动，未执行实机测试；设置/触摸现场、整份数据物理持久性与12组总体验收仍未完成。详见[备份完整清单](docs/BACKUP-SESSION-ADAPTATION.md)和[震动状态](docs/HAPTICS-ADAPTATION.md)。

2026-11-12 用户再次反馈设置项目无法修改：优先检查设置，保留未完成的备份manifest工作区改动。本次完整设置链路22项离线回归通过（`logs/settings-latest-report-joined.json`），不能代替现场结果；已有内核日志无本次操作保存回执。已统一scripts与工具包中的采集脚本，字节/ZIP/shell语法核对通过，无设备操作、无新镜像。下一步是当前Recovery一次“交换导航按钮”操作前后记录，以区分点击无响应与保存失败回退；不重置原设置。设置根因未定，全部12组仍未完成。详见[设置续查](docs/SETTINGS-ADAPTATION.md)。

2026-11-12 备份摘要发布修正：维护补丁0046改为同目录临时写入、文件同步/关闭、rename及目录同步，避免失败或中断截断正式摘要。真实hash/文件与BackupPartition调用54项通过，旧实现同组44项失败；恢复54项/备份会话55项回归通过。installclean后make -j$(nproc)30并发构建`recovery-dijun-unified-digest-atomic.img`，SHA256 `7f4c42935ff34c01ce85cec049c94b60ebd072400255cf299aedaca10dacafff`，736份生产来源/封装通过；同镜像profile9组/102调用、模块4组/24调用、策略12+53/init5通过。目录同步失败时完整新摘要可能已可见，分卷逐文件提交不等于整份备份事务。详见[摘要发布范围](docs/DIGEST-PUBLICATION.md)。当前224项绑定清单126匹配/78漂移/20无充分绑定，全量审计仍未通过；震动、自动触摸、设置现场与原12组任务仍未完成。

2026-11-12 交付证据刷新：当前仍为`recovery-dijun-unified-mtp-reset.img`，SHA256 `046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27`，735份生产来源一致。模块夹具区分模块/触摸报告等待，将可选震动顺序约束改为触摸已尝试；同镜像模块4组/24调用、profile9组/102调用、策略12+53项和init5份通过，旧模块脚本同夹具仍14项失败。主要当前索引已更新为实际重跑报告；222项索引绑定清单124匹配/78漂移/20无充分绑定，总审计仍在历史review摘要处失败，这不是功能通过率。详见[当前交付与证据状态](docs/DELIVERY-EVIDENCE-STATUS.md)。生产代码与镜像未改，震动、设置现场、自动触摸及原12组目标仍未完成。下文早期“当前”及下一步属于各历史检查点。

2026-11-12 codec/PCM与FF原始接续：[两份OS4共12场景](logs/haptics-pcm-ff-join-review.json)执行codec probe、Mode1/Slot1 put、hw_params/sysclk与参数/时钟/RX widget，再接生产80ms SINE/IRQ。原始回调生成slots2/3、24bit word/32bit slot及单声道1.536MHz/双声道3.072MHz夹具缓存；不代表真实backend协商。四次参数寄存器更新全失败仍返回0；RX首/末写失败返回-5，后续FF仍发相同参数和命令。指针/分配/字符串/格式/寄存器/PM/ACK/调度/IRQ为显式边界，无真实ALSA/DSP/电机。详见[范围](docs/HAPTICS-PCM-FF-STATE.md)。生产046ab9e3/735来源保持，未改增益、校准或路由；共享软件路径仍不能选定物理原因，后续重点每设备校准/寄存器读回与输出通路，已有采集不重复索取。设置现场、自动触摸、震动及完整12组未完成。

2026-11-12 ASP与FF同上下文接续：[两份OS4共14场景](logs/haptics-asp-ff-join-review.json)从原厂A1 probe执行clk_en/asp_start/时钟切换，再提交生产80ms SINE和显式提供的开始/完成IRQ。未开ASP、已开及开启失败均请求相同五次FF写入与0x01800081命令；没有发现纯软件ASP前置门控。ASP标志在尝试前已置1且失败不回退，完成时重启ASP失败可留下state1/count0/completion已饱和；13jiffy STOP超时也可能最终回调返回0。codec/BCLK3.072MHz/PLL0/寄存器/PM/锁/ACK/队列/IRQ仍为显式边界，不证明实际时钟或电机。详见[范围](docs/HAPTICS-ASP-FF-STATE.md)。生产未变，046ab9e3镜像/735来源保持；下一步ASP参数/PCM寄存器与每设备校准读回，震动、设置现场、自动触摸及完整12组保持未完成。

2026-11-12 音频socket对端接续：[两份OS4共34场景](logs/haptics-audio-peer-review.json)执行原始socket handler→ResourceManager→ModulePrimary→updateA2HMode及串行原子release，使用前轮捕获的72字节启动消息。编号42通知震动流活动并协调已有流A2H；未知编号/短读/EOF/read=-1也请求相同0100回复，不能当成硬件就绪。合成许可流不活动时请求Haptics Source2，app拒绝时0，活动时不请求设置。socket/stream/usecase/app策略/setA2HParameter仍为显式边界，无真实ALSA/DSP/电机。详见[范围](docs/HAPTICS-AUDIO-SOCKET-PEER.md)。没有生产修改或新构建，046ab9e3镜像/735来源保持；下一步ASP与独立FF状态关联，物理震动、设置现场、自动触摸及完整12组未完成。

2026-11-12 原厂服务线程/XML接续：[14场景](logs/haptics-service-tail-review.json)执行原始hash初始化、动态效果线程构造、真实XML消费者及首次threadLoop到等待。正常worker会经音频socket请求、设置XR_TDM7_RX及Source=PCM/ASP/TDM路由、请求PCM0/9；此前仅构造/on无mixer调用不足以排除后台音频初始化依赖。XML缺失/无long项保留默认35，正常31，合成42被原始消费后进入普通on；数组写失败仍开PCM、socket超时重试后仍继续，不能把PCM请求视为路由就绪。libxml/Thread/ALSA/socket为明确边界，原厂tinyalsa叶函数转换实际执行，无真实DSP/电机。详见[范围](docs/HAPTICS-SERVICE-THREAD-XML.md)。未改生产或构建，046ab9e3/735来源保持；下一步核对ASP/FF状态关系及音频socket对端，完整12组与震动/设置/自动触摸未解决。

2026-11-12 原厂实际 PCM 初始化接续：[26 场景](logs/haptics-pcm-init-review.json)执行两份 OS4 的 selector、PCM/波形数据构造及 AAC init 本体。48kHz/XR_TDM7_RX、频率120/140边界与越界回退、库/符号缺失、分配/信号量/线程错误均核对；初始化范围无额外 mixer/供电控制写入。AAC 返回-2/-1/11仍不阻止外层继续；部分构造上下文的普通 on 仍发 gain100/CUSTOM31/play，不能据此认定物理可用。跳过的替代设备/map、校准恢复、XML long-id/恢复标志、libc/math/loader/线程边界已列明，AWA本体和工作线程未执行，不称完整启动。详见[范围](docs/HAPTICS-PCM-INITIALIZATION.md)。当前046ab9e3镜像与735生产来源保持，未改生产或构建；震动、设置现场及完整12组继续进行中。

MTP Reset交付收尾：同一046ab9e3镜像的profile脚本回放9组/102次阶段调用通过；735来源与完整维护补丁80+1+3文件核对一致，0待同步。交付核对见logs/mtp-reset-delivery.json；这属于离线软件证据，震动/设置及完整12组仍未完成。

2026-11-12 MTP Reset会话修正：补丁0045把合法class Reset从普通Cancel区分，服务器消费独立信号后关闭旧session/通知、撤销待上传/编辑资源，保留存储，要求重新OpenSession后继续；信号待消费时状态为DeviceBusy，失败/替换Setup不复位。控制80/服务器78、移动复制48/native+compat事件62及传输往返通过，旧代码控制3项/Reset服务器9项失败。新增Reset+断线检查曾抓到首版吞ESHUTDOWN，已修正并重新installclean/30并发构建，首版不交付。当前recovery-dijun-unified-mtp-reset.img，SHA256 046ab9e356e5301661daa4ff7dd6a29504cee7706ee32da0353d988f7e6a4e27，735来源/封装核对通过；同镜像profile回放另记。真实ep0/bulk取消/残余包/旧事件队列与UDC未完成，不称为完整USB复位。震动和设置仍未解决，完整12组继续进行中。详见[范围](docs/MTP-RESET-SESSION.md)。

2026-11-12 原厂震动服务初始化续查：[两份OS4共30项](logs/haptics-service-init-review.json)执行constructor输入发现前缀及单独FF后端构造，绑定原厂build.prop。识别cs40l26后先请求校准恢复，再查询能力；Cirrus/audio分别由属性控制，mixer_open失败仍保留FF fd与Cirrus标志。后端只读取custom_wave_id，文件/字段缺失保留-1；这些范围未见额外功放使能写入。校准恢复本体为已标明的调用边界，外层0x13084之后的XML/线程/派发未执行，后端sysfs全局路径及目录/ioctl/属性/mixer/libc++为夹具，不是完整服务启动或电机证据。未发现支持新增控制写入的依据，生产与da614695镜像不变；设置现场与震动未解决，完整12组继续进行中。

2026-11-12 旧版完整配置/input/自检接续：[四版本44项](logs/haptics-legacy-config-input-join.json)从同一原厂probe推进到DSP配置、boost/brownout、runtime PM/logger/ASP、27个IRQ子项、input/FF回调与内置upload/play/erase。模拟ACK路径probe=0；start mailbox注入-5后probe仍=0、upload/erase状态仍0，说明原厂probe成功和自检返回不足以证明播放命令成功。配置/IRQ/FF/MFD错误分支按原始返回退出，CALL_RAM_INIT后失败仍可fw_loaded=1；MFD失败路径原始remove请求注销input后注册标志仍1，标志不代表存活设备。正常路径68次raw写入、25次wseq bulk、实际自测effect100ms/SINE8ms/magnitude45及三worker顺序均核对；本场景未调用completion/wait，不注入完成事件。身份B2、regmap/全FF序列/ACK/电源与内核IRQ/input/PM/串行队列仍为夹具，无DSP或电机。前16/20项报告中remove本体“未执行/被替换”标注已撤回，原始remove实际执行，只有其内核服务是夹具；已重跑并修正证据。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)。生产与da614695镜像不变，震动/设置/自动触摸及完整12组未完成；剩余为实际寄存器/校准依赖、IRQ消息及内核并发/完成链等硬件边界。

2026-11-12 OS2/OS3 probe→固件/参数接续：[20项原始执行](logs/haptics-legacy-probe-upload-join.json)把四份原厂probe的DT/PLL/ID、DSP分配、正常WMFW解析、五份WMDR加载接入同一上下文，全部参数路径68次raw写入；随后明确在MEM_RDY更新注入-5，未完成DSP配置或注册input。独立文件清单核对每次写入地址/长度/摘要；主bin缺失仍加载其余四份并进入配置（63次写入），不能把进入配置当作参数完整。原厂pre-config接受夹具状态1或2，持续3时10次轮询后-22且未解析固件；该早退绕过release_firmware，仅为原始函数观察，原厂remove本体已执行，其内核teardown服务为夹具。芯片身份0x40a270/B2、寄存器/算法表、ACK、电源与内核均有明确模拟边界；不代表现场OS4的A1芯片或物理输出。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)。生产与当前da614695镜像未变，下一边界为旧版DSP完整配置、input/start/IRQ/自检接续；震动、触摸、设置及完整12组仍未解决。

2026-11-12 震动CUSTOM回调连接：[两份OS4共12项](logs/haptics-custom-callback-review.json)把原始服务/XML的CUSTOM31 effect接入同一A1 probe后的原始upload callback→分配/长度/地址检查→有界copy夹具→真实worker→start。正常请求mailbox0x0100001f；部分copy/地址非法-14、分配失败-12、波形43越界-22，错误不播放且临时effect清零/缓冲区释放；部分复制尾部清零字节也核对。补齐此前直接填worker跳过callback的边界，但没有真实usercopy/页表、input core、DSP、计时线程或马达。未发现据此改用CUSTOM的具体生产缺陷，物理无震动保持未解决。详见[范围](docs/HAPTICS-ADAPTATION.md)，当前da614695候选不变；完整12组继续进行中。

2026-11-12 当前交付更新：`recovery-dijun-unified-mtp-transaction.img`，SHA256 `da614695843c1c8f7dd8e1eabc747a65d4e5d755680ba1a0c1dbaeec08ac79b8`。维护补丁0044让FunctionFS按服务器当前活动事务ID处理Cancel，空闲/已结束/其他ID正常消费控制报文，不再中断新传输；scope guard覆盖数据/响应/错误退出后清理。73项控制检查通过，旧实现同组5项失败；68项真实server检查核对生命周期，48项移动/复制、62项事件和native/compat传输回归通过。installclean后make -j$(nproc)30并发构建，734来源与封装核对通过。同镜像profile回放及交付审计见logs/mtp-transaction-delivery.json。Reset/DeviceBusy/bulk取消/compat ep0与真实USB仍待完成；没有修复物理震动或确认现场设置可用。详见[范围](docs/MTP-TRANSACTION-CANCEL.md)。当前定向交付不替代被历史来源漂移阻断的全量审计，完整12组继续进行中。

2026-11-12 设置故障再次报告：用户表示似乎所有设置项目都不能修改，本项继续按现场故障处理，未验收。当前源码的常规开关在 SetValue/Flush 失败时恢复旧状态，语言/主题也依赖公共保存链；这只是共同故障候选，不能据此认定 persist 损坏。复核用户 raw-off 附件只确认 Linux input 事件，未包含设置点击或保存回执；旧 bootfix 日志同时有 persist 查找失败与保存成功，不能代替本次证据。下一步依据一次“交换导航按钮”操作的视觉现象、操作后完整 recovery.log、挂载/容量和运行二进制摘要定位输入命中或保存失败。现有 tools/settings-state-collector.zip 可保存前后状态；未连接手机、修改设置或生成新镜像。

2026-11-12 OS2/OS3 原始震动 probe 前缀推进：四个 OS2/OS3 原厂模块共 16 项执行，原始 probe 使用合并 DT 属性运行到 pinctrl/PLL/芯片 ID 错误分支；另在 PLL helper 原始执行、synthetic 芯片 ID/revision、明确 regmap 返回成功的条件下，执行到真实 `request_firmware("cs40l26.wmfw")`，再注入 `-ENOENT` 并核对 teardown。旧版硬件 ID 与寄存器返回不是实测；没有成功 firmware 上传、input/start/IRQ/selftest、DSP 或电机验证。见[结果](logs/haptics-legacy-probe-prefix.json)和[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)。生产未改、无新镜像，震动和完整12组仍未完成。

2026-11-12 设置现场新证据边界：用户贴出的 getevent 回显显示 raw-off 后 event3 有触点、变化坐标及抬起；`imgs/built/1/touch-after-raw-off.txt` 是 UTF-16LE dmesg，不含该回显。getevent 只证明 Linux input 层有事件，不证明 Recovery GUI 命中，也没有 Flush/persist 回执。设置“完全无视觉变化”与“先变后回退”分别指向输入消费和保存链路的不同边界；本次根因仍未判定，不清理现有设置文件。详见[设置记录](docs/SETTINGS-ADAPTATION.md)。

2026-11-12 震动现场证据重审：现有 `imgs/built/1/touch-after-raw-off.txt` 内 43 次播放都能配对到 SINE 上传成功、start worker 完成和 `TRIGGER_CP`/`COMPLETE_MBOX`；6 次记录 VBST brownout，36 次既无 brownout 也无完成前 stop，另 1 次在完成前 stop。43 次 stop/erase 均在 10.491 ms 内记录完成。它证明驱动/邮箱执行，不证明用户请求身份、电气输出或可感知位移；brownout 不能解释全部周期。见[逐周期结果](logs/haptics-playback-field-observation.json)、[stop/erase 结果](logs/haptics-erase-field-observation.json)与[震动记录](docs/HAPTICS-ADAPTATION.md)。OS4 原厂 probe、配置、IRQ/input 与自带 FF 自检已有离线接续；OS2/OS3 尚缺完整 probe 到 input 的同上下文接续，设备状态采集已有工具但尚无结果。生产路径不因这些间接证据改波形、增益、路由或校准，物理震动仍未解决，12 组未完成。

2026-11-12 震动日志关联纠正：5条`0x13020`首写NACK在时间上位于stop请求之后，随后出现PM state 2完成、stop done、erase_ret0及下一组upload/mailbox日志；无线程号或事务ID，不能把后续日志绑定为该失败写入的重试成功。撤回此前“没有中断下一条、不能作为无震动根因”的结论。[32项原始ARM64执行](logs/haptics-mailbox-error-review.json)确认mailbox写/读各20次失败返回-62、busy20次返回-110；原始stop worker在PM入口失败时直接退出，但mailbox失败仍可打印done。因此done不等于命令成功，NACK与无震动的因果关系未定。[现场解析结果](logs/haptics-playback-field-observation.json)改为只记录顺序窗口，保留state 2完成这一独立观察；详见[范围](docs/HAPTICS-ADAPTATION.md)。regmap/PM/恢复helper等仍为显式夹具，无DSP或电机证据。未改生产代码、设备树、校准或镜像，完整12组继续进行中。

2026-11-12 六版本 probe 调用图：新增[静态重定位对照](logs/haptics-probe-callgraph.json)与脚本，交付一致性复核 [PASS](logs/haptics-probe-callgraph-audit.json)。OS2/OS3 四份模块的 probe 直接目标序列一致；OS4 两份彼此一致但与旧版不同。旧版调用目标含 regmap read/write 与 probe 内 upload/play/erase，自测调用未出现在 OS4 probe；OS4 有 part-number resolver 及不同 workqueue/fwnode API。只核对 ELF relocation/symbol，不执行分支或硬件。该差异是继续做 OS2/OS3 原始 probe 接续的依据，不是 OS4/旧版震动可用性的判断；详见[固件模拟范围](docs/HAPTICS-FIRMWARE-EMULATION.md)。

震动能力查询中断修正：补丁0043让已有FF描述符的只读能力查询遇EINTR/EAGAIN时保留描述符与缓存能力，等待下一轮查询；避免关闭触发input core清理效果，不做无限重试。ENODEV/EBADF仍关闭并重新探测。28项路由/6项后台FF通过，旧代码同组EINTR/EAGAIN两项失败；14项日志ABI通过，8种时长effect字节不变。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-haptics-probe.img，SHA256 `e64e796370ad7983d27692ce22827ab03f72999e68881a1b4fe507247ec48f73`，732来源/封装核对通过；同镜像回放另记。现场没有能力查询EINTR证据，不能认定持续无震动根因或物理修复；设置现场及完整12组继续进行中。

时区保存失败回退：补丁0042在页面提交前保留五项旧值，部分写入/生成时区/flush失败时恢复选项和精确旧tw_time_zone，刷新旧环境，保留待选项供重试；检查时区/偏移索引边界。backend生成时区传回读写错误，回退不从GUI选项重建自定义时区。17项真实LVGL回调+实际adapter/libc检查通过，旧回调同组11项失败；保存链22/点击20/语言主题9/震动路由24/owner16回归通过。存储/属性/页面路由为夹具，目录fsync失败后的磁盘发布不构成回滚。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-timezone-retry.img，SHA256 `f31bbe13f856d25c0080b26cac041366bb91c5f61b95f88f9f5136df83a47023`，731来源与封装核对通过，同镜像profile回归另记。不能以此解释所有设置失效，物理震动与完整12组仍未完成。

MTP上传原子发布：补丁0041以同目录唯一临时文件接收，接收/长度校验/fsync/close均成功才rename，失败只删除临时文件，保留旧目标。数据库在同一observer锁下创建并登记精确临时路径，inotify、ReadDir与overflow reconciliation均不发布传输中的临时文件。68项真实server/database/storage主机检查（含22项新原子发布场景）与48项move/copy回归通过；旧实现5项覆盖对照均失败。目录fsync在rename之后失败只警告，完整新文件已提交，不能声称可恢复旧inode；模拟进程中途退出保留旧目标但留下临时文件，跨重启清理未完成。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-mtp-atomic-upload.img，SHA256 `7ca65801af3a62b4970cf1ad12d05a8af49dd8e870992b45e40ad6192a06a23a`，727来源与封装核对通过，同镜像profile回放结果另记。震动、现场设置及完整12组仍未完成。

震动生产请求诊断补齐：维护补丁0040在后台owner记录begin/end/expired、请求序号/时长/队龄/替换计数/耗时，在FF层记录实际type/waveform/period/magnitude和擦除/上传/播放/close的开始结束、实际返回值、独立保存的errno、单调时间与PID/TID。提交入口不执行日志I/O；周期能力probe正常不打日志。GUI与FF序号是不同空间，只能结合线程/时间定位，不能认定跨调用者严格关联。日志可能拖慢worker，不提供阻塞输出的实时保证；accepted仅系统调用边界，不等于电机。24项路由/4项后台FF/16项owner/14项日志ABI核对通过，8种时长effect字节与旧捕获一致。新增擦除失败和短写模拟；短写不再误报旧errno。installclean后make -j$(nproc)30并发新候选recovery-dijun-unified-haptics-request-trace.img，SHA256 `610f4acc2534cbd3fdd95f6733257efa52329435569df5230c4ea1a9c3326a8d`，726来源与封装/新二进制核对通过；同镜像profile另记。未改波形、幅度、增益、校准或触发实机操作，震动与完整12组仍未完成。


震动诊断因素分离：独立工具新增--sine-gain100与--custom-existing-gain，与原--play/--stock-long组成波形SINE/CUSTOM×是否写gain100的四种请求。两个SINE的effect字节完全相同；两个CUSTOM除运行时指针外与原厂HAL捕获一致，数组{0,31}也核对。47项主机syscall替身和18项目标ARM64/QEMU启动/拒绝/普通文件失败检查通过；不等于真实播放。显式gain100在close后保留，“不写增益”不会恢复默认状态，必须记录执行顺序，不能把跨次请求视为独立初态；工具不自动播放四种模式。CUSTOM继续仅供已审核OS4，cross入口限1..1000ms，无任意波形/增益。重新构建独立工具并打包tools/haptics-diagnostic-os4.zip，未连接手机或修改生产镜像。当前MTP日期候选8c624d0e不变，物理震动、设置现场和完整12组仍未完成。


MTP上传日期修正：维护补丁0039按MTP格式校验年月日/时分秒、单个小数位、Z和±HHMM，显式偏移转UTC不依赖Recovery时区；保留无偏移的本地时区/DST行为，拒绝归一化后的非法日期和不存在的本地时间，失败不改变调用者输出。实际MtpUtils+独立Python日期oracle80项通过，旧实现79项中48失败（旧版空指针另未执行）；生产server/database/文件上传46项及移动复制48项通过，含4项新日期落盘检查。主机libc/USB替身非手机RTC/Windows枚举。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-mtp-datetime.img，SHA256 `8c624d0e1a4b9bbff1b99ce83dbcce2c3cdfc3013c2270d65c04e075a8a81ee3`，725来源及封装/新二进制核对通过；同镜像profile另记。没有修正震动、修改校准或改变FF；原子上传覆盖/输出日期格式化/完整元数据等仍待完成，全部12组保持进行中。


设置保存失败后重试修正：维护补丁0038让语言/主题在flush失败时恢复旧内存值，保留待选项；避免主题值先变而未重建、再次点击被同值判断阻断。真实回调/LVGL事件9项通过，旧实现同组4项失败；存储/路由/console为显式夹具，不是实际persist或完整GUI。设置整行20项、真实文件保存21项、嵌套路径31断言回归通过。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-settings-retry.img，SHA256 `e8adb7259265b4fa05a1057ba9141e09af805c7ff2240cb07a45bb009bbe2214`，724来源及封装/新二进制核对通过。同镜像profile回放结果另记。目录fsync失败可能已发布完整新文件，内存回退并不构成磁盘回滚；这一边界保持明确。尚无本次设置现场日志，不能解释全部设置不可修改；物理震动未解决，触摸P0和全部12组继续进行中。


温度GUI交付更新：维护补丁0037通过现有status backend/controller接入tw_cpu_temp，合法整数-273..1000°C独立于电量解析；缺失/非法/禁用时隐藏，后续读数恢复。状态栏按实际文本重新布局，窄屏优先时间/录屏/电量，空间不足隐藏温度；装饰不可点击。11组真实LVGL/provider/controller检查通过，含14种解析值、定时刷新、0/负温、晚到/禁用恢复、电量隐藏、Wi-Fi/录屏、四宽度与明暗主题；28项状态回归通过。已检查1440宽实际渲染图，host字体/settings/tick仍为夹具，未证明Android显示或物理温度。installclean后make -j$(nproc)30并发构建[新候选](imgs/built/recovery-dijun-unified-temperature-ui.img)，SHA256 `f2dea7dbf8ad58a9363f0906effa9ade627e7903bc45ee71e1b1fc1159994d84`，723来源及封装/新二进制核对通过。震动未改且仍未解决，设置现场采集未到，完整12组保持进行中。


最新交付更新：`recovery-dijun-unified-thermal-identity.img`，SHA256 `338a4bf6c4e4563a30e6d26eecfbf6ac0793d5158974753a107eb38674f455db`。0036修正CPU温度固定thermal_zone0的身份假设：dijun设置ro.twrp.cpu_temp_type=cpu-crg，每5秒刷新按type精确匹配；缺失/重复/非法值返回无效，晚注册保持可重试。12项实际文件枚举/真实方法检查通过，旧实现同组9场景失败；28项状态/21项保存回归通过。installclean后30并发构建、719来源及封装/新二进制核对通过。同镜像profile回归另记。GUI尚无温度控件，震动未改/仍未解决，完整12组保持进行中。

最新交付：`recovery-dijun-unified-otg-selection.img`，SHA256 `aaa4b25c1bd58a0b61508288a479d824f38701c38d2ed606530b39c503181ef7`，718来源/封装及installclean后30并发构建通过。0035修正存储选择容量失败/设备消失/设置提交失败时仍提交或留下新挂载的问题，15项真实选择+UpdateSize方法检查通过，旧实现同组12场景失败；底层设备和I/O仍为替身，详见[范围](docs/STORAGE-SELECTION-ADAPTATION.md)。设置20项交互/21项保存/31项路径回归通过，不能替代用户设置操作前后日志。USB发现、写入中拔除、现场设置和物理震动未验证，全部12组保持进行中。

震动固件发布核实：当前settings-row镜像真实脚本/CAS在六版本双槽12次回放中，624个模块插入边界均核对9份Cirrus文件与对应ODM原件一致；原厂firmware目录在cache后从私有夹具移除，RAM字节仍保留。OS4 vendor/ODM同名a2h有8个参数字、dbc有2个参数字不同，原厂ueventd与镜像均ODM优先；保留原厂参数。见[结果](logs/haptics-firmware-publication.json)及[范围](docs/HAPTICS-ADAPTATION.md)。insmod/内核加载/DSP/电机未执行，不能解释用户当时的物理无输出；生产未改，震动和完整12组仍未完成。

震动保护回调核实：新增[44项原始IRQ函数执行](logs/haptics-protection-irq-review.json)，确认VBST欠压/解除通知仅日志，不是软件增益恢复。四类boost/amp故障另读0x2034执行对应位清零/置位/清零，读写失败返回IRQ_NONE；regmap/IRQ/供电为边界，不能证明实际保护解除或当前根因。保持原厂保护、波形与增益，生产镜像未改；详见[范围](docs/HAPTICS-ADAPTATION.md)。实际无震动和全部目标继续未完成。

录屏多段时间轴推进：三份160×96/12.5秒样片各跨3个Cluster及0/5/10秒关键帧，15/30/60 FPS共1313帧编号/PTS经独立FFmpeg原生解码核对，30次跨边界跳转与线性解码一致。没有Cues，最后帧之后的跳转输出为空；不代表小时级/索引性能/目标codec/全分辨率或GUI播放完成。见[结果](logs/video-timeline.json)与[范围](docs/VIDEO-FRAMES-VALIDATION.md)。生产镜像未改，震动和全部12组继续进行中。

震动Source通路核实：两包原始ELF还原10条DAPM route/8个widget，Source0/1/2为Off/PCM/A2H，原厂服务0→1选择PCM。新增20项原始PCM事件执行覆盖A1/B2、SVC FLAGS恢复、寄存器/mailbox失败；DAPM调度/硬件仍为显式夹具，不能据此声称FF需要Source切换。未向Recovery盲写音频路由，生产镜像未改。见[结果](logs/haptics-dapm-route-review.json)与[范围](docs/HAPTICS-ADAPTATION.md)。实际无震动仍未解决，完整12组保持进行中。

录屏独立解码推进：[18份FFmpeg原生VP8解码与72次输入跳转](logs/video-ffmpeg.json)核对实际WebM单视频轨/尺寸/PTS/1500ms时长、彩条中心像素和跳转结果。拥塞恢复样片从0.5s读到PTS1.0s帧；1.2s后无新帧时正确为空。工具从Debian包解压、版本/包及213工具/库哈希保存，不安装或进入镜像。短文件单cluster/无cues结果不代表长文件索引、GUI播放、目标codec或手机性能；当前2773dec6镜像未改，震动和全部12组继续进行中。详见[范围](docs/VIDEO-FRAMES-VALIDATION.md)。

录屏保存新增确定修正：stop忽略fclose错误会导致screenrecord_saved误报成功。补丁0032传播关闭失败、保留更早错误；6项stdio/codec故障及同对象重录检查通过，修改前close场景失败。18项真实帧/时间轴/队列回归通过。installclean后make -j$(nproc)（30并发）构建新候选recovery-dijun-unified-recording-close.img，SHA256 `2773dec6298035e66dcb0b24deb78636207a6bbf24fab6f9490a5ad3151d83c7`，714来源/封装核对；同镜像profile回归9组/102次阶段调用通过。震动未解决，全部12组继续进行中；下文旧镜像均为历史检查点。见[范围](docs/VIDEO-FRAMES-VALIDATION.md)。

录屏拥塞验收推进：[18项真实编码/封装/解码](logs/video-frames.json)覆盖六种尺寸/FPS×顺序/队列排空/拥塞恢复。首帧编码门控后两帧入队、七帧丢弃，白色源缓冲改写不影响已复制彩条；恢复帧保留0/100/200/1000ms时间，总时长1500ms；stop排空生成三帧文件。ASan/UBSan通过。未验证手机吞吐量/目标ARM64/display shadow、I/O/codec错误或独立播放器；没有生产修改或新镜像，震动及12组完整目标继续进行中。详见[范围](docs/VIDEO-FRAMES-VALIDATION.md)。

震动SINE系数接续：[46项原始SINE/parser/get_reg执行](logs/haptics-sine-coefficients-review.json)替换此前虚拟系数地址边界，实际固件BUZZ2地址为duration0x280701c/freq0x2807014/level0x2807018。生产80ms/8ms/64转换为20/125/64；原始get_coeff按低16位匹配，调用者0x1f202与元数据0x4f202高位差异不阻断解析。频率/幅度边界及首次写失败后同ID重试覆盖。寄存器仍为显式夹具、DSP/电机未执行，无生产修改或新镜像，震动与全部12组目标继续进行中。详见[范围](docs/HAPTICS-ADAPTATION.md)。

震动原厂路由复核：新增[20项原始服务执行](logs/haptics-service-route-review.json)，实际运行XML列表消费者（列表布局为夹具）和普通on入口。波形31分支请求SVC0及Source0→1；mixer写失败仍返回0且缓存可使下次跳过重试。普通on在校准标志已置位/空callback条件下直接提交CUSTOM31，不调用mixer，因此不能以缺Source切换认定普通长震动无输出的根因。未执行ALSA/DAPM/DSP或真实电机，未修改生产镜像；当前1c0813cf候选、震动及12组目标继续进行中。详见[范围](docs/HAPTICS-ADAPTATION.md)。

设定日期：2026-11-11（北京时间）  
适配对象：小米 15S Pro / dijun / XRing O1  
工作目录：`/root/AAA/xringo1-twrp`  
维护设备树：`dtsrc/O1_asic_dual`  
构建源码：`/root/AAA/twrp`，目标 `twrp_dijun-bp2a-eng`

> 核心目标：尽最大限度适配 OS3 + OS4，优先交付一个自动识别版本的 recovery 镜像；如果同一镜像能够可靠容纳 OS2 的适配，则一并覆盖 OS2。整理为可复现、可维护的设备树，逐项完成功能适配、使用说明和离线验证。本轮不连接手机、不刷机、不做实机测试。

OS4 正式版增补已完成本轮离线档案、选择/混装拒绝、构建与同镜像脚本验证：`os4-stable` 对应 `OS4.0.4.0.XODCNXM`。旧 `os4-current` 继续表示 OS4.0.0.19。详见[正式版增补记录](docs/OS4-STABLE-ADAPTATION.md)，硬件仍为 U。

设置交互续修：公共checkbox/switch行此前只有右侧控件响应，文字/空白未绑定。新增0033整行命中并复用统一取消guard，保留原业务target/保存失败回退。真实LVGL输入20项通过，旧组件同组8项失败，覆盖拖出返回、滚动、禁用、失败重试。新候选[settings-row镜像](imgs/built/recovery-dijun-unified-settings-row.img)，SHA256 `3c0bed7c0e93b2b5b7a50aada62165d69562c6217955a35d85eb4e03ba7cbe67`，installclean/30并发构建及716来源/封装通过。不是所有设置现场根因的确认，未改震动驱动/幅度/校准；详见[范围](docs/SETTINGS-ADAPTATION.md)。全部12组目标仍在进行中。

当前 P0：OS4 正式版触摸现场已定位到raw报告模式，用户写raw0后恢复215条事件/7组按下抬起；普通报告启动策略与设置嵌套persist路径修正已进入487b5候选。自动冷启动、GUI与快速唤醒尚未确认，仍保留P0；此前累计IRQ/无事件快照是历史证据，不能继续作为当前未知边界。详见[触摸失效排查](docs/OS4-TOUCH-FAILURE.md)。

2026-11-12 定向排查：现场 runtime 已确认精确 cache 和模块阶段完成；再次核对原始 ISR 的 TUI/锁/GPIO、报文获取与普通报告门控，尚无证据选定其中分支。更正早期 sensorhub 分支解释：原始 ISR 在状态 bit0 置位时打印日志后继续解析，并非直接阻断事件。已提供[静置/划屏对照采集脚本](scripts/collect-touch-no-events.ps1)，随附设备侧脚本，保存分时 IRQ 与事件，未执行实机采集或生成新修复镜像。下一证据需求是动作关联的 IRQ、SPI DMA 差值及同期事件/驱动日志，避免继续用累计中断或合成成功场景替代故障定位。

## 当前执行检查点

2026-11-12当前候选为`recovery-dijun-unified-clock-failure.img`，SHA256 `1c0813cf324d76be52e588e4dd3358c1c104946841e393aef84df2d951437adc`。时间格式化原先忽略time/localtime_r失败，新增0031清空输出并传播错误；28组状态读取检查通过，旧实现3组失败。installclean/30并发构建、712来源与包装检查通过；同镜像profile回归9组/102次阶段调用通过。详见[范围](docs/CLOCK-FAILURE-ADAPTATION.md)。没有实现RTC漂移补偿，震动及整体12组未完成项保留。

2026-11-12震动诊断补齐原厂HAL长震动对照：独立工具新增显式CUSTOM{0,31}/gain100/定时erase入口，31项主机检查与12项目标ARM64启动/失败检查通过。请求与原始服务捕获比对，未在手机执行或修改生产震动路径；两入口兼有波形/增益差异，不能单独判因。详见[用法和限制](tools/haptics-diagnostic/README.md)。整体12组保持进行中。

2026-11-12当前候选更新为`recovery-dijun-unified-fsck-result.img`，SHA256 `e153160d5cb2c8f438a899847bff6714caee37ac32eeb136996ef1aa08395b11`。修正e2fsck退出1（已修正错误）被普通ExecCmd误判失败；真实Repair146断言通过，旧实现3断言失败。交付ARM64工具对一次性ext4链接计数错误实际修正，返回1后复查0、内容一致；文件系统套件增至17项。installclean/30并发构建、封装与711来源记录通过；同镜像profile回归9组通过。详见[结果处理](docs/FSCK-RESULT-ADAPTATION.md)。震动及完整12组未完成项保留。

2026-11-12补充[当前镜像文件系统工具实际执行](docs/FILESYSTEM-TOOLS-EXECUTION.md)：15项通过，ARM64 linker/库/工具取自fac3c815镜像，在QEMU用户态操作私有普通文件，覆盖ext4格式化/填充/扩容/检查、F2FS casefold格式化/填充/结构检查、EROFS压缩/提取/内容比对与三类无效卷拒绝。未接GUI/PartitionManager、内核挂载、加密或物理块设备；损坏修复、异常I/O和完整生命周期仍待补。震动及12组未完成项保持进行中。

2026-11-12震动音频初始化复核：[两份OS4原始控制查询/文件初值12项](logs/haptics-algorithm-defaults-review.json)确认SVC FLAGS文件初值0、DVL EN由参数覆盖为1；音频XML另配置SVC=1。原始直接FF start worker未调用这些ALSA开关，但DSP内部依赖仍未知，不能据此认定缺音频服务是根因，或盲目开关保护/提高幅度。详见[分析边界](docs/HAPTICS-ADAPTATION.md)。生产镜像未变，实际校准/状态待既有采集证据；震动、设置现场结果和完整12组仍未完成。

分区操作具体缺陷已修正：0028之外，清除/转换/修复/调整大小仍把嵌套挂载点截为/mnt，/system别名在后三入口也未统一。新增维护补丁0029按选中owner路由并保持操作锁，传播子分区失败和cache降级结果；46断言通过，旧实现20断言失败。设置31/21、备份55、恢复54与profile核心回归通过。installclean后make -j$(nproc)构建30并发成功；新候选`recovery-dijun-unified-partition-paths.img`，SHA256 `fac3c815d6fab6febe23910c2f7bbf2c28d509a35003cb9db6df388b9237b4ed`，710来源记录与封装通过，同镜像profile回归9组/102阶段通过。[范围](docs/PARTITION-OPERATION-PATHS.md)仅目标路由/错误返回，不是实际格式化/fsck或手机验收；震动未改，完整12组仍未完成。

现场A1校准分支补充：[原始代码核对](logs/haptics-A1-calibration-review.json)两包共16项通过。原始probe读取真实DT后f0=130Hz、redc/q字段均0；在显式上下文转接后的原始calib_dt_config中，A1请求写F0_OTP_STORED=0x208000和Q_STORED=0，而B2跳过Q。A1原始sysfs可接受正值Q恢复，但设备实际Q/persist值和DSP依赖未知，不能把Q=0直接解释为静音。详见[震动记录](docs/HAPTICS-ADAPTATION.md)。原始probe在fw_upload边界注入失败，后续另用原始固件parser上下文；不是完整A1 probe成功或新实机证据。未改校准/增益/保护或生产镜像；震动与完整12组保持未完成。

震动定向状态采集工具已完成：[用法与副作用](docs/HAPTICS-STATE-COLLECTION.md)、[PowerShell入口](scripts/collect-haptics-state.ps1)、[设备脚本](scripts/collect-haptics-state.sh)。先保存dmesg/IRQ，再按已审核OS4属性读DSP/固件/保护算法参数与f0/redc/q，并仅在persist已挂载时读原厂三个校准文件；不播放、不写sysfs、不校准、不挂载。部分show会唤醒DSP，前后日志明确分开；overprotection_gain不能当作通用FF增益。11项私有文件执行通过，包含阻塞FIFO/缺节点/读错误/profile门控/输出拒绝；两份OS4 ELF分组与7项show指针核对。未运行Windows/Android或手机命令，未修改生产镜像；下一步依据设备自身stored/persist差异或保护状态选择修正，物理无震动和完整12组仍未完成。

震动现场证据更新：原先作为触摸日志的raw-off dmesg含43次真实SINE上传成功、start worker完成及配对TRIGGER_CP/COMPLETE_MBOX；时长80×32、106×9、256×2。6次VBST欠压并解除衰减、5条mailbox首次写失败，只有一次提前stop；36次无欠压/提前stop仍不能证明物理输出。此前“无请求后回执”的当前描述已过时；优先查实际增益/校准/供电状态与原厂初始化，保留用户空间调用者/GUI动作未关联限制。见[逐次现场证据](logs/haptics-playback-field-observation.json)、[范围](docs/HAPTICS-ADAPTATION.md)。当前487b5镜像不变，未改震动驱动/幅度/保护，整体12组保持进行中。

设置故障已发现并修正具体路径缺陷：GetRootPath把`/mnt/vendor/persist/TWRP`截成`/mnt`，导致真实分区管理器查不到fstab中的persist并拒绝保存。新补丁0028按最长挂载点/别名前缀匹配，挂载/卸载保持真实owner；旧实现31断言13失败，新实现31通过。此前设置测试替换了分区查找，未覆盖该缺口。详见[设置记录](docs/SETTINGS-ADAPTATION.md)。最新候选[触摸+设置镜像](imgs/built/recovery-dijun-unified-touch-settings.img)，SHA256 `487b5ce3d991e46241bcf7768350d8986b135f6e9b6d5b9aa4c3deb6e5457e32`，已installclean/30并发构建，包装检查与709份来源指纹记录通过；同镜像profile回归9组通过，709份当前来源复核一致。保留原设置文件；用户当前保存是否恢复尚未确认，震动/完整12组继续进行中。

构建后验证完成：新ordinary-reports镜像9组同镜像profile脚本回归通过；普通报告策略7项检查通过；设置存储21项主机回归通过（包含存储不可用/满盘/写入失败）。这些检查不能证明用户当前设置可保存，仍需现场点击后Recovery日志；没有宣称旧的全量审计适用于新镜像。

2026-11-12 最新检查点：用户手动写 `enable_touch_raw=0` 后，event3 捕获215条真实input事件、7组完整按下/抬起及变化X/Y，见[现场干预证据](logs/touch-raw-off-observation.json)。已在维护树加入等待模块live与Xiaomi input注册后的普通报告请求，整个调用timeout 6秒；只标记requested，不将sysfs缓存当作触摸就绪。原厂raw缓存初始值就是1，此前“读到1说明启动后有人写入”的推断撤回；mode1004的延迟worker可开启raw，但尚未绑定到现场来源。新候选[ordinary-reports镜像](imgs/built/recovery-dijun-unified-ordinary-reports.img)已installclean后以make -j$(nproc)构建，SHA256 `0d6b65d3a2e526c95220fd3cffdf6b9021c977c1a028d3055b199091da005bd5`，包装与708份来源指纹已记录。冷启动、GUI与休眠唤醒尚未实机验证。震动及完整12组目标继续进行中。

新增用户故障：设置中的多项项目无法修改。源码共同保存路径会在Flush失败时回退开关/阻止语言与主题应用；尚无本次设置点击后的Recovery日志，保存失败只是待核实分支。未删除设置、未改persist内容；需区分点击无响应与修改后回退，并核对错误日志/挂载/容量。

设置故障续查：当前源码21组设置存储与31条真实分区路径断言再次通过；现有现场日志仍不包含本次设置点击结果。常规设置当前仅右侧复选框绑定修改事件，文字区域不触发切换。准备[操作前后采集工具](tools/settings-state-collector.zip)，保存Recovery日志、挂载状态和设置文件元数据/摘要，等待用户操作后再采集；不自动修改/删除设置或挂载。shell语法与打包字节检查通过，Windows/Android执行未验证。详见[采集方法](docs/SETTINGS-ADAPTATION.md)。生产镜像未变，设置现场故障、震动、触摸自动启动和完整功能目标均保持未完成。

触摸P0新定位：第三批v1 debug日志实际捕获170个0xc0/1664字节raw头、IRQ/SPI各+170、无input事件，raw sysfs缓存为1；控制器处于application/v1。原始ISR仅将0x11送普通parser，当前明确为报告模式与Recovery坐标需求不匹配。已核对写raw节点0请求关闭c0/开启11，但wrapper隐藏回调错误，尚需实际0x11/坐标作为恢复证据，启用raw的来源仍未确定。详见[现场报告](logs/touch-v1-debug-observation.json)和[触摸记录](docs/OS4-TOUCH-FAILURE.md)。触摸未宣称修复；震动/全部12组目标继续进行中。

ARM64动态linker执行补充：[28项检查](logs/profile-linker-arm64.json)使用原始Android输出c282f镜像，六profile各三服务`--list`及缺libteecli负向，共24项；另4项真实动态小程序对照验证构造/main执行与缺符号拒绝，明确`--list`跳过重定位，不宣称安全服务ABI已完整验证。真实namespace、服务本体重定位和合成加密卷仍待完成。详见[范围](docs/PROFILE-LINKER-ARM64.md)。交付目录镜像当前缺失，原始输出仍在，没有复制或新构建。

v1调试采集脚本已增加开启/恢复等级读回与采集退出码检查，5条私有文件执行路径通过；没有设备/Windows执行。第二批现场触摸IRQ+SPI各1613无事件及震动A1/43波形仍是最新实机证据，P0/震动未修复，全部12组继续进行中。

第二批现场日志已改变触摸下一步：静置4.01秒触摸/SPI IRQ增量0；划屏12.01秒两者均增1613，无保存input事件。启动明确TouchComm v1、匹配固件免刷新、后台注册input；重点转v1报文类型、配置/解析到input。初始化power-off警告尚不能当作运行期断电。震动同启动确认A1/43 RAM波形和原厂probe自检软件路径完成，后续按实际芯片条件检查。详见[新观察](logs/touch-action-runtime-observation.json)、[触摸记录](docs/OS4-TOUCH-FAILURE.md)。已准备恢复日志等级的v1 debug采集脚本，未执行设备命令。P0/震动均未修复。

触摸定向定位工具补充：两份原始 OS4 模块静态检查确认 `synaptics_tcm/info` 是 0444 缓存状态回调，没有 SPI/reset/report 切换调用。现有采集脚本在计时窗口外保存该信息；新增分时日志分析器拒绝计数倒退、IRQ 身份变化、采集错误及能力列表冒充事件，10 项合成日志检查通过。现有现场包仍无窗口起止数据，分析为 insufficient，没有新增实机根因证据。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)。工具未集成镜像，本轮生产树和镜像未改；P0、震动及12组目标继续进行中。

震动诊断目标执行：交付的静态ARM64工具在QEMU用户态完成[8项原始目标启动/失败路径](logs/haptics-diagnostic-arm64-test.json)，实际执行bionic、参数解析、时钟、stdio和普通文件的失败ioctl/close。缺节点ENOENT、普通文件ENOTTY、非法参数拒绝均核对；唯一event路径配合临时前缀，不访问真实input，没有上传/播放成功。QEMU未安装或注册binfmt，哈希与来源已保存。工具由“仅目标编译”推进到有限目标执行，仍不证明Android驱动或电机；完整目标/触摸P0/震动未完成，生产镜像不变。

录屏帧检查：新增[6组实际录屏→WebM解析→VP8解码](logs/video-frames.json)，覆盖五档FPS和奇数尺寸、带行填充BGRA，逐帧核对中心YUV、尺寸/时间戳及停止后1500ms时长，ASan/UBSan通过。主机实际生产recorder/converter与libwebm执行，codec使用主机libvpx；未验证ARM64/DRM/完整采样、队列丢帧、I/O故障或独立播放器。详见[验证范围](docs/VIDEO-FRAMES-VALIDATION.md)。没有生产修改或新镜像，录像组保持未完成，触摸P0/震动及12组目标继续进行中。

震动现场定位工具：新增[独立诊断工具及用法](tools/haptics-diagnostic/README.md)，静态 ARM64 文件记录 open/名称/能力/upload/play/erase/close 的 BEGIN、返回码、errno 和单调耗时，明确区分只读 inspect 与显式 play。20 项主机故障/顺序/参数检查通过，48 字节效果与当前 Recovery 捕获一致；没有运行目标二进制、连接设备或改动镜像。当前周期 8ms 与原厂 probe 自检一致、幅度64高于其45，无依据盲目调大。现场真实提交/驱动完成/DSP仍未知，触摸 P0 和全部12组未完成。

校准默认值续接：[36 项检查](logs/haptics-calibration-coefficients-emulation.json)执行原始 WMFW 系数初始化、sysfs store 和 DT 校准配置。三项校准地址未在所查固件/五份参数找到文件初值，不能解释为硬件为零；原厂 DT 的 130 Hz 默认值经原始配置函数写入 F0_OTP_STORED，写失败会返回 -5。因此没有恢复 persist 并不等于基础频率缺失，尚不能据此修复无震动。B2 q 拒绝与 f0/redc 错误传播已验证到显式 PM/regmap 边界；下一步核对 ROM/OTP 与播放依赖。生产镜像不变，完整目标保持进行中。

原厂震动校准恢复核查：两包[16 项原始服务执行](logs/haptics-calibration-restore-emulation.json)确认读取设备 persist 的 z/f0/q 十六进制值、寻找 input0..9 校准节点、逐项跳过非正值；原始写失败被忽略，FF 调用方仍置初始化标志。B2 驱动直接拒绝 q_stored。Recovery runtime 缺少同等恢复流程，但尚无证据把这项差异绑定到现场无震动；先核对固件默认值/系数依赖再决定生产修改，不伪造校准值或运行校准。详见[震动记录](docs/HAPTICS-ADAPTATION.md)。生产镜像未改、触摸 P0 与全部功能任务继续进行中。

震动增益核查：[12 项原始 OS4 指令与固件默认值检查](logs/haptics-gain-emulation.json)确认 probe 初始增益为 100、SOURCE_ATTENUATION 固件默认值为 0；0/50/100 映射为 400/24/0，超过 100 的请求被拒绝。当前没有依据添加 FF_GAIN 来解决“默认静音”，不修改生产幅度或运行校准。现场后续状态、FF 请求是否实际提交与 DSP/电机工作仍未知。原始镜像从构建输出恢复，完整任务继续 `in_progress`。

原厂服务请求续接：[18 场景对比](logs/haptics-service-request-emulation.json)实际执行两包原厂 FF helper：XML 指定 long_vib_id=31，服务发 gain=100、CUSTOM `{0,31}`、replay=0、play=1，stop 参数调用删除效果。当前 Recovery 发 SINE/8ms/64/指定时长；原始 driver worker 在 RAM count=5 夹具拒绝 CUSTOM 编号31，count=32 接受并发送 `0x100001f`，与 Recovery 正弦的 `0x1800081` 不同。两条路径均没有物理验证，不能直接换入口宣称修复；计时线程、原始 user-copy、现场波形数量和 DSP 状态仍未确认。生产代码和 c282f 镜像不变。

| 项目 | 当前结论 | 下一工作 |
| --- | --- | --- |
| OS4 正式版触摸 P0 | 现场raw0干预后坐标恢复，215事件/7组按下抬起；新启动策略已构建，自动恢复未验证 | 核对普通报告请求时序、冷启动/GUI/唤醒稳定性，定位raw开启来源 |
| 震动 | 用户最新确认OS4震动调用正常；其余版本/物理效果不外推 | 不再作为当前排查主线，保留既有证据 |
| 当前产物 | recovery-dijun-unified-sideload-completion.img，SHA256 `f5231d7886615dbfe0a89063706178ed2120866085248e5c7aa47e27ceed2c74`；760份来源核对通过 | ZIP队列23、镜像路由40、侧载生命周期33及安装收尾27已覆盖；实际USB/FUSE/ARM updater仍待完成 |
| 整体目标 | `in_progress`，12组整体功能仍未完成；当前定向交付通过，历史全量审计的来源漂移尚未收尾 | 按任务继续OS3/OS4统一镜像和OS2兼容，推进安装/侧载等其余功能；不要求实机测试 |

本表汇总当前状态；下文保存历史证据，不表示早期“下一步”仍未开展。最新索引为[simulation-report.json](simulation-report.json)，安装进度见[安装验收](docs/INSTALL-CHAIN-VALIDATION.md)，旧证据刷新及各历史“当前”不得外推到新镜像。当前定向交付不等于完整12组验收通过。

构建输出内原始 c282f 镜像已恢复至交付目录并核验；此前“整个工作区已无镜像”的描述不准确，原始构建时来源档案仍未找回，本次清单是当前源码事后重建。OS4正式版触摸和震动均没有根因证据或功能验证，保持未解决。

触摸配置续接：另有两包 62 项原始配置获取/probe 模拟和 2 次原始 dijun DTBO 检查通过。已复现配置失败后 probe 成功、input 注册但 parser 不输出事件；同时覆盖后台配置恢复的合成分支。两包触摸节点直接引用解析后属性相同，ODM 固件/配置与 profile blob 哈希吻合。证据见[配置模拟](logs/touch-configuration-emulation.json)、[设备树检查](logs/touch-devicetree-audit.json)；真实 SPI、panel setup 与实际 cache 发布仍未知，不能将该机制当作本次根因。当前镜像不变。

SPI/供电续接：两包新增 58 项原始 `syna_spi_probe`、Xiaomi DT 解析、GPIO 申请、供电与复位模拟通过，并贯通原始硬件回调→平台 probe→配置→ISR，包含真实 overlay 的 `synpatics,cfg_0` 子节点。pinctrl 获取/状态错误及 GPIO 延迟错误可被部分原厂分支忽略，平台注册成功仍不代表平台驱动已绑定；原始解析取得 1440×3200/倍率 100，供电和复位请求顺序已记录。[证据](logs/touch-spi-emulation.json)不证明实际电平、延时或 SPI 可用。后续已据模块生命周期修正生产脚本并构建 module-state 候选，详见下方当前生产修正；触摸 P0 保持未解决。

本文件是后续执行和验收依据。文中的“目标”“拟新增”“待分析”均表示待完成工作；现有成果与新目标分别记录。

当前生产修正：模块目录存在不再等价于就绪，脚本检查 `initstate=live`，对 coming 做有限等待并拒绝非 live 硬依赖。新候选 `recovery-dijun-unified-module-state.img` 已完成 installclean/30 并发构建，同镜像 96 次原有阶段调用和 24 次状态回放通过；旧脚本同夹具有 14 个断言失败。详见[模块状态记录](docs/MODULE-STATE-ADAPTATION.md)。触摸/震动实机仍未确认恢复，整体 12 组工作保持进行中。

传输与 panel 续接：两包新增 [86 项原厂 SPI 传输/识别入口模拟](logs/touch-transport-emulation.json)、[22 项原厂 panel setup 模拟](logs/touch-panel-emulation.json)。持续全零 lockdown 响应在原厂路径中反复读 flash、在模拟指令预算内未到达 panel 注册；先空后有效响应可继续。panel/notifier 注册失败及报告切换失败也可能被后续流程忽略。这里只确认可复现机制，尚无本次启动证据将其认定为根因；未修改原厂模块或生成新镜像。下一步转向原始协议报文与包装注册接口，触摸 P0 保持未解决。

本次[传输/panel 交付一致性审计](logs/touch-transport-panel-delivery-audit.log)通过：707 份构建来源、当前镜像、同镜像阶段回放、全部已索引证据及文档链接一致。整体仍有 12 组待完成工作，硬件状态保持 U。

包装层与震动初始化续接：两包原厂 Xiaomi wrapper 新增 [50 项 panel/input/raw 接口模拟](logs/touch-wrapper-emulation.json)，确认 input 可脱离 panel 单独注册、raw callback 失败仍可被 sysfs 成功字节数隐藏；因此不增加无错误反馈的强制写节点逻辑。六包另新增 [80 项原厂 PLL/芯片识别模拟](logs/haptics-pll-emulation.json)，涵盖 PLL 五次重试与 OS4 ID/revision 接续失败。当前 `recovery-dijun-unified-module-state.img` 未改，未实机测试；触摸 P0 与震动均未证实修复，后续继续完整协议/固件/DSP/IRQ 边界。

协议识别续接：两包各 31 项、共 [62 项原始 detect/ID parser/长度协商模拟](logs/touch-identification-emulation.json)通过。确认 v2 长度字段为零仍可能 detect 成功，初次读失败可经 identify/reset 合成响应恢复；完整 message/SPI 仍为显式边界。历史 OS4.0.0.19 的 firmware_load AVC 与当前正式版故障未绑定，现镜像已有相关策略规则及二进制决策证据，不重复添加。当前镜像未改，触摸 P0 未解决；后续继续原始 message 编解码与配置/IRQ 接续。

报文续接：新增两包各 45 项、共 [90 项原厂报文/事件/ISR 模拟](logs/touch-message-emulation.json)。v1 原始头读取和分段拼接贯通 parser/ISR；v2 command 10 仍为显式响应边界。确认 v2 report 分配失败可能返回 0 而无数据；两协议空报告复用旧 output 长度可令 ISR 重报旧坐标。两版行为一致，尚无证据把这些机制归为当前全无触摸的原因。生产树与当前 module-state 镜像未改；[交付审计](logs/touch-message-delivery-audit.log)核对输入指纹与关键场景。P0 未解决，后续优先减少 v2 command 边界、核查模块自动加载和 profile/cache 时序，震动及整体 12 组工作继续保留。

加载时序静态续接：[两包 vendor_boot 与当前镜像检查](logs/touch-load-order-audit.json)确认所查原厂首阶段归档没有 Synaptics/Xiaomi touch 模块，recovery RC 没有直接模块加载动作，C++ profile 分支按 cache→modules 调用。未执行 bootloader 合并/init/内核，不能排除所有早载来源；当前文件证据不支持将“固件发布前自动加载”当作根因。后续优先完整 v2 command/帧协议与控制器响应边界。

v2 帧续接：两包各 39 项、共 [78 项原始 command/read/write/CRC/序号/重试模拟](logs/touch-v2-command-emulation.json)通过，取消此前整体 command 响应替代，物理字节仍为夹具。正常配置与应用信息命令接续 ISR 可输出坐标；payload CRC 连续失败后可能返回 0 并产生全零报告，配置 CRC 耗尽还可保存全零配置、后续 ISR 仅发无触点状态。两包一致，不能判定当前实机触发此机制。当前镜像未改，未编译；[交付审计](logs/touch-v2-command-delivery-audit.log)绑定来源和关键分支。触摸 P0、震动与整体 12 组工作保持未完成；下步接续原始 detect/panel/模式恢复，保留 IRQ/内核时序边界。

v2 启动接续：两包各 22 项、共 [44 项原始识别→连接→应用信息/配置→后台→ISR 模拟](logs/touch-v2-startup-emulation.json)通过。应用信息超时的三次事件排空和重发实际执行；耗尽或配置超时后连接仍成功，进入 bootloader 模式并注册 input，但无事件。仅恢复 application 模式不会补配置；请求固件失败或更新三次失败时，后台可跳过应用配置重取仍注册 input。更新成功边界之后执行原始应用信息/配置获取，可恢复合成坐标。固件更新本身、panel、IRQ 注册及内核调度仍是夹具，不是此次根因证据。当前 module-state 镜像未改；[交付审计](logs/touch-v2-startup-delivery-audit.log)绑定全部来源。触摸 P0 和整体 12 组保持进行中，下步接续原始 panel/flash 与报告切换到同一启动链。

panel/flash 接续：两包各 16 项、共 [32 项 v2 启动→原始 DT/panel/报告切换→后台/ISR 场景](logs/touch-v2-panel-startup-emulation.json)通过。其中六项取消 flash-area 整体替代，实际执行 identify、切 bootloader、boot-info、boot-config 128 字节读取及切回 application；物理响应仍合成。普通报告启用失败后连接仍返回 0 并注册 input，后续有无坐标取决于所供报文，不能把模拟发送成功当作控制器启用。全零 lockdown 在预算内持续重读、未排后台；一次 flash 读取超时可重试恢复。配置缺失进入 bootloader 时原始 panel 跳过报告切换，输入注册仍无事件。两版一致，触摸根因未定。当前镜像未改，[交付审计](logs/touch-v2-panel-startup-delivery-audit.log)核对来源与分支；后续继续固件解析/更新、wrapper 注册及 IRQ/内核时序，震动与整体目标继续进行中。

固件解析续接：两包各 13 项、共 [26 项原厂固件解析/比较及启动接续](logs/touch-firmware-emulation.json)通过。实际使用原厂 `synaptics_spi_dijun.img`，原始 ARM64 解析三个有效区域并校验 CRC、比较 build 与完整 16 字节配置 ID。匹配时无需写 flash，但后台仍执行原始应用信息/配置重取；已有有效配置时解析失败仍可能出事件，缺配置且三次 flash-access 失败时仍可注册 input 却无事件。不同 ID/强制更新在原始 flash 访问 identify 超时处终止，尚未执行擦除/编程/复位。控制器响应和内核服务仍为夹具，两版结果一致，不是此次实机根因证据。生产代码及当前镜像不变，[交付审计](logs/touch-firmware-delivery-audit.log)保存一致性结果；触摸 P0、震动和整体 12 组工作继续进行中。

震动固件续接：旧 OS4/正式版正常与校准固件共 [64 项原始 DSP parser/系数初始化/地址查询模拟](logs/haptics-firmware-emulation.json)通过，正常 525、校准 428 条系数与 34/35 次写入请求逐段核对。空算法表时 parser 可返回 0，但后续原始系数地址查询仍返回 -22；合成匹配表可恢复软件地址解析，未运行真实 DSP。范围见[固件记录](docs/HAPTICS-FIRMWARE-EMULATION.md)，[交付审计](logs/haptics-firmware-delivery-audit.log)绑定来源。生产代码和当前镜像未改，震动未修复；触摸 P0 与整体 12 组继续进行中。

震动上传续接：两包新增 [72 项原始上传/PM 关机/身份检查接续](logs/haptics-upload-emulation.json)通过，正常/校准固件分别沿原始 parser、系数初始化和版本检查到达 DSP config，在明确的 MEM_RDY 写失败处停止。五次 PM 重试、十次关机等待、预处理失败跳过固件释放、固件 ID/最低版本边界均有记录；参数 `.bin` 虽使用真实字节，但合成算法版本导致原始 parser 拒绝，不能当作参数加载或 DSP 启动成功。详见[上传范围](docs/HAPTICS-FIRMWARE-EMULATION.md)，[交付审计](logs/haptics-upload-delivery-audit.log)核对来源。当前生产/镜像未改，触摸 P0、震动与整体目标继续进行中。

原厂参数续接：新增两包 [16 项 packed 算法表→原始参数 parser/write 接续](logs/haptics-coefficients-emulation.json)，独立从正常/校准 wmfw 各解出 14 行 ID/revision/X/Y 基址，作为 regmap 读取边界。原始参数 parser 接受实际参数，正常/校准新增 34/28 次参数写入逐段匹配；主参数缺失、版本错或首写失败后外层仍继续到 config，已分别核对不完整写序列。全组在 MEM_RDY 更新注入失败，未启动 DSP。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-coefficients-delivery-audit.log)，当前镜像不变，触摸 P0、震动及整体工作继续进行中。

2026-11-11 执行进度：已生成 `imgs/built/recovery-dijun-unified-module-state.img`，
六套 profile、78 个去重 blob 和启动激活代码进入同一镜像。选择预检 77 场景通过；
从当前触摸优先镜像取出的脚本在六包两槽位及异常夹具上完成 96 次阶段调用，核心门控与 Binder 期限也通过主机回归。
镜像不再携带旧模块覆盖，按精确档案从已安装固件取得额外模块；容量与 OS4 安全组件字节保留检查通过。
这仍是离线候选：完整功能模拟、多用户、合成加密卷、备份/刷写等尚未完成，硬件保持 U。
设置保存已改为同目录临时文件提交，向界面传递实际错误；21 组持久化/损坏输入/时区回归通过，详见 [设置适配](docs/SETTINGS-ADAPTATION.md)。
多用户发现、异常 XML 和逐用户选择已修复，核心 18 组、后台 12 类、界面路由 8 类离线检查通过；[多用户记录](docs/MULTIUSER-ADAPTATION.md)列明尚未验证的协议和超时边界。
电量/充电读数和温度接口完成 24 组主机回归，缺值不伪造满电、0% 可显示、缓存并发已保护；温度图形入口仍未实现，见[状态读取](docs/STATUS-ADAPTATION.md)。
震动设置后端到 FF 的 22 场景回归通过，设备不存在、晚注册、断开及写入失败均有处理；六包原厂属性/驱动/固件哈希核对通过。另有 21 项实际 LVGL 控件回放通过，修复双重反馈和取消逻辑；完整页面与物理电机仍未验证，见[震动适配](docs/HAPTICS-ADAPTATION.md)。
震动原厂 ARM64 函数新增 120 项主机模拟通过，覆盖六份样本的生产 FF 请求、正弦参数转换、播放入队、DSP 写失败和槽耗尽；完整初始化与硬件仍待验证，见[驱动函数模拟](docs/HAPTICS-DRIVER-EMULATION.md)。
震动注册/上传/擦除生命周期另有 90 项原厂 ARM64 模拟通过，六包八条原始 DTBO 共 48 次合并检查通过；dijun 条目确认 130 Hz 且无固件延迟属性。发现原厂 PM 失败可能留下成功结果，OS4 组合模块成功也不保证 input 注册；不得据此认定历史无震动的唯一原因，见[生命周期与 DTBO 记录](docs/HAPTICS-LIFECYCLE-EMULATION.md)。
本次进度保存：已实现 GUI 震动后台 owner，16 项并发/I/O 门闩与 4 项生产 FF 阻塞联调通过，原有 22 项路由、21 项 LVGL 控件和 64 项操作完成回归通过。按 30 并发 installclean 后重建独立候选，六包同镜像 77 次阶段调用、init 和策略检查通过，见[后台执行记录](docs/HAPTICS-WORKER-ADAPTATION.md)。新增触摸 P0 后整体有 12 组功能工作未完成，以 `simulation-report.json` 的 `not_yet_completed` 为准。

历史 module-state 候选 SHA-256 为 `abc31e604a466df1d6102132caa5a0a880a9f0f8a3f4acb43e1b46ce8c06d9ae`；当前产物指针见上方最新检查点。上一份 OS4 正式版候选与证据保留；本轮不连接设备，物理电机仍为 U。

本次续接进度：六包新增 120 项原厂 start/stop worker、固件失败与 I2C 包装模拟，另有 54 项基于原始 dijun DTBO 属性的早期 probe 模拟全部通过。确认两类 pinctrl 错误分支可能返回 0 而未注册 input；这不是历史实机根因结论。生产代码与当前镜像未变，详见[播放与初始化边界](docs/HAPTICS-PLAYBACK-EMULATION.md)；新增证据已纳入[交付一致性审计](logs/haptics-playback-delivery-audit.log)，707 份来源、镜像、设备树与报告指纹核对通过。

续接执行点：优先排查 OS4 正式版触摸 profile/cache、probe 与 input 事件生成，保留用户失效状态；随后继续分析 PLL/芯片识别之后的固件与 DSP 启动、IRQ/完成事件，并补齐完整 GUI 页面与业务回归；后台 stop 可以等待正在执行的内核 I/O，没有永久阻塞时的退出期限。不可把 PM 故障注入写成历史实机根因。随后按机器报告推进其余 11 组功能，生产改动继续保存补丁并按 `make -j$(nproc)`、最终 installclean 的既定流程构建与验证。

六份所需分区已全部提取并校验；system/system_ext/product/mi_ext/mi_product（存在时）的目录与选定配置资源清单已齐。
详见 [功能矩阵](compatibility-matrix.md)、[启动选择](docs/PROFILE-SELECTION.md)、
[模拟报告](simulation-report.md)、[功能入口](FEATURE-USAGE.md)、[维护流程](MAINTENANCE.md)。

归档恢复完成 30 项实际 libtar 主机回放，修复硬链接/长名称越界、短写误报、结束块检查和扩展属性解析；同组旧代码 17 项失败。压缩/加密与分卷另有后续管道回放；稀疏空洞与完整任务流程仍待补，见[归档恢复范围](docs/ARCHIVE-RESTORE-ADAPTATION.md)。

原始镜像复制新增 65 项回放通过，含实际备份→恢复往返、容量拒绝、I/O 故障、取消和进程中断。备份临时文件提交与恢复已写块不可回滚的边界分别记录；完整会话/digest/槽位流程仍待补，见[原始镜像范围](docs/RAW-IMAGE-ADAPTATION.md)。

操作完成反馈新增 64 项回放通过，旧代码 25 项失败；已修复校时影响、队列计时、重复通知及能力/时长检查。覆盖备份/恢复/ZIP worker 和 screen tick，完整分区会话仍待补，见[完成反馈记录](docs/OPERATION-FEEDBACK-ADAPTATION.md)。

恢复会话预检新增 54 项通过，旧代码 45 项失败；修复取消残留、父子目标清单、后续目标先检查再写入及跨线程组分卷校验。完整管理器端到端仍待补；压缩/加密管道已有后续独立回放，见[恢复预检范围](docs/RESTORE-SESSION-ADAPTATION.md)。

备份取消与 tar 生命周期新增 55 项通过，旧版同组 35 项失败。PID/进程组归属、目录清理、`.info` 发布及 GUI 取消收尾已修正；完整管理器流程与断电完整性仍待补，见[备份会话范围](docs/BACKUP-SESSION-ADAPTATION.md)。

归档编解码新增 46 项主机回放通过，真实执行 tar/pigz/OAES、普通/加密/压缩/混合分卷并逐字节恢复。修复 AES 管道 EOF 死锁、短读、编码器失败误报及共享缓冲区；完整管理器、真实进度、稀疏空洞和断电完整性仍待补，见[编解码范围](docs/ARCHIVE-PIPELINE-ADAPTATION.md)。

MTP 对象与会话新增 42 项生产代码回放通过，旧源码同组 28 项失败。修复存储撤销、递归枚举、删除失败丢句柄、重命名覆盖、上传短写/长度检查和断线清理；后续移动/复制与重建另有独立回放，见[MTP 对象范围](docs/MTP-OBJECTS-ADAPTATION.md)。

MTP 移动/复制与目录重建新增 48 项通过，旧代码同组 36 项失败；原有 42 项对象回归在最终代码上通过。移动保留句柄、复制不覆盖已有目标，跨文件系统失败保留可用副本，rescan/inotify 溢出和根目录重建已覆盖；后续事件退出已有独立回放；解密后发布仍待补；configfs 调度另有独立回放，见[MTP 转移范围](docs/MTP-TRANSFERS-ADAPTATION.md)。

MTP 事件生命周期新增 62 项通过，旧代码同组 56 项失败；单工作线程、有界队列、可取消 AIO 和两秒请求期限替代每事件阻塞线程，原有传输/对象/移动回归通过。实际 UDC 仍待验证；configfs 调度另有独立回放，见[事件退出范围](docs/MTP-EVENTS-ADAPTATION.md)。

USB init/configfs 切换新增 42 项通过，旧配置同组 33 项失败；当前镜像的 45 项专用域策略检查通过，补齐 ADB/MTP/fastbootd 服务交接及 minadbd 提前就绪。MTP 调用者、控制请求和真实 UDC 仍单独验收，见[USB 切换范围](docs/USB-CONFIGFS-ADAPTATION.md)。

MTP 控制报文与事件批处理新增 66 项通过，旧源码同组 60 项失败。修复状态回复长度/越界、短传输错误、不支持请求的 STALL 和事件错误丢失；交易取消、会话复位及兼容路径调度仍待整合，见[控制请求范围](docs/MTP-CONTROL-ADAPTATION.md)。

MTP 调用层 40 项、消息接收端 11 项通过；旧源码分别 24/40、4/11 项失败。启停确认、有限回收、非阻塞消息及父进程退出已覆盖，完整解密后发布联调仍待补，见[调用层范围](docs/MTP-CALLER-ADAPTATION.md)。

## 1. 优先级与完成定义

| 优先级 | 目标 | 完成条件 |
|---|---|---|
| P0 | 固件证据、启动基础、分区识别和解密链路 | OS3 两个样本与现有 OS4 样本均有独立分析档案；组件选择、启动顺序、异常处理通过离线验证 |
| P1 | 同一镜像覆盖 OS3 + OS4，完成日常 recovery 功能 | 对每个样本使用同一产物哈希执行模拟；功能矩阵、使用文档和未验证项齐全 |
| P2 | 在同一镜像中加入 OS2 | OS2 两个样本完成相同检查，不破坏 OS3/OS4 的选择规则和功能，不超过镜像容量 |
| 交付要求 | 整理设备树、补丁和构建流程 | 原始文件可溯源，配置按兼容组合组织，构建和验证可重复，清除过时的支持声明 |

“一个文件”定义为：**同一 SHA-256 的 `recovery.img` 用于覆盖范围内的版本**，运行时自动选择适配组合。按 OS 编译不同镜像、要求用户替换模块，均不算单文件兼容。

优先完成 OS3/OS4；OS2 作为可行性扩展。若无法合并，先提供具体冲突证据、容量测算及已尝试的兼容方案，再给出实际可交付范围。不得通过混装 ABI、忽略依赖错误或压低功能标准来宣称“全版本通用”。

## 2. 固件样本与来源

“初始版本”“最后版本”沿用用户给出的样本定位；本次未独立核验官方发布序列。首尾两个样本不自动代表中间每个版本。

| 样本 ID | 系统版本 | Android 信息 | 内核 / ABI 当前结论 | 适配优先级 |
|---|---|---|---|---|
| os3-initial | OS3.0.4.0.WODCNXM | 包内 Android 16 / SDK 36 | 6.6.77，g5770c661275f；不能仅按 6.6 选择 | P0/P1 |
| os3-final | OS3.0.304.0.WODCNXM | 包内 Android 16 / SDK 36；构建身份 16OS3.1.260921… | 6.6.118，gc44b714366cc；与初版触摸 ABI 不同 | P0/P1 |
| os4-current | OS4.0.0.19.XODCNXM | 已提取 system 为 17；vendor 与 system 身份分别记录 | 已分析 6.18.21 路径 | P0/P1 |
| os4-stable | OS4.0.4.0.XODCNXM（用户指定首个正式版） | system Android 17 / SDK 37；system SPL 2026-10-01，vendor SPL 2026-09-01 | 6.18.21，g284297031c53；独立模块/安全组件档案 | P0/P1 |
| os2-initial | OS2.0.121.0.VODCNXM | 包内 Android 15 / SDK 35 | 6.6.30，g8eff17a54aa9；厂商 ABI 须独立比较 | P2 |
| os2-final | OS2.0.209.0.VODCNXM | 包内 Android 15 / SDK 35 | 6.6.77，g561b227c0e7d；与 OS3 初版存在符号差异 | P2 |

下载来源：

- [OS3 最后版本：OS3.0.304.0.WODCNXM](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS3.0.304.0.WODCNXM/dijun-ota_full-OS3.0.304.0.WODCNXM-user-16.0-67dca2cb87.zip)
- [OS3 初始版本：OS3.0.4.0.WODCNXM](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS3.0.4.0.WODCNXM/dijun-ota_full-OS3.0.4.0.WODCNXM-user-16.0-1398c39929.zip)
- [OS2 最后版本：OS2.0.209.0.VODCNXM](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS2.0.209.0.VODCNXM/dijun-ota_full-OS2.0.209.0.VODCNXM-user-15.0-b8b8e6c29b.zip)
- [OS2 初始版本：OS2.0.121.0.VODCNXM](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS2.0.121.0.VODCNXM/dijun-ota_full-OS2.0.121.0.VODCNXM-user-15.0-06c0ede3f3.zip)
- [OS4 首个正式版：OS4.0.4.0.XODCNXM](https://bkt-sgp-miui-ota-update-alisgp.oss-ap-southeast-1.aliyuncs.com/OS4.0.4.0.XODCNXM/dijun-ota_full-OS4.0.4.0.XODCNXM-user-17.0-b0ce732f48.zip)。
- OS4 旧样本本地包：`dijun-ota_full-OS4.0.0.19.XODCNXM-user-17.0-aa6a58e947.zip`。

2026-11-11 对四个远程链接的 HTTP HEAD 检查均返回 200，并声明支持字节范围请求。原始响应记录在 [固件来源检查记录](logs/firmware-source-head-20261111.json)。随后已范围提取六份 OTA 元数据、payload manifest 与启动/模块分区，并校验 metadata hash、操作数据 hash（存在时）及完整分区 SHA-256。完整远程 ZIP 尚未下载，ETag 不能当作其 MD5；其余分区获取状态以每份 `firmware/samples/<sample>/inventory.json` 为准。

后续先获取 OTA 元数据、payload manifest 和关键分区；必要时完整下载。记录文件大小、SHA-256、提取工具版本、分区哈希和校验结果。范围提取须正确处理 ZIP/ZIP64、payload 操作类型与数据区偏移；未知操作类型必须报错，禁止静默输出不完整分区。

## 3. 当前起点与已知缺口

| 项目 | 已有证据 | 对本轮工作的含义 |
|---|---|---|
| OS4 启动与用户 0 解密 | `twrp-recovery-mitee-bootfix.img`，MD5 `5819f969bceb558cf734d5ae5608e211`，既有日志证明 metadata 和用户 0 CE 解密 | 保留为历史已验证基线；本轮无需重新实机测试 |
| 外设修复候选 | `twrp-recovery-devicefix.img`，MD5 `1795eee8bfec097568a0ead30182ba67`，构建、回归和镜像检查通过 | MTP、时区、震动及快速开关屏已实现候选修改，仍只能标记对应离线证据 |
| 双内核目录 | 已有 `/lib/modules/6.6`、`/lib/modules/6.18` | 只说明已有组织方式，尚不足以证明 OS2/OS3 每个样本的模块兼容 |
| MiTEE 配置 | 当前服务与 crypto profile 来源于 OS4，准备脚本限制 6.18 路径 | 必须改为按固件组合选择；不能把 Android 17 / 2026-09-01 身份套给 OS3/OS2 |
| 多用户解密 | 新增逐用户选择与核心/线程/路由模拟；旧 skip 变量没有源码消费者 | 工作资料绑定密钥、同步调用中止及真实用户 999 解锁仍未验证 |
| 文档与脚本 | README 仍有笼统功能勾选、旧模块数量和历史构建说明 | 用版本×功能×证据矩阵替换；审计脚本与注释是否一致 |

已有证据入口：[crypto 适配记录](dtsrc/O1_asic_dual/CRYPTO-ADAPTATION.md)、历史基线与外设候选名称/哈希见本节上表（当前工作区未保留其 JSON，不作为本轮可复核产物）。

## 4. 单镜像兼容方案的技术目标

### 4.1 逐包建立完整档案

每个样本至少分析：

- `boot`、`init_boot`、`vendor_boot`、`recovery`、`dtbo`：头格式、内核来源、ramdisk 合并顺序、bootconfig、init 和设备节点要求。
- `vendor`、`odm`、`vendor_dlkm`、`system_dlkm`、`odm_dlkm`：驱动、依赖、固件、HAL、私有库、VINTF、init、SELinux 和 linker 配置。
- `system`、`system_ext`、`product`、`mi_ext`、`mi_product`：系统身份、补丁级别、动态分区布局、依赖资源及恢复时挂载要求。以该包实际存在的分区为准。
- 原厂 fstab：文件系统、槽位规则、metadata/FBE/wrapped-key 参数、persist 路径、USB/OTG 和挂载顺序。
- KeyMint/Keymaster、Gatekeeper、tee-supplicant、keystore2、TA 与共享库的真实接口和启动条件。每个文件记录来自哪个包、哪个分区及其哈希。

以提取结果建立兼容类别；不可把 HyperOS 大版本、Android 版本、内核大版本、模块 ABI 视为同一个维度。

### 4.2 启动和内核模块

1. 检查各包 recovery 格式，优先延续当前 **recovery 不带内核，使用对应系统 boot/vendor_boot** 的布局；确认所有样本后才能确定共同镜像格式。
2. 保持原厂 vendor_boot 对关键 first-stage 模块的所有权。当前基线中不存在自定义 `modules.load` / `modules.load.recovery`；不得未经逐包验证重新引入严格加载列表。
3. 模块选择至少结合内核 release、架构、页大小、vermagic 条件、导出符号和 `CONFIG_MODVERSIONS` CRC 等可获得证据。`module_layout` CRC 相同也不能替代完整依赖检查。
4. 同一 `major.minor` 下若存在不同 ABI，改为独立 profile 和明确选择规则；不得直接覆盖同名 `.ko`。不兼容模块必须在加载前被排除。
5. 对额外触摸、震动、USB 等模块采用有依赖和来源记录的后续加载；所需固件必须在请求发生前可用。
6. 首阶段必需驱动缺失与可选功能驱动缺失分别处理。未知组合不强制插入猜测模块；记录原因，并尽可能保留已可用的界面和 ADB。

### 4.3 解密组合与运行时识别

- 在修改任何 recovery 身份属性之前，读取并保留真实来源信息：实际内核、当前槽位以及对应系统/vendor 的构建身份、补丁级别和可核验文件指纹。
- 为每种已分析组合选择一套一致的 `TEE + TA + KeyMint/Gatekeeper + 私有库 + init + VINTF + crypto profile`。允许经证明相同的文件去重，不允许将不同版本组件随意拼接。
- 已知 MiTEE 对执行路径敏感；保留该版本原厂需要的真实可执行路径和权限，并检查 linker 的符号版本、Binder 库配对及服务注册唯一性。
- OS/SPL 等解密身份由相应固件档案产生，写入时机早于服务启动；不得统一伪装成最新版，也不能靠无限提高版本号解决密钥升级错误。
- persist、metadata 和密钥存储遵循各包布局。恢复流程应保留先前存在的挂载，禁止用临时空目录替代真实安全存储；不得把加密原始 userdata 的挂载失败直接解释成损坏并触发格式化。
- 将用户 0、无锁屏凭据、PIN/密码、次用户与工作资料分成不同模拟用例。离线模拟不保存真实用户密码或密钥，不把模拟 provider 打包进正式镜像。
- 缺少或冲突的 profile 应给出明确状态和诊断，服务重试有上限；解密服务异常不能无限等待或触发 recovery 自动重启循环。

### 4.4 一份镜像的容量与覆盖边界

先考虑同内容去重、公共依赖提取、按 profile 激活私有组件，以及复用目标系统上匹配且可访问的资源。评估后者时必须覆盖分区尚未挂载、系统已清除、OTA 中间状态等情况；依赖系统文件的功能须在说明中写明前提。

以所有目标样本中最小 recovery 容量和各自头/封装要求计算预算。当前统一候选文件为 104,857,600 字节，其中压缩 ramdisk 为 76,627,259 字节；文件尾部填充不等于实际内容已占满分区。每次构建报告内容大小、总大小与真实可用余量，不能只看压缩前文件大小。

中间版本仅在关键组件指纹和兼容条件可证明等价时纳入覆盖类别。对于未采样的后续 OS4 版本，提供增补 profile 的流程，不宣称已保证兼容。

## 5. 功能适配、使用入口与离线验收

每行都要在每个目标样本下填写状态，不能以“菜单存在”或“编译成功”代替功能链路通过。适用功能完成实现、异常处理及使用说明；不适用项须有固件或源码依据。

| 功能 | 适配和使用要求 | 离线检查 / 模拟验收 |
|---|---|---|
| 启动、ADB、日志 | 正常进入 recovery；电脑 ADB shell/pull/push 有明确说明；失败可诊断 | ramdisk 合并、init/import、权限、服务启动图、超时与退出策略；模拟节点缺失/服务失败 |
| 屏幕、亮度、界面 | DRM 显示、分辨率、旋转/缩放、亮度、字体和语言；明确设置入口 | KMS 属性缺失/存在、单/多 plane 配置、虚拟 framebuffer、UI 截图和亮度节点 mock |
| 触摸、按键、唤醒 | 点击、滑动、多指、坐标缩放、音量/电源、组合截图、快速开关屏 | 回放输入事件与坐标边界；双按、长按重复、截图组合、唤醒输入门控、帧间顺序回归 |
| 震动 | 按钮/键盘/操作反馈和强度或时长设置；匹配原厂驱动 | 模块/固件匹配；LED、timed_output、FF 能力探测与 ioctl 模拟；不支持的能力正确降级 |
| 时间、电量、温度 | UTC/时区正确，设置可保存，电量/充电/温度显示合理 | RTC/时区/DST、重启设置加载、Health/sysfs、缺失值和边界值模拟 |
| metadata 与 FBE 解密 | 启动解密入口、凭据提示、内部存储路径；保持数据与密钥语义 | ELF/符号/TA/接口检查、服务注册和调用流程、dm-default-key/fscrypt 参数、合成加密卷；硬件密钥结果单独标记未验证 |
| 多用户与工作资料 | 识别用户、解释可访问范围；不强行沿用跳过次用户配置 | 枚举、逐用户状态、错误密码、用户缺失、隔离和超时流程；真实 TEE 解锁仍未验证 |
| 挂载与文件系统 | system/vendor/odm 等、metadata/persist、mi_ext/mi_product 和内部存储 | 对每版真实 fstab/LP metadata 解析；ext4/EROFS/F2FS 夹具、只读/读写规则、缺失逻辑分区、挂载释放 |
| MTP | 内部存储与 OTG 的电脑访问；启停后 ADB 可恢复；说明加密未解开时行为 | FunctionFS 描述符、配置状态机、双 ready 顺序、MTP 操作/存储事件、文件内容哈希；Windows 真机枚举未验证 |
| USB OTG | 识别外置存储、浏览、备份目标与移除；所需格式逐项声明 | controller/role 配置、vfat/exFAT/NTFS/ext4 能力检查；虚拟块设备插拔、只读卷、满盘及 I/O 错误 |
| 安装 ZIP、镜像刷写、ADB sideload | 每种入口独立说明目标选择、槽位和失败提示 | 测试包/合成分区上的成功与失败、尺寸检查、路径路由、传输中断与校验；不写真实手机或主机物理盘 |
| 动态分区、A/B、fastbootd | 槽位读取、启动项选择、逻辑分区操作和重启入口 | 使用各版 LP/boot-control 夹具；active/inactive 路由、分区容量和失败路径；真实 bootloader 行为未验证 |
| 备份、恢复 | 文件备份与原始分区备份分别说明；目标、排除项、加密状态和可恢复范围明确 | 临时镜像/目录内往返，比较内容、权限、xattr、符号链接、稀疏文件；覆盖压缩、分卷、损坏包、满盘和中断 |
| 清除、格式化、修复/转换文件系统 | 明确可选分区、确认流程和保留项；仅展示真实支持的操作 | 一次性镜像夹具上执行，核对目标解析与命令参数；加密失败不自动转换为清除请求 |
| 文件管理、终端、设置 | 路径、权限、持久化设置、重启/关机、截图和录屏入口完整 | 虚拟目录、设置迁移、退出路由；截图像素和视频帧/时间轴可检查 |
| 可选网络、其他平台功能 | 先核对驱动、固件、服务与当前 GUI 是否支持；有依据再纳入 | 建立依赖与协议模拟；尚未具备的能力显式标记，不能借通用 README 宣称支持 |

涉及 OTA 快照状态时，只做离线元数据和路由一致性检查，不将其重新扩展成 AVB/vbmeta 排查或刷写任务。

## 6. “模拟适配”的执行范围与证据等级

本轮只在主机、容器、临时目录、一次性文件镜像及适用的模拟环境执行。**不要求用户操作手机，不执行实机 adb/fastboot 命令，不把新实机结果作为本轮完成条件。** 既有实机日志可以作为历史证据使用。

| 等级 | 含义 | 可以得出的结论 |
|---|---|---|
| S0：固件证据 | 文件已提取，来源与哈希完整 | 知道该版本原厂使用什么 |
| S1：静态检查 | 配置、依赖、ABI、符号、结构和调用关系检查通过 | 未发现已检查范围内的静态冲突 |
| S2：主机模拟 | 实际生产逻辑与替身设备/服务结合运行，含异常和回归用例 | 已覆盖的软件路径符合预期 |
| S3：构建及镜像验证 | 从维护树构建成功，核验最终 ramdisk 和 profile 内容 | 交付镜像包含预期实现，可复现检查 |
| H：历史实机证据 | 只引用此前明确版本、明确镜像哈希的设备结果 | 仅支持原结果对应的范围，不能转移到新镜像或其他版本 |
| U：硬件未验证 | 主机不能替代的部分 | 明确记录，不伪装成失败，也不标为功能已实机成功 |

模拟优先使用实际生产函数和状态机，替换系统调用、设备节点、属性源、HAL 返回值；不写一份与实现重复的模型来“自证正确”。合成文件系统、分区元数据、触摸事件和服务异常必须可重复运行。失败回归至少证明修改前失败、修改后通过。

QEMU 或通用 ARM64 环境只用于其实际可模拟的用户空间与虚拟设备路径，不宣称能够复刻 XRing DRM、触摸控制器、MiTEE、RPMB 或 UFS wrapped-key。真正硬件解密、USB 物理枚举、震动效果、唤醒延迟和功耗保持 U 状态。

所有写入测试仅针对本任务创建的夹具，测试工具应拒绝外部真实块设备路径。将解密失败、MTP 断开、驱动缺失和服务崩溃作为预期用例，而非跳过项。

## 7. 设备树整理要求

设备树是交付配置的唯一维护入口，AOSP 源码内的设备目录由可重复脚本同步。平台源码改动保留独立补丁、基线 commit 和应用顺序。不得依赖只存在于 `/tmp`、旧安装目录或手工重打包中的修正。

建议逐步形成以下组织；目录可按 Android 构建要求调整，职责必须保留：

```text
dtsrc/O1_asic_dual/
  BoardConfig.mk, device.mk, recovery.fstab
  profiles/<compat-id>/          # 匹配条件、内核 ABI、解密/服务/固件档案
  prebuilt/common/              # 经哈希确认可共享的资源
  prebuilt/dijun/<compat-id>/    # 不能跨组合混用的原厂组件
  recovery/root/                # 公共 init、选择入口及诊断文件
  patches/                      # 平台源码补丁、基线和顺序
  diagnostics/                  # 有界、可定位问题的诊断工具
scripts/                        # 获取、提取、同步、构建、验证、生成报告
tests/fixtures/<sample-id>/      # 可公开/可复现的固件元数据与合成夹具
docs/                           # 兼容矩阵、功能使用、验证结果和维护说明
```

具体要求：

- 统一 fstab 语法和逻辑分区命名；需要版本差异的部分由 profile 管理，禁止同一分区混入无法解析的绑定挂载行。
- 模块清单和依赖由真实固件派生并可重建；统计数量由脚本生成。清理遗留激活列表、旧根目录覆盖和重复 HAL 声明。
- 每个 blob 保留来源包、分区路径、SHA-256、适用 profile、依赖和打包路径；保持需要的文件类型、执行权限和 SELinux 语义。
- `dijun` 为本轮唯一承诺对象。现有 violin/jinghu 配置保持隔离，不将 dijun 的适配结果标记成它们的支持结果。
- README 的功能勾选改成有版本、有证据的状态表；旧候选与失效说明归档。修正提取脚本注释、实际算法、历史文档之间的矛盾。
- 未实现的自动检测和目录仅标为设计，完成后才能写入“已支持”；构建过程不得静默抓取未固定版本的依赖。

## 8. 执行阶段与退出条件

| 阶段 | 工作 | 退出条件 / 交付物 |
|---|---|---|
| A：样本建档 | 获取四个新增包的关键内容，与 OS4 现有提取物统一校验 | 六份样本档案，缺失/损坏项清单，版本与组件差异表 |
| B：兼容分类 | 比较 kernel/module ABI、分区、TEE、HAL、属性与固件 | 明确可合并类别和冲突点，单镜像预算与识别规则 |
| C：设备树维护 | 实现 profile 选择、公共资源去重、版本服务隔离，整理源码补丁 | 干净同步后可构建，不依赖旧产物；每个 profile 可解释选择原因 |
| D：功能补齐 | 按第 5 节逐项实现、处理异常、写使用说明 | 所有功能有状态；失败项有修复或明确边界，不能留无解释的勾选 |
| E：模拟与回归 | 对全部覆盖样本、两槽位夹具和错误组合运行验证 | 可重复的报告；未知版本、ABI 冲突、缺失服务、满盘、中断等用例通过 |
| F：统一构建与交付 | 清理安装输出，构建同一镜像并逐 profile 检查 | 一个优先面向 OS3/OS4 的候选，条件允许则同一哈希扩展 OS2；提供全部说明与校验和 |

下载、提取、独立档案分析可并行；有依赖的选择、生成和构建按顺序执行。遇到必须依赖真实硬件才能证明的项目，记录 U 并继续完成其余可独立工作，不反复要求实机验证。

## 9. 构建、回归与交付规范

现有脚本：`bash scripts/compile_recovery.sh`。构建继续使用用户指定的全部可用 CPU：

```bash
cd /root/AAA/twrp
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
lunch twrp_dijun-bp2a-eng
make -j$(nproc) installclean
make -j$(nproc) recoveryimage
```

保留当前主机必要的 Python 环境处理。正式打包前执行 installclean；检查最终镜像内库和可执行文件确实对应新构建，防止 relink stamp 残留。记录源码版本、补丁哈希、构建配置、日志和产物 SHA-256；MD5 可用于与历史记录对照。

可复用现有 `tests/devicefix_regression.py`、`scripts/verify_source_recovery.py`、`scripts/verify_devicefix.py` 的机制，但其中绑定 OS4 属性或固定产物的断言应转为 profile 驱动，不能把删除断言当作完成兼容。

每个版本、每项功能的报告至少包含：**适配状态、证据等级、用例和结果、使用前提、失败表现、剩余边界**。建议交付：

1. 整理后的设备树、平台补丁、固定的构建基线与一键构建脚本。
2. `recovery-dijun-unified.img`（最终目标名；当前阶段产物为 `recovery-dijun-unified-recording-close.img`，完整功能验收未结束）及 SHA-256、尺寸与 ramdisk 内容清单。
3. `firmware-inventory.json`：六份样本的来源、提取结果、组件指纹和兼容类别。
4. `compatibility-matrix.md`：每版每功能状态，明确实际覆盖的 profile 和未知版本处理。
5. `simulation-report.md` 与机器可读结果：静态检查、状态机、文件镜像、异常和回归证据。
6. `FEATURE-USAGE.md`：逐功能入口、操作步骤、前提、预期结果、错误处理；标注操作是否已模拟。文档可以说明安装方式，本轮不执行实机安装。
7. `MAINTENANCE.md`：新增固件如何提取、比较、复用或新增 profile、重新构建与回归，以及如何从产物追溯源文件。

## 10. 最终验收清单

已勾选项仅限对应证据范围：启动脚本/服务调用使用主机替身，真实密钥操作保持 U；整体目标仍未完成。

- [x] 六个样本完成来源、包内版本及关键分区核对；未知项有明确记录。
- [x] OS3 两个样本与 OS4 当前样本进入同一镜像的离线验证矩阵。
- [ ] OS2 是否纳入同一镜像有完整技术结论；不以“Android 15 应该兼容”代替证据。
- [x] profile 选择在两槽位、未知版本、冲突身份和缺失资源情况下行为确定；不会跨 ABI 试装模块。
- [x] 解密组合、身份设置和服务顺序按版本验证；不伪造真实 TEE 解密结论。
- [ ] 第 5 节全部功能有实现状态、使用说明和验证结果，不遗漏 MTP、时间、震动及快速唤醒回归。
- [ ] 静态、主机模拟和最终镜像检查全部通过，或逐项给出可复核的限制；不存在未处理的基础启动级回归。
- [x] 设备树可从固定基线复现；清理安装输出后仍能生成一致功能和内容清单。
- [x] 单镜像容量满足所有已声明样本，依赖目标系统资源的功能写明前提。
- [ ] README 和报告只声明证据支持的范围；历史实机结果没有被套用于新版本。
- [x] 代理没有连接手机或执行实机/刷写命令，没有扩展到 AVB/vbmeta 工作。原始离线约束后，用户另行授权诊断指令并提供现场日志；这些用户观察单独记录，不等于代理实机验收。

最终成果名称使用“OS3/OS4 优先的多版本离线适配候选”。只有同一镜像的六份样本检查均完成时，才扩展为“覆盖所列 OS2/OS3/OS4 样本”；本轮不使用“全版本已实机验证”表述。

震动 DSP 配置接续新增两包正常/校准共 [36 项原始代码模拟](logs/haptics-config-emulation.json)：执行 MEM_RDY、CALL_RAM_INIT、写序列解析/写入、HALO 检查及 IRQ mask，最深到 GPIO 读取注入失败。CALL_RAM_INIT 连续写失败尝试 20 次，返回 -62；其成功后原厂立即设 `fw_loaded=1`，之后序列读取/写入、HALO、IRQ 或 GPIO 失败仍保留 1，因此此标志不能作为配置完成或可震动的证据。序列为全 FF 立即结束的显式合成数据，PM/HALO/IRQ 状态及邮箱确认均为夹具，没有执行 DSP。生产树和当前镜像未改；触摸 P0、震动和全部 12 组未完成项保留。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/haptics-config-delivery-audit.log)。

六份 OS2/OS3/OS4 固件包的[跨版本字节审计](logs/haptics-firmware-cross-version-audit.json)显示，七个 ODM 固件/参数文件的提取字节跨六版本一致，样本内 ODM/vendor 42 对关系逐一记录；独立[核验](logs/haptics-firmware-cross-version-audit-verification.json)及统一交付审计均检查来源哈希。它排除了所检查样本之间这七个文件存在版本字节差异的假设，不证明运行时加载或 DSP 接受。当前最大缺口仍是 OS2/OS3 从成功 firmware request 到同一原始 probe 的 DSP/input/start/IRQ 接续；OS4 的配置模拟使用合成 sequence/register 状态且全部故意终止，未执行 DSP。震动仍未修复，生产树和镜像未改。

触摸 P0 继续：新增两包 [32 项原始 flash 失败/后台接续](logs/touch-flash-failure-emulation.json)。原始块检查、擦除命令、首两段编程命令及复位实际执行，命令页范围/地址/固件字节逐项核对；传输响应与 flash 几何为夹具，全部场景以注入错误结束，没有真实写入或完整编程成功。更新失败仍清 pending 并通知完成；后台三次擦除失败后仍注册 input，缺配置时即使复位回 application 也没有坐标。已有配置可解析明确提供的合成报文，并不证明 bootloader 会真实发报告。两版一致，当前故障根因未定。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-flash-failure-delivery-audit.log)。生产树和当前镜像未改，触摸、震动及整体 12 组目标保持进行中。

触摸完整命令接续：两包新增 [26 项原厂完整编程/复位/后台配置模拟](logs/touch-flash-complete-emulation.json)，逐项核对全部 625 段编程请求与两条擦除命令，配置单独更新为 25 段。所有传输确认/boot-info/复位及配置响应均为显式夹具，未执行物理写入。原厂 update 可在 reset 响应仍为 bootloader 时返回 0，随后后台仍注册 input、配置为零且无事件；app 模式下配置获取超时/空配置也无坐标。成功重取配置可恢复合成 ISR，末段写失败后重试则核对 1250 段。测试预期曾错误假设 bootloader 会主动切回 app，已按原始分支纠正；不是生产修复。详见[范围](docs/OS4-TOUCH-FAILURE.md)与[交付审计](logs/touch-flash-complete-delivery-audit.log)。当前镜像未改，触摸 P0、震动及整体目标继续进行中。

震动 probe 接续新增两包 [16 项原始启动链模拟](logs/haptics-probe-upload-emulation.json)：清空设备上下文后由原始 DT 解析、供电/复位、PLL 与芯片识别接入实际固件/参数上传和配置，完整核对 68 次 raw write；最深到 GPIO、boost DCM/IPK 后的 `0x3804` 读取注入失败。所有错误均传播到 probe 并进入 remove 边界，未到 input 初始化；后期错误时 `fw_loaded=1` 仍存在，不能当作 probe 成功。原始合并 DT 属性有来源绑定，电源/寄存器/邮箱/序列与 remove 内部清理仍为夹具；完整 DSP、IRQ、电机和 OS2/OS3 此层接续待继续。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-probe-upload-delivery-audit.log)。生产与当前镜像未改，触摸 P0 和完整 12 组目标继续保留。


触摸 IRQ/PM 续接：新增两包 [40 项原始 IRQ 开关/PM/ISR 模拟](logs/touch-irq-emulation.json)。pending 持续时关闭 IRQ 请求 150×20 ms 等待后仍继续关闭；提前清除分别只请求 1/3 次。开启标志为 1 时可跳过非零 depth；wake 设置失败后软件 wake 标志仍改变。原始 PM 回调仅改变标志/通知 completion，所测 PM 标志与 sensorhub=1 都不阻断合成 ISR 坐标。所有 depth、wake、等待与报文为显式夹具；不等于测得 3 秒硬件延迟或定位当前根因。只有命名的 depth 不变场景允许有限执行预算耗尽，其他超限失败。详见[范围](docs/OS4-TOUCH-FAILURE.md)与[交付审计](logs/touch-irq-delivery-audit.log)。当前生产/镜像未改，触摸 P0、震动和整体 12 组工作继续进行中。


显示恢复续接：两包新增 [48 项原始显示 suspend/resume 模拟](logs/touch-display-resume-emulation.json)，接续原始 sensing/sleep/dynamic、IRQ、应用信息/配置与 parser/ISR。配置超时/空配置、应用信息三次失败、bootloader、复位事件失败、normal sensing 四次耗尽后仍可能设置 active；再次 resume 直接返回 0、不补配置，合成 ISR 无坐标。配置超时消失后，新的 suspend→resume 周期可重新取配置并恢复合成坐标。报告切换失败可被 resume=0 掩盖，不能用注入的坐标证明控制器接受模式切换。pending 关闭在显示入口只请求 3×20 ms，区别于独立 IRQ 接口的 150 次。所有电源/复位/命令响应/IRQ/温度均为显式夹具，无真实显示通知调度或实测延迟。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-display-resume-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动与整体 12 组目标继续进行中。


显示通知包装接续：新增两包 [30 项原始 notifier→worker→Synaptics dispatch/display 恢复模拟](logs/touch-notifier-emulation.json)。包装 worker 在配置失败/供电失败/dispatch 禁用/回调缺失后仍清休眠标志，重复亮屏任务会被包装层跳过，前两类分别留下下层 active=1/0，不能只检查一层状态。配置失败配对仍可经新的休眠/亮屏周期恢复合成坐标。队列拒绝、非法/未注册 panel、空通知及无关事件均有断言。两个独立 ARM64 地址空间通过显式带类型 host callback 桥接，未模拟内核链接/并发；flush 仅接受已排空队列，不宣称快速通知不会丢失。详见[范围](docs/OS4-TOUCH-FAILURE.md)和[交付审计](logs/touch-notifier-delivery-audit.log)。两版一致，根因仍未确定，当前生产/镜像不变，触摸 P0、震动和整体 12 组任务保持进行中。


震动 boost 后配置：两包新增 [26 项原始 probe→上传→clip/DBC/noise/calibration/brownout 模拟](logs/haptics-postboost-emulation.json)。实际 DT 属性读取目的地址与阈值字段绑定，独立核对 `0x201c=0x3000`、合成高位保留后的 `0x6408=0xa549140c`、`0x6404=0x5a491909`；原始代码消费的 vbbr/vpbr 字段顺序保留，不根据名字交换生产参数。clip/欠压读写、四个高低半字写序列及第二 IRQ mask 读取失败都传播 -5 至 probe/remove，不执行 input，即使 fw_loaded=1。完整 68 次原厂固件/参数 raw write 核对通过；寄存器/PM/HALO/序列和服务仍为夹具，没有 DSP/IRQ/电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[交付审计](logs/haptics-postboost-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动和整体 12 组目标继续进行中，下一边界为 runtime PM/logger/ASP 配置。


震动 runtime PM/logger/ASP 接续：两包新增 [16 项原始 probe 故障模拟](logs/haptics-runtime-config-emulation.json)，核对 68 次原厂固件/参数 raw write，执行 PM setup/entry/error recovery/exit、logger 和 ASP。resume -5 的原始错误处理会 set-status(0) 并调用 PM exit；logger/ASP 读写/分配/写序列故障均传至 probe/remove，未到 input，fw_loaded=1 不能证明成功。COUNT/SOURCE 初始 0、PM 服务/定时器和序列等为显式夹具，没有 DSP/电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)与[交付审计](logs/haptics-runtime-config-delivery-audit.log)。生产/当前镜像未改，触摸 P0、震动和完整目标保留；后续为 B2 邮箱、波形计数及 probe/input 接续。


触摸 IC-mode 接续：两包新增 [22 项原始模式函数/通知恢复模拟](logs/touch-ic-mode-emulation.json)，移除整体 IC-mode 成功替身，核对模式 2 的 `0xc7 / 31 0a 00`。dispatch 返回显示 resume 的保存值，IC 命令超时/分配失败不向上传播；重复亮屏跳过回调。配置失败后该命令仍不补回报告配置，合成 ISR 无坐标。IC 函数遗留 x0 不作为成功返回，控制器响应/IRQ/调度仍是夹具。详见[范围](docs/OS4-TOUCH-FAILURE.md)、[审计](logs/touch-ic-mode-delivery-audit.log)。没有根因或硬件恢复结论，生产及当前镜像不变，触摸 P0、震动和全部 12 组继续进行中。


震动波形/IRQ/input 接续：两包新增 [26 项原始 probe 模拟](logs/haptics-wave-irq-emulation.json)，从 B2 mailbox/波形诊断推进到 27 次 IRQ 请求、input/FF 回调与 sysfs 初始化、MFD 故障。计数读失败两次各重试 20 次，诊断错误未阻断后续 IRQ；B2/播放配置/IRQ/input 失败则传回 probe。input init 成功置注册标志后 MFD 失败，probe 仍失败。内核 IRQ/input/FF、合成计数 5/0、PM/HALO/mailbox 与序列均为明确夹具，全部场景以注入错误结束，没有完整 probe/DSP/电机成功结论。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[审计](logs/haptics-wave-irq-delivery-audit.log)。生产和镜像不变；后续接 probe 自带 upload/play/erase 自检，触摸 P0、震动与全部 12 组目标保留。


震动 probe 自检接续：两包新增 [16 项原始 probe→上传/启动/擦除 worker 模拟](logs/haptics-probe-selftest-emulation.json)。原始 ordered 队列标志 0x20012/max_active1 与顺序模型核对，非法逆序被拒绝；七条执行场景/包实际到 probe 返回。PM、启动写入、mailbox 和上传参数失败均可被最终 probe=0 掩盖，erase PM 失败还留下效果链表。寄存器/PM/IRQ/input/mailbox 仍为明确夹具，没有 DSP/完成中断或电机成功结论。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[审计](logs/haptics-probe-selftest-delivery-audit.log)。生产与镜像不变；继续 IRQ/完成链、旧版初始化和完整 GUI，触摸 P0、震动及全部 12 组目标保留。


非空通知队列与震动 IRQ 续接：新增两包 [16 项原始触摸 pending-work flush](logs/touch-pending-flush-emulation.json)和 [30 项原始 mailbox IRQ/状态/完成调用](logs/haptics-irq-completion-emulation.json)。触摸在原 notifier 的 flush 边界保存上下文，执行旧 worker 后继续排新任务；正常顺序不丢转换，配置失败后重复亮屏仍跳过下层、cfg=0，新的 off/on 才可恢复合成坐标。震动从实际注册 handler 接入可变合成环，核对 ACK 回绕、GPIO 触发/完成区别、锁门控及 complete 调用；读写失败仍可返回 IRQ_HANDLED。真实调度/物理 IRQ、内核 completion 等待和 DSP/电机仍未验证，不能据此认定当前实机根因或功能已修复。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)、[震动记录](docs/HAPTICS-FIRMWARE-EMULATION.md)及[交付审计](logs/pending-flush-irq-delivery-audit.log)。生产与 `recovery-dijun-unified-module-state.img` 未改，没有重编译；触摸 P0、震动和全部 12 组目标保持进行中。


触摸跨模块注册续接：新增两包共 [16 项原始 DT/panel/connect/后台→Xiaomi panel/input 注册](logs/touch-joined-registration-emulation.json)。参数直接来自原始 Synaptics setup，双 ARM64 空间显式桥接；callback 表和内核 input 服务仍为夹具。正常分支核对原始轴/slots 与合成 ISR；input 分配/注册失败则 wrapper 返回空，两版 Synaptics 均先写 input+0x2c0、后检查空指针，模拟捕获精确未映射写并终止，不继续 ISR。此为原厂错误路径证据，尚未绑定此次用户故障，不改写原厂模块。panel 队列失败不阻断后台独立 input 注册，配置超时则即使注册成功仍无合成坐标。详见[触摸记录](docs/OS4-TOUCH-FAILURE.md)、[交付审计](logs/touch-joined-registration-delivery-audit.log)。生产与当前 `recovery-dijun-unified-module-state.img` 不变，触摸 P0、震动和整体 12 组目标保持进行中。


震动主动擦除/完成等待续接：新增两包共 [30 项原始 probe→生产 FF 上传/播放→mailbox IRQ→erase 等待](logs/haptics-active-erase-emulation.json)。生产效果为 80 ms/8 ms/64，原始写入独立核对。正确 done 通过原始 handler 解除等待；停止消息通知不同 completion，读/ACK 错误或缺完成则请求 580 ms 后返回 -62、保留效果。超时后迟到 done 可再次 erase 释放；新 start 清除先前 complete_all，第二效果缺 done 仍超时。无启动 IRQ或启动命令失败时 erase=0 也不能证明播放发生。单等待者 completion/HZ/顺序调度是显式模型，上游 completion 源码仅作契约参照，物理 IRQ/DSP/电机未验证。详见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)、[交付审计](logs/haptics-active-erase-delivery-audit.log)。生产和当前 `recovery-dijun-unified-module-state.img` 未改，没有重编译；触摸 P0、震动及全部 12 组目标保持进行中。


震动 regmap IRQ 前置回调新增两包 [12 项原始执行](logs/haptics-pre-irq-emulation.json)：probe 取得原始 chip 指针，确认仅注册 pre、post=null、27 子 IRQ；pre 实际执行 PM resume→`0x10004` 状态读→PM suspend。状态读错误/PM 错误返回 -5；状态 bit0=0 会日志后返回 0。上游 v6.18 regmap 参照在调用 pre 时忽略其返回值，故显式安排子 handler 验证 pre 错误不必然阻断 mailbox done；kernel dispatcher/status-mask/nested IRQ 未执行，不能推断本机实际中断链。见[范围](docs/HAPTICS-FIRMWARE-EMULATION.md)和[交付审计](logs/haptics-pre-irq-delivery-audit.log)。生产树和镜像未改；震动仍未解决，触摸 P0、全部 12 组保持进行中。

六版本震动 input 契约复核：重跑 `python3 tests/haptics_lifecycle_emulation.py` 得到 90 项 PASS；新增独立检查 `python3 scripts/audit_haptics_lifecycle_report.py` 逐一校验六个 profile、模块/模拟器来源哈希及原始 `cs40l26_input_init` 的 input 名称、PERIODIC/CUSTOM/SINE/GAIN 能力、96 槽和 callback。报告索引已去重并刷新。该证据没有执行真实 input core ioctl、节点权限、物理 IRQ/DSP 或电机；不表示震动已修复。本轮发现目标 unified 镜像及其来源档案当前不在 `imgs/built/`，因此全量 image delivery audit 无法完成；没有重建生产镜像。OS4 触摸故障仍待用户提供该次启动日志，P0 未解除。

OS4.0.4 现场日志到达：归档 日志包（历史路径 `imgs/built/1/os4-touch-20261112-000013.zip`，当前工作区缺失），SHA-256 `b113b4bb4a422bd79698d2b72fa4823c699d99e5da14d90755ab06be4362a4c8`。启动选择 `os4-stable`，runtime 报告模块阶段 complete 和 `haptics_input=registered`；`/proc/bus/input/devices` 的 sysfs 路径为 `/devices/platform/soc/ec100000.i2c/i2c-0/0-0043/input/input4`，`/dev/input/event4` 为 `root:input 0660`，getevent 明确列出 FF_PERIODIC、FF_SINE、FF_CUSTOM、FF_GAIN，Recovery 启动时先报告无设备，模块稍后出现后成功选中 event4，证明晚注册重探测有效。日志包的 dmesg 是启动后 624 秒取得且没有 CS40L26 错误行；IRQ 快照中主 IRQ 累计 4 次、mailbox 子 IRQ 累计 1 次，但没有振动前后差值。另已核对原厂 OS4 probe 自带 100 ms 上传/启动/擦除自检：主机执行原始自检路径会写 `0x2802134=100`、发 mailbox `0x01800081` 后擦除；现场 mailbox IRQ 计数可能来自该自检，但快照没有时间相关性，不能据此认定。没有 GUI 振动请求的 FF 上传/播放返回码或硬件状态读数，因此只能确认输入后端已建立，实际 DSP/功放/执行器仍未知。此前“模块第 54 位可能耗尽 45 秒预算”的风险并非这次启动的解释：该次日志明确显示模块阶段 complete 且震动设备注册成功。OS4 触摸节点也已注册，但没有 `getevent -lt` 触摸样本或可视响应证据，触摸 P0 仍保留。下一采集只需围绕一次受控 GUI 振动触发前后记录 event4 FF 事件和 CS40 IRQ 计数差，并保留触发时间；避免重复拉整包启动日志。
现场解析器 [audit_haptics_runtime_observation.py](scripts/audit_haptics_runtime_observation.py) 和机器报告 [OS4 stable runtime observation](logs/os4-stable-haptics-runtime-observation.json) 已加入证据索引。Synaptics IRQ 快照值 3003 已登记为未关联累计值；输入节点存在不代表真实触摸事件。归档中的输入/模块/getevent/recovery/logcat/dmesg 与单独保存的 IRQ、live getevent 文件均记录哈希。ZIP 中的 `dijun-runtime.log` 为 UTF-16，解析器按 BOM 解码。


补充 recovery 震动执行检查点：原计划把可选 `xring_smartpa` / `xring_audio_hw_third` 排在第 51/54 位；runtime modules 阶段外层期限为 45 秒，因此前置 probe 阻塞时可能来不及尝试震动，也可能消耗触摸加载机会。生成器现保持已接受的原厂依赖边，在触摸硬依赖闭包完成后优先处理震动专属依赖闭包；六包计划顺序主机检查通过。runtime 另以 `twrp.profile.haptics_input=pending/registered/not_registered` 独立记录 `cs40l26_input` 名称，最长轮询 1 秒。主机回放验证模块 live 但没有 input、立即 input 和延迟 input；这不验证真实异步 I2C、input 权限、FF ioctl 能力或电机，也不归因触摸故障。OS2/OS3 为 `xring_smartpa`，OS4 为 `xring_audio_hw_third`。触摸 P0、震动及整体 12 组目标仍未解决。

settings-row构建后验证：同镜像profile回归9组/102次阶段调用通过，21项既有控件反馈检查通过；来源重建73+1+3文件一致、0待更新。公共行20项输入检查及保存21/路径31回归作为不同边界证据保留。未确认实际触摸冷启动、设置保存或物理震动，完整目标仍进行中。

震动现场 A1 接续：两份 OS4 共 16 项原始 probe→固件/配置→自检→生产 FF/IRQ/erase 检查通过。A1 原始 ROM 与 B2 不同，加载后 PM 状态需显式转换；过时状态、errata 序列/Q/固件写错误均阻止进入 input。A1 在同一上下文写默认 Q=0，仍不能推导静音；生产80ms/8ms/64请求在显式完成消息下擦除成功，缺 done 则580ms请求后-62。内核/PM/寄存器/邮箱/全FF序列/DSP仍有明确模拟边界，没有电机恢复结论。见[结果](logs/haptics-A1-joined-review.json)、[范围](docs/HAPTICS-ADAPTATION.md)。生产 settings-row 镜像未改，震动与完整12组继续进行中。

挂载模式确定修正：补丁0034把system/vendor切换改为操作锁内的检查/卸载/修改/重新挂载/失败恢复流程；检查两个目标的挂载返回值，全部成功才提交全局模式，保留回滚失败日志和实际未恢复状态。15项生产函数主机检查通过，旧实现同组8项失败。installclean后30并发新候选recovery-dijun-unified-mount-mode.img，SHA256 `848096d4b42b41926e2741ba4a34ef1ec4922aaa66036281724e7a2d65b652f1`，717来源及封装/新二进制核对通过。详见[范围](docs/MOUNT-MODE-ADAPTATION.md)。不是震动或一般设置故障修复结论；全部12组保持进行中。

mount-mode构建后验证：同镜像9组/102次profile阶段调用通过，717来源及新二进制核对完成；GUI/FF库字节与settings-row一致，生产挂载事务15项通过，旧实现同组8失败。未验证实际挂载/界面/震动，目标仍进行中。

震动FF core边界补齐：16项上游6.18原函数→原厂A1停止/擦除接续确认EVIOCRMFF先stop0，只有stop确认不能代替播放done，缺done可-62；flush忽略该错误仍返回0。随后现场43次stop/erase独立配对全部erase_ret0（最大10.491ms），因此该模拟风险不能解释已有无震动现场。上游不是本机vendor源码，PM/寄存器/队列/DSP仍有明确边界；不改生产，当前mount-mode候选保持不变。见[结果](logs/haptics-ff-core-review.json)、[现场](logs/haptics-erase-field-observation.json)、[范围](docs/HAPTICS-ADAPTATION.md)。震动/完整12组继续进行中。

震动六版本供电引用核实：原始DTB+overlay5重新合并并核对，VA均mldo8→常开mbuck10，reset为低有效GPIO_105，IRQ为GPIO_046/低电平。六个原厂模块supplies均VP/VA，但DT只声明VA，与现场VP dummy警告相符；不等于物理缺电或应添加VP。两份OS4提取init相关命令除通用LED trigger外没有Cirrus输出write，二进制服务/实际供电未覆盖。见[拓扑](logs/haptics-power-topology.json)及[范围](docs/HAPTICS-ADAPTATION.md)。不改生产/不重编译，震动与完整12组继续未完成。

同镜像验证收尾：9组/102次profile阶段调用通过，718份构建来源仍一致，设置交互20/保存21/路径31与挂载模式15回归通过；当前交付审计见 `logs/otg-selection-delivery.json`。硬件与完整12组验收仍未完成。

震动校准恢复接续：新增[14项原厂服务→同一probe后A1/B2 sysfs store检查](logs/haptics-restore-joined-review.json)。A1接受合成z/f0/q，真实系数地址依次0x280212c/0x2802128/0x2802150；B2拒绝Q。越界F0、PM失败或Q写失败传回stdio错误，原服务仍继续，不能以恢复函数结束认定就绪。有效合成值恢复后生产SINE依然提交20/125/64并在显式done下擦除；这不是DSP/电机或校准必要性的证明。本机persist值与寄存器读回仍未知，未向生产加入未经现场值核对的恢复或校准。生产otg-selection候选不变、无需重编译；震动及完整12组保持进行中。

震动原厂波形核实：新增[10项WMDR波形表/原始parser/CUSTOM请求检查](logs/haptics-stock-wave-review.json)。从原厂cs40l26.bin独立解码43条记录，与同一A1 probe的原始解析输出逐条核对类型、flags、offset、length和数据SHA。原厂long_vib_id31对应type12、offset1916、length7words，数据SHA `a7a957218ddc595e63d4dc8097d5b7aa0b92f72f96104307a1d8bb4f41d4704e`。以文件解析数量43作为显式regmap读边界，原始CUSTOM31/42 worker成功，43越界-22、空表-61、20次读取失败最终-62。排除所查OS4参数包缺波形31的疑点；不证明DSP加载/电机输出，也不据此把生产SINE换成CUSTOM。当前otg-selection镜像未改，震动及完整12组仍进行中。

CPU温度身份核实：新增[六版本原厂DT/驱动注册证据](logs/thermal-topology.json)。匹配base+overlay5合并后，cpu-crg均引用已启用的tsensor@EB008000通道0，同控制器22个物理传感器、整树38个thermal区域。原始模块通过devm_thermal_of_zone_register注册；通道0不等于Linux thermal_zone0编号，当前固定路径仍未获运行时身份验证。GUI2没有温度字段，后续应按type=cpu-crg匹配并补显示、缺值/晚注册/编号变化检查。此为静态证据，无生产修改/重编译；震动与完整12组目标继续未完成。

thermal-identity构建后收尾：同镜像9组/102阶段profile回放通过，719来源保持一致；当前交付审计见 `logs/thermal-identity-delivery.json`。GUI和FF库与otg-selection一致，温度界面/物理震动/完整目标仍未完成。

设置问题再次报告：优先暂停温度GUI新增工作，复核当前设置点击20项、保存21项、路径31断言均通过，不能代替本次现场结论。采集工具增加运行二进制摘要、输入/raw状态及进程映射，以一次“交换导航按钮”操作前后日志定位事件/保存边界。此次无生产修改、无新镜像，设置故障待对应现场证据；触摸P0、震动和完整12组目标仍进行中。

temperature-ui构建后收尾：同镜像9组/102阶段profile回放通过；723来源/维护补丁76+1+3文件重建一致、0待更新。当前交付审计 `logs/temperature-ui-delivery.json`；硬件温度/震动及设置现场仍未完成，完整12组保持进行中。

震动OS2/OS3真实系数续接：新增[60项原始解析器→系数查找→FF上传检查](logs/haptics-legacy-firmware-join.json)。四份OS2/OS3的normal/calib固件均用原始parser解析实际字节；独立packed算法表供给regmap读取。normal固件接同一上下文的原始upload callback/worker，撤掉cl_dsp_get_coeff替身，80ms/8ms/64请求解析到0x280701c/14/18并写20/125/64，与OS4一致。首/次/三项写失败均停止并传-5，缺首项名称原始查找传-14；头错误/固件写错误不产生完整系数，table读失败仍保留解析metadata但返回-5。parser-only也能建立软件系数且不写固件，不能据此推断DSP已加载。此举补齐旧版“模拟系数地址”边界，没有执行完整probe/参数加载、真实PM/input/workqueue/start/IRQ/DSP或电机；不把结果解释为震动恢复。生产temperature-ui候选与FF库未改，无需重编译，全部12组继续进行中。

震动OS2/OS3参数加载续接：新增[48项原始wavetable创建/固件解析/参数loader和parser接续](logs/haptics-legacy-parameters-join.json)，四版normal均请求5文件/34次参数raw写，calib请求4文件/28次写。逐文件记录原始parser返回，独立解码WMDR核对全部地址/长度/数据SHA。主文件缺失、头错误(-22)、首写错误(-5)及SVC首写错误(-5)均警告后继续，loader最终仍返回0；首分配失败才返回-12。calib模式用原厂参数会有三条revision警告但接受对应区域，不能把警告当作全包拒绝。参数写仅被记录，未使DSP运行，亦未连通完整probe/config/start/IRQ；loader0不是参数完整或电机输出的证明。没有证据将该故障机制对应到用户当前OS4无震动，不改原厂模块或生产请求。temperature-ui镜像未改，全部12组保持进行中。

settings-retry交付收尾：新镜像内脚本回放9组/102次阶段调用通过；724来源及维护补丁76+1+3文件重建一致、0待更新。已有控件反馈21项通过，FF库与temperature-ui一致。交付审计见logs/settings-retry-delivery.json；设置现场、物理震动及完整12组仍未完成。

MTP日期交付收尾：同镜像9组/102次阶段回放通过，725来源及76+1+3维护文件重建一致、0待更新；新镜像仅MTP库字节改变，GUI/FF库与settings-retry一致。当前审计logs/mtp-datetime-delivery.json。物理震动未解决，设置现场原因未确认，全部12组保持进行中。


请求诊断候选交付收尾：同镜像六版本双槽回放9组/102次阶段调用通过，726份构建来源保持一致，维护文件重建76+1+3且0待更新。14项日志与ABI、24项路由、4项后台FF、16项owner检查通过；交付审计入口`python3 scripts/audit_haptics_request_trace_delivery.py`，结果`logs/haptics-request-trace-delivery.json`。这是诊断候选，未确认触摸、现场设置保存或物理震动恢复，完整12组继续进行中。


2026-11-12 设置完整保存链路续查：新增tests/settings_joined_test.py/.cpp，在私有chroot保留真实/mnt/vendor/persist/TWRP路径，执行真实LVGL文字点击/公共行/取消guard/general回调→twrp_settings_store→DataManager Get/Set/Flush/Save→分区lookup/mount入口→InfoManager文件保存与重新加载。checkbox/switch各11场景，共22项通过；只换回HEAD旧partitionmanager方法同22项均失败。已有挂载/保存时挂载、拒绝挂载、ENOSPC、短写、只读、rename失败、目录fsync失败、BackingFile未初始化、常量键拒绝、其他字段超长均覆盖，并在故障解除后再次点击验证重试。目录fsync失败会出现磁盘新值已发布但UI/内存回退，不声称磁盘回滚。底层Mount/IsMounted、属性/元数据、页面导航/电机为显式替身，不是完整Recovery或现场persist；不推导用户设置已恢复。无生产修改或新构建，当前610f4acc诊断候选不变，震动/设置现场和完整12组继续进行中。复现python3 tests/settings_joined_test.py；审核python3 scripts/audit_settings_joined.py，范围详见docs/SETTINGS-ADAPTATION.md。


MTP原子上传交付收尾：同镜像六版本双槽9组/102次阶段调用通过，727来源保持一致、维护文件76+1+3重建且0待更新；与610f4acc候选仅MTP库字节改变。当前审计logs/mtp-atomic-delivery.json。进程退出临时残留、目标断电/USB和完整调用链仍未完成，震动与现场设置尚未解决，完整12组继续进行中。


时区回退交付收尾：同镜像六版本双槽9组/102次阶段调用通过；731来源、维护文件79+1+3重建一致且0待更新。当前审计logs/timezone-retry-delivery.json。MTP与FF库字节保持上一候选一致，物理无震动、现场设置原因及完整12组仍未完成。


FF查询中断交付收尾：同镜像六版本双槽9组/102次阶段调用通过，732来源、维护文件79+1+3重建一致且0待更新；与f31bbe13候选只有FF库字节改变。28路由/6后台FF/14日志ABI及旧查询2失败对照完成，当前审计logs/haptics-probe-delivery.json。没有实机查询中断或电机恢复证据，物理无震动、现场设置及完整12组仍未完成。
