# 刷新容量卡住：只读紧急采集

在电脑 PowerShell 中，将两个同名 `collect-refresh-state` 文件放在同一目录，然后运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\collect-refresh-state.ps1
```

多设备时用 `-Serial 序列号`。保持 Recovery 当前现场，不必再点刷新容量。脚本不执行 wait-for-device；没有设备时各项仍有超时并记录错误，不自动重启或重试连接。

先保存 recovery.log，再抓取两次 recovery 线程/内核栈、系统线程、fd、mountinfo、logcat、dmesg 和属性。每条 adb 客户端有 15 秒上限，线程集合各 30 秒；单个内核栈有设备 timeout 时限 2 秒。超时只终止该电脑 adb 客户端，不对 recovery 或设备任务发信号；远端只读命令不保证随客户端一同退出。采集结果可能不完整，查看 capture-status.tsv 与 stderr/error 文件。脚本不执行 df、du、目录大小遍历、挂载、容量刷新、sysfs 写入或设备重启。

压缩包保存在运行目录；若压缩失败，原目录仍保留。原始日志可能含个人信息，留在本地供分析，不同步公开仓库。当前脚本完成 shell 语法和源码检查，未在 Windows/手机上执行验证。
