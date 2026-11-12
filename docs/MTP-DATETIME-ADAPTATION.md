# MTP 上传日期解析


2026-11-12 文件上传时间接续修正（0049）：此前日期解析已能接受epoch0，但MtpServer仍用0作缺值哨兵，合法`19700101T000000Z`和等价偏移时间不会落盘。当前改用optional<time_t>记录是否有日期；空串/非法输入保持原来“使用新上传文件当前时间”的行为，有效0/-1都会调用futimens。接收失败不再尝试设置时间；时间应用失败后不发布临时文件，返回上传失败并保留旧目标。只处理文件上传，不宣称目录DateModified或DateCreated已适配。

原始server/database/packet/storage与私有真实文件链路增至94项（ASan/UBSan），新增16项为新建/覆盖各8项：epoch0、带偏移的epoch0、epoch-1、缺失、非法、futimens失败、接收失败、fsync失败。检查实际stat纳秒/秒、内容、数据库DateModified、旧目标保持、临时文件清除和下一次无日期上传；外层没有复写时间算法。接收失败用全部payload已进入初始缓冲的3字节输入，避免隐含“部分bulk失败后USB已排空”；其他日期场景用60000字节跨传输数据。缺日期/非法值不设置时间，有效零秒确实调用；fsync失败仍保留旧目标。旧实现16项有10失败，负一秒/缺失/非法各新建覆盖六项通过。主机文件系统与真实USB/Android挂载仍有边界。

首轮94项中两条receive-error随后重试因内存USB peer未丢弃剩余bulk字节而失败，保留logs/mtp-upload-time-first-attempt.json与before-first-attempt.json。未为了日期项扩大成真实端点排空/恢复实现，也没有把超时算成旧实现缺陷。调整后的旧10失败全部是明确断言，当前94项全部通过，移动复制48项回归通过。

入口：`python3 tests/mtp_objects_test.py --report logs/mtp-upload-time-objects.json`，`python3 tests/mtp_transfers_test.py --report logs/mtp-upload-time-transfers.json`；旧源码保留于`backups/mtp-upload-time-pre-fix/mtp`。定向来源/镜像审计为`python3 scripts/audit_mtp_upload_time_delivery.py`。完整MTP仍缺目录日期、媒体格式/属性、进程崩溃临时文件处理、真实USB残余数据与断电持久性证据。

2026-11-12 MTP文件上传时间修正：维护补丁0049将有效time_t（包括0和-1）与缺失/非法日期分开，接收失败后不尝试设置时间；futimens失败在rename发布前中止，保留原目标。真实server/database/私有文件链路94项通过，新增新建/覆盖各8项共16日期场景、旧实现同组10失败；移动复制48项通过。首次测试中部分bulk失败后重试暴露USB替身未排残余数据，保存logs/mtp-upload-time-first-attempt.json，不把该边界冒充完整端点恢复；该场景改为已完整读入payload后的接收失败。installclean及make -j$(nproc)30并发构建`recovery-dijun-unified-mtp-upload-time.img`，SHA256 `57798214bab0d211aa53e5036e46e45c528483aebb3cc16286da86406928484a`，742份来源/六配置封装通过；同镜像profile/module回放与定向审计见logs/mtp-upload-time-delivery.json。继承0048 OTG修正，列表证据仍明确绑定此前031497e5镜像；设置用户确认保留。目录日期、媒体完整元数据、临时文件崩溃残留、USB/断电和其余完整12组保持未完成，不以震动为当前主线。

---

以下为0039日期解析的历史检查点，其中epoch0未修正描述仅指当时。


MTP上传日期修正：维护补丁0039按MTP格式校验年月日/时分秒、单个小数位、Z和±HHMM，显式偏移转UTC不依赖Recovery时区；保留无偏移的本地时区/DST行为，拒绝归一化后的非法日期和不存在的本地时间，失败不改变调用者输出。实际MtpUtils+独立Python日期oracle80项通过，旧实现79项中48失败（旧版空指针另未执行）；生产server/database/文件上传46项及移动复制48项通过，含4项新日期落盘检查。主机libc/USB替身非手机RTC/Windows枚举。installclean后make -j$(nproc)30并发构建新候选recovery-dijun-unified-mtp-datetime.img，SHA256 `8c624d0e1a4b9bbff1b99ce83dbcce2c3cdfc3013c2270d65c04e075a8a81ee3`，725来源及封装/新二进制核对通过；同镜像profile另记。没有修正震动、修改校准或改变FF；原子上传覆盖/输出日期格式化/完整元数据等仍待完成，全部12组保持进行中。

原实现把除Z以外的日期全部交给mktime，所以`20261111T020953+0800`会随Recovery时区改变；sscanf还接受非法字符/尾缀与被libc自动归一化的日期。0039先校验完整输入，再转换与反向核对字段，显式偏移使用timegm后减去偏移，检查溢出。没有偏移继续使用本地mktime，DST空档因反向字段变化拒绝；DST回拨的重叠时间沿用libc选择，不承诺某一偏移。合法epoch-1不会仅因返回-1而被拒绝。

复现：

```bash
python3 tests/mtp_datetime_test.py --report logs/mtp-datetime.json
python3 tests/mtp_objects_test.py --report logs/mtp-datetime-objects.json
python3 tests/mtp_transfers_test.py --report logs/mtp-datetime-transfers.json
```

输入定义采用现有MTP注释的一位可选小数；小数不进入秒精度time_t。UTC偏移小时00..23、分钟00..59；年份0001..9999，不接收闰秒60。实际上传东/西偏移和带小数Z都落为1794334193秒；非法日期由现有doSendObjectInfo置modifiedTime=0，保持当前上传时间，不新增协议拒绝。未处理有效Unix零秒被同一调用者哨兵忽略的既有问题。

80项直接检查使用真实主机libc和编译后的整个MtpUtils，数据由Python datetime独立计算，不复写C++算法。46项链路使用实际server/database/packet和私有chroot实际文件/inotify/线程，USB和Android属性为替身，启用ASan/UBSan。48项转移回归单独保存。旧实现同组79项48失败；旧版sscanf无法安全接收null，因此baseline显式跳过该项，现版本80项含null拒绝。

本项没有实现原子上传提交、完整媒体格式和日期属性，formatDateTime仍使用本地无偏移字符串且未补失败处理；不能凭日期测试认定完整MTP目标完成。没有连接手机、刷机、改AVB或执行物理震动。

MTP日期交付收尾：同镜像9组/102次阶段回放通过，725来源及76+1+3维护文件重建一致、0待更新；新镜像仅MTP库字节改变，GUI/FF库与settings-retry一致。当前审计logs/mtp-datetime-delivery.json。物理震动未解决，设置现场原因未确认，全部12组保持进行中。
