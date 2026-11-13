# 多用户发现与解锁入口

<a id="slot-unmount"></a>
## 槽位切换前的 Vendor 卸载失败

0102补齐Vendor普通卸载失败后的MNT_DETACH结果检查。两者都失败时operation_end(1)并返回false，不进入SetActiveSlot；备份页和重启确认页沿用0101的错误处理。保留现有延迟卸载成功后继续行为；没有Vendor分区时也继续。延迟卸载并不证明旧引用已全部释放，本次未添加这种声明。

现有tests/slot_result_test.py扩展到21场景：新增后台 / 备份 / 重启三处延迟卸载成功与失败，以及无Vendor路径。当前21项通过；保存的0101后台同夹具三个双卸载失败场景失败。原核心和回调执行，HAL / 卸载 / DataManager / 导航是替身，没有真实设备操作。报告本地logs/slot-unmount.json、logs/slot-unmount-negative.json；交付审计logs/slot-unmount-delivery-audit.json。既有报告不覆写，其哈希继续绑定历史执行。

<a id="slot-result"></a>
## 槽位失败传播

0101修正SetActiveSlot的结果契约：非法槽位、缺失Boot HAL或HAL拒绝返回false；这些路径不发布tw_active_slot、不改active_slot_display_，也不刷新分区详情。启动时从空槽位初始化显示保留原行为，不调用HAL；已选相同槽位直接成功。后台先检查槽位能力，再将核心结果传递给operation_end与调用者。

备份选项页检查返回值：失败记录已有unable_set_boot_slot本地化消息并保留当前页面和输入；重启确认页原有失败分支现在能收到核心失败，保持待切换并显示错误，不请求重启。没有新建UI消息或绕过backend。

tests/slot_result_test.py执行原核心、后台和两个GUI回调14场景：成功、相同槽位、初始显示、非法槽位、无服务、HAL拒绝、无能力及页面失败/成功路径。旧实现9项失败；当前14项、入口锁21项、侧载20项通过。HAL/capability/DataManager/挂载/导航是替身，不是实际Boot HAL或渲染GUI验收；失败前的vendor卸载不回滚。交付审计本地logs/slot-result-delivery-audit.json。此缺陷收尾，不重复上述检查。

<a id="storage-reboot-guard"></a>
## 存储忙时的重启与槽位入口

离开解密页后，provider 仍可能处于同步调用中并持有存储事务锁；原重启 / 槽位入口没有检查这把锁。补丁0100对两个入口使用非阻塞try-lock：其他线程持锁时返回false，不阻塞界面，不执行sync、参数写入、vendor卸载或槽位修改。侧载重启交接先取得同一递归锁，再领取待处理动作，避免忙时消耗请求；空闲后下一次GUI轮询继续处理。

`tests/reboot_storage_test.py`用原backend方法、真实递归锁和持锁线程执行21项检查；旧实现同夹具9项忙时检查失败，12项空闲 / 控制通过。`tests/sideload_reboot_test.py`原核心 / 私有进程 / 原轮询20项通过，新增忙时保留→释放锁→下一轮交接场景。HAL / 分区 / DataManager / USB / sync和最终重启是替身；没有操作设备或执行真实TEE调用。交付审计为本地`logs/reboot-storage-delivery-audit.json`。

此修改只提供入口冲突保护。不会中断已经进入Binder / TEE的调用；也未在request_reboot返回到最终Reboot之间保留停止新任务的预约。安全取消、完整关闭串行化、父资料协议及真实CE驱逐仍未完成，不因本次检查通过关闭整组目标。必要检查通过后不重复该项。



2026-11-12 CE失败与缓存接续（0050）：已经独立选择用户，不代表provider失败时未安装过密钥。原始vold Decrypt_CE_storage顺序为unlock→prepare；前一步成功、后一步失败会返回false，但s_ce_policies仍有该用户。原始fscrypt_unlock_ce_storage遇已有policy会直接返回true，不重新读取凭据或安装。Recovery现只在该次provider返回false时请求fscrypt_lock_ce_storage(user_id)，不发布解密成功；驱逐失败记录用户ID与固定错误信息，不输出凭据，也不伪装硬件清理成功。

