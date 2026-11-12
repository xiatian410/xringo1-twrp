# 时区保存失败回退

时区保存失败回退：补丁0042在页面提交前保留五项旧值，部分写入/生成时区/flush失败时恢复选项和精确旧tw_time_zone，刷新旧环境，保留待选项供重试；检查时区/偏移索引边界。backend生成时区传回读写错误，回退不从GUI选项重建自定义时区。17项真实LVGL回调+实际adapter/libc检查通过，旧回调同组11项失败；保存链22/点击20/语言主题9/震动路由24/owner16回归通过。存储/属性/页面路由为夹具，目录fsync失败后的磁盘发布不构成回滚。installclean后make -j$(nproc)30并发构建recovery-dijun-unified-timezone-retry.img，SHA256 `f31bbe13f856d25c0080b26cac041366bb91c5f61b95f88f9f5136df83a47023`，731来源与封装核对通过，同镜像profile回归另记。不能以此解释所有设置失效，物理震动与完整12组仍未完成。

复现：

```bash
python3 tests/timezone_retry_test.py
python3 tests/timezone_retry_test.py --source backups/timezone-retry-pre-fix/gui2.cpp --output logs/timezone-retry-before.json
python3 scripts/audit_timezone_retry_delivery.py
```

17项分别为东八区/分钟偏移/美国冬季DST规则/西区成功，五个SetValue位置失败，flush失败与重试，时区/偏移上下界，错误事件和空store。旧回调不检查第五码入结果，或在失败时留下部分新值/已变化的TZ；越界通过UBSan检测。四项成功同时核对libc UTC偏移（冬季DST规则按日期生效）和保存夹具。

初始旧zone为CUSTOM-9:45，GUI选项仍美国中部；回退须保留这个精确zone，不能重建CST6。实际执行DataManager::UpdateTimezoneEnvironment，但Android属性接口为可控记录，未模拟属性写入失败。DataManager键/文件保存由map替身实现，本套不证明persist或断电行为；真实保存链22项是独立回归。rollback没有重复flush，不篡改已经rename的文件；恢复SetValue自身持续失败或并发修改仍不具事务保证。

旧版对照只替换gui2.cpp中的回调；adapter使用当前错误传播实现以隔离回调差异，不能将11失败描述为旧镜像全栈重放。17项也不是AndroidBionic全GUI或保存事务的完整验证。


时区回退交付收尾：同镜像六版本双槽9组/102次阶段调用通过；731来源、维护文件79+1+3重建一致且0待更新。当前审计logs/timezone-retry-delivery.json。MTP与FF库字节保持上一候选一致，物理无震动、现场设置原因及完整12组仍未完成。
