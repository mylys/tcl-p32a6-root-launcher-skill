---
name: tcl-p32a6-root-launcher
description: 为自有 TCL p32a6 Android 5.1.1 电视核验 sserver 按次 Root、安装可回退的 phh 持久 Root、配置 Leanback 默认 HOME；适用于这套旧固件的授权维护及故障恢复。
---

# TCL p32a6 Root 与默认桌面

目标是按用户选择完成 Root、桌面或回退，不默认把三项全做。用户只要求解释、制作教程或检查时，不连接或修改电视。此技能记录的是 **p32a6 / API 22 / V8-A962T04-LF1V117** 的实测路径，不是通用 TCL Root 工具。

## 先确定任务与环境

- 从当前会话取得明确设备、ADB 地址与授权范围。所有命令指定单一 `--serial`，不扫描局域网。模型显示 `AOSP on p32a6`，案例商品型号为 TCL 55V2；商品名不能替代固件核验。
- 若用户已授权相应修改，不重复索要相同许可。开机脚本写入和签名参考调整必须属于当前授权；仅允许安装普通 App 不等同于这两项授权。
- 若另一任务正在操作同一电视，先确定由谁执行；未取得用户授权，不自行给其他聊天发消息。
- 所需工具：Python 3.10+、ADB；构建另需 JDK 17、Android SDK、NDK。工具路径和地址由参数提供，禁止复制案例的私人路径或密钥。

## 按需要读取

- 获取按次 Root、核验能力：[01-root-access.md](references/01-root-access.md)。`sserver` 是厂商本地命令服务，必须验证 `uid=0(root)`；普通 ADB 不等于 Root。
- 持久 Root：[02-persistent-root.md](references/02-persistent-root.md)。先完成并在电脑校验关键分区备份，再准备源码构建、安装与回退。
- 默认桌面：[03-default-home.md](references/03-default-home.md)。必须使用兼容 API 22 的桌面；Root 不会让最低 API 23 的 Projectivy 自动兼容。
- 重启、遥控器、关闭调试和恢复：[04-validation-recovery.md](references/04-validation-recovery.md)。
- 已验证范围、来源和不能推断的事项：[05-case-evidence.md](references/05-case-evidence.md)。

## 关键约束

1. **先检查，后修改，保留回退。** 备份配置及实际要改的文件。系统分区备份保存在用户电脑，不能只留电视内。不要把关键分区备份称作整机备份。
2. **不要覆盖原厂 recovery/watchdog 逻辑。** `prepare_root.py` 只接受案例原始启动脚本 SHA-256，在 shebang 后插入 daemon 启动段，其余字节保持不变；固件或哈希不同就停止写入，转为只读分析。不要关闭 SELinux、替换 app_process 或刷分区来追求同样结果。
3. **Root 授权要分清身份。** phh 上游对 ADB shell UID 2000 自动放行；`adb shell su -c id` 成功不能证明普通应用授权弹窗正确。需分别验证普通应用未授权拒绝、手动允许、重启后行为，不能设为自动允许全部应用。
4. **桌面用系统 HOME 偏好。** Android 5 没有 `cmd package set-home-activity`，使用附带 Java helper 调用 PackageManager API；保留 CyberUI。不要直接覆盖整个 `packages.xml` 或 `package-restrictions.xml`。
5. **签名调整严格限于这次同签名桌面更新。** 临时 `sys.currentlauncher` 参考切换属于厂商限制的绕过，必须说明范围。恢复事务前的值；不要启用 `persist.sys.matrix.mi.enable=1`，它还影响共享签名比较且在 system_server 初始化时缓存。
6. **失败不循环重试。** `pm install` 可能退出 0 但输出 Failure；桥接超时也可能仍在编译。查看唯一暂存目录、安装日志、实际 APK 哈希和 HOME 候选，判断是否成功后再行动。超时不启动第二次安装，不删除运行中作业的文件。
7. 不卸载系统核心、原桌面、输入源、遥控器、蓝牙、键盘等组件；未核实用途的包不批量停用。`com.tcl.usagestats` 还含 NTP 校时，不能只凭名称停用。
8. 配置变化逐步验证。开机拉起普通 App 不等于默认 HOME；注入 HOME 不等于实体遥控器通过。与用户反馈分别记录。维护完成关闭网络调试并验证端口；若用户要求保留连接或另有已协调任务需要连接，记录例外而不是擅自断开。

## 脚本使用边界

脚本位于 `scripts/`。`build_*`、`make_*`、`prepare_root.py` 和 `verify_backup.py` 只在电脑生成/校验产物；`tv_bridge.py`、`home_preference.py` 会访问指定电视。运行自定义脚本和写 HOME 需要显式 `--execute`，这只是误操作保护，不代替用户授权。

发布或分享时只提供本技能和经过审阅的源码。排除 APK、私钥、密码文件、ADB 凭据、授权数据库、设备快照和固件备份。最终反馈写清实际完成、验证方式、仍待确认的行为，以及用户可执行的恢复入口。