`python3 tests/ce_lifecycle_test.py`接续原始DecryptDevice、MarkUserDecrypted、CheckUsersDecryptionStatus、MarkDataLocked、Decrypt_CE_storage、fscrypt_unlock_ce_storage、fscrypt_lock_ce_storage、evict_user_keys。15场景覆盖用户0/10成功、错误secret、安装失败、prepare失败后的清理/错凭据再试/正确重新安装、用户隔离、已有cache、全部锁定后单用户再解锁、adoptable卷驱逐、驱逐失败诊断、已解锁用户、缺失用户、DE失败与crypto未就绪。全部原始方法从实际checkout原样提取；属性/DE准备/凭据派生与认证/密钥读取/安装及驱逐ioctl/用户目录准备/挂载是显式夹具，未使用实际密码或密钥。缓存和原始控制流执行不等于真实fscrypt内核挂载试验，更不等于父绑定工作资料协议。

15项当前通过；保存的原始partitionmanager在同组有3断言失败（owner/secondary prepare失败留cache、失败驱逐路径），无超时计作缺陷。用户枚举/控制18项回归通过，真实tinyxml2/ABX代码仍执行。原始vold的evict_user_keys即使evict回调失败也会移除缓存，因此测试不能从“缓存消失”推出内核密钥已移除；prepare失败日志明确保留这个边界。MarkDataLocked已有行为未在本轮更改，旧实现与当前均通过其锁定/再解锁夹具。

维护系列新固定`system/vold`基线e7e26ed2ffd9ad0469a05515cfd91940a3366d19，并记录FsCrypt.cpp、Decrypt.cpp、Android.bp原始摘要；Recovery的静态libvold链接关系也纳入测试/审计来源。这是证据补齐，没有修改vold的密钥格式、派生参数或父资料协议。

2026-11-12 多用户CE失败收尾修正：原始Decrypt_CE_storage先安装CE后prepare，prepare失败可留s_ce_policies；补丁0050在Recovery的provider失败出口请求驱逐本次用户，失败记录诊断，其他用户隔离。原始Recovery/vold八个方法接续15场景通过，旧实现同组3断言失败；用户枚举/控制18项回归通过。失败后错误secret仍失败、正确secret重新read/install；原始MarkDataLocked→lock/evict→再解锁及adoptable清理均执行，install/evict ioctl和prepare/mount仍是夹具，不等于物理已锁。vold基线e7e26ed2及FsCrypt/Decrypt/Android.bp纳入维护来源记录，未改其密钥协议。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-ce-cleanup.img`，SHA256 `9861830824b5a34bb5782bdbd6704bbc7c4b33374e20fe0fb87ffa23fae498cf`，746来源/六配置封装通过；同镜像回放和定向审计见logs/ce-lifecycle-delivery.json。父绑定工作资料协议、同步Binder安全中止和真实CE重挂载继续未完成；完整12组目标保持进行中，未操作设备。

回归/交付审计：`python3 tests/multiuser_core_test.py --report logs/ce-lifecycle-multiuser-core.json`、`python3 scripts/audit_ce_lifecycle_delivery.py`。Windows/实机、原始child_profile_lock/Keystore父绑定协议、同步调用安全取消仍未执行。用户0成功后的MTP发布与次用户不改变内部存储根目录的现有规则保留。

---

下文是初始0011检查点，历史产物名及证据不自动转为当前镜像验收。


此前维护树写有 `TW_SKIP_SECONDARY_FBE_USERS := true`，但固定的 recovery/vold 源码没有使用这一变量。
实际 GUI `select_user()` 固定选择用户 0；删除未使用的变量本身不能实现次用户支持。
当前补丁 `0011-multiuser-discovery-and-selection.patch` 同时修改用户发现、后台选择和界面路由。

## 当前实现

- 从 `/data/misc/vold/user_keys/de/<id>` 的实际目录枚举用户，并要求 vold 在安装 DE 密钥后发布的 `twrp.user.<id>.decrypt` 为 `0` 或 `1`。
- 保留底层库支持的 ID 范围 0–9999；拒绝别名数字、符号链接和非法状态。按 ID 排序，每次替换快照，避免重复和已删除用户残留。
- `/data/system/users/<id>.xml` 只提供显示名称；缺失或损坏时显示数字 ID，不隐藏有 DE 状态的用户。
- 用户 XML 使用固定版本的 tinyxml2 解析，避免原 rapidxml 错误处理直接 abort。支持既有 ABX 转换，释放转换临时文件；限制资料大小和名称长度。
- “挂载 → 解密 Data”在仍有锁定用户时保留入口。存在次用户时先显示用户列表；每个用户显示独立锁定状态，已解锁项不可重复点击。
- 选择用户后显示其名称与相应 PIN、图案、密码输入方式；无锁类型沿用原来的默认凭据尝试。启动阶段仍优先处理用户 0。
- 后台线程在启动时捕获用户 ID 和凭据，拒绝处理中切换用户或重复请求。密码不放入全局 DataManager 属性。
- 次用户成功只更新其 CE 状态；不会执行用户 0 的 PostDecrypt、改变内部存储根目录或发布“全部用户已解锁”。失败保持原锁定状态。
- 用户列表读取采用存储事务锁的非阻塞尝试，避免界面等待正在进行的解密事务。

显示名称不能用来判断用户是不是工作资料或应用分身；界面按实际 ID 操作。
没有新增“将用户 0 凭据自动套给其他用户”的行为，也没有改动真实凭据、密钥或 Android 用户配置。

## 离线证据

| 检查 | 结果与范围 |
|---|---|
| 核心枚举/解锁控制 | [18 组通过](../logs/multiuser-core.json)：真实 ParseUsers、MarkUserDecrypted、DecryptDevice 分支；临时目录、属性和 CE provider 替身 |
| 修改前回归 | [原实现 10 组未通过](../logs/multiuser-core-before.json)：重复/缺失资料/陈旧记录、顺序、损坏 XML/ABX、转换文件清理、非法身份；原本正确的凭据失败和逐用户隔离用例保留通过 |
| 状态变化回归 | [修改前失败](../logs/multiuser-backend-before-mode-fix.log)，修改后通过：选择次用户后全局 FBE 标志变化也不能回退到用户 0 |
| 实际解析代码 | 使用 checkout 的 tinyxml2 和 `abx.cpp`；包含有效 ABX 往返与损坏输入，不以伪造解析结果替代 |
| 后台线程 | [12 类通过](../logs/multiuser-backend.json)：真实后台线程、身份捕获、忙状态、存储锁、模式变化不重定向、失败、用户 0/次用户隔离和刷新 |
| 界面路由 | [8 类通过](../logs/multiuser-routes.json)：执行真实选择回调；导航和 LVGL 边界替身；另检查挂载入口及成功返回用户列表的连接 |
| 四语言 | [校验通过](../logs/multiuser-i18n.log)：语言字段一致，原有 239 条控制台消息格式签名保留 |

以上 S2 不执行真正的 MiTEE、Gatekeeper 或 fscrypt 解锁。界面路由测试不验证字体、布局或触摸命中区域；完整源码编译与镜像检查另外记录为 S3。

## 使用范围与剩余工作

通过挂载页面进入“解密 Data”，选择锁定用户，输入该用户所需凭据。成功后返回用户列表查看各自状态。
用户 0 的内部存储入口仍为原路径；次用户数据可在其实际存在且已解锁的 `/data/user/<id>`、`/data/media/<id>` 等路径访问。
备份仍受未解锁用户排除规则限制，不能把用户 0 解锁后的备份当作所有用户完整备份。

工作资料绑定父用户的统一凭据、应用分身密钥、Keystore synthetic-password/child-profile 协议与真实 TEE 调用尚未证明。
当前仅提供独立选择和调用已有 provider 的路径，不能宣称任意工作资料都能用主用户密码打开。

已验证服务缺失的启动就绪期限和请求拒绝。**进入原厂同步密钥调用后，仍缺少可安全中止的完整期限机制**；
当前线程保持运行，界面拒绝重入，而不是在调用尚未结束时伪造超时失败并启动另一请求。
真实工作资料解锁、重新挂载后的 CE 密钥行为、硬件调用卡住后的恢复及完整备份隔离仍属后续工作。

本项首个候选：[recovery-dijun-unified-multiuser.img](../imgs/built/recovery-dijun-unified-multiuser.img)。
[最终镜像检查](../imgs/built/recovery-dijun-unified-multiuser.json)与[635 份源码记录](../imgs/built/recovery-dijun-unified-multiuser-sources.json)对应同一镜像 SHA-256；五版本启动脚本模拟见[报告](../logs/multiuser-profile-runtime.json)。
最新统一产物以[总报告](../simulation-report.md)为准。
