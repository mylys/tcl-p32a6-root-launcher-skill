# 5. 已验证案例与来源

## 验证范围

2026-10-23 至 2026-10-24，在机主授权的 TCL 55V2 / p32a6 / V8-A962T04-LF1V117 上完成：

| 项目 | 证据与结论 |
|---|---|
| 按次 Root | 已有 ADB 转发到本地 sserver，命令输出 uid=0(root) |
| 持久 Root | 正常重启后 boot ID 改变，su daemon 自动运行，su -c id 成功 |
| 普通 App 授权 | 测试 App 未授权被拒；中文授权框手动允许后返回 Root；保存的授权跨重启保留 |
| 系统改动 | 新增 su，原厂 install-recovery.sh 插入 daemon 启动段；system 恢复只读 |
| 系统默认 HOME | PackageManager HOME 候选包含 CyberUI 与 Leanback，首选返回 Leanback |
| 开机保持 | 重启后第 212、232、252、272 秒采样均为 Leanback 前台 |
| 实体遥控器 | 机主明确反馈“HOME、设置、输入源都正常” |
| 原厂桌面 | 保持安装和启用，准备了系统 API 回退 |
| 收尾 | 指定设备 5555 端口拒绝连接；没有公开设备实际地址 |

原机使用的私有 ADB 授权、Root 管理器数据库、签名私钥、原始分区和完整设备日志不发布。这里是案例事实摘要，不是上传的原始证据包。

本案例没有验证全部 TCL 型号、全部授权过期策略、未来固件升级后的保持情况、所有课程播放/支付功能或每个 HDMI 端口的实际音视频。

## 方案取舍

- Projectivy 4.72 / 4.54 最低 API 23，目标设备 API 22，未安装成功；Root 不能补齐系统 API。
- FLauncher 0.18 的普通应用模式在此机停在启动画面，未作为最终桌面。
- LeanbackOnFire 1.63 API 22，实际运行与遥控导航通过。
- 单次 BOOT_COMPLETED 拉起另一个普通桌面测试版，不能可靠保持前台；最终使用真实 HOME 候选和系统偏好。
- `com.tcl.bi` 数据上报组件在案例中停用；`com.tcl.usagestats` 还含 NTP 校时，保留。这里不提供“一键停用所有 TCL 包”的清单。

## 固件分析依据

本机 PackageManagerService 的 `installPackageLI`、`isTclLauncher`、`compareSignatures`，以及 ActivityManagerService 的 `startHomeActivityLocked`、`setDefaultLauncher`、`startUILauncher` 支持教程所述逻辑。

安装校验的关键分支曾对照 smali 核验。JADX 的大方法可能有结构恢复警告，不能把全部反编译文本当作源码。系统中的 services.odex 原始 SHA-256 为：

```text
e226c36760181caf8e8ea8908f0dadbc5eec057596113ab84c3921bde7af6f61
```

固件文件和反编译文本不随仓库发布。用于对照的文件哈希不是可供其他机型直接使用的补丁。

## 固定上游来源

- [phhusson/Superuser](https://github.com/phhusson/Superuser/tree/9ae9705874b9fc7d3990aac639ab9667b06519c0)
- [phhusson/Widgets](https://github.com/phhusson/Widgets/tree/a64044a791754284c59e19342684dfd8bac8521a)
- [LeanbackOnFire v1.63](https://github.com/tsynik/LeanbackLauncher/releases/tag/v1.63)
- [AOSP Android 5.1.1 PackageManagerService](https://android.googlesource.com/platform/frameworks/base/+/android-5.1.1_r1/services/core/java/com/android/server/pm/PackageManagerService.java) 用于理解基础接口；TCL 分支必须以本机固件为准。

## 公开版脚本的验证层级

本仓库把一次设备脚本整理为参数化、默认不自动修改设备的复用工具。公开版本做离线单元测试、Python/Java 编译、APK 构建及结构验证；持久 Root 安装/回退不为发布而在正常工作的电视上重新执行。

因此，区分三种表述：历史设备流程“已实机验证”、公开构建脚本“已在电脑复现”、公开版系统写入脚本“由已验证步骤整理并离线检查”。不能把最后一种说成每条公开脚本都已在所有目标设备重新跑过。

### 本次公开版离线检查（2026-10-24）

- 12 项标准库 unittest 通过，覆盖未知固件拒绝、启动脚本逐字节保留、错误架构拒绝、备份损坏/截断拒绝、超时不重跑、失败保留证据以及临时转发清理。
- skill frontmatter 与格式校验通过；所有本地 Markdown 链接可解析。
- app / HOME 两个 APK 重新构建、验签通过，证书一致；aapt 确认 HOME 与 TCL 标记仅出现在预期版本，代码和资源与原 APK 一致。
- Java HOME helper 和 Root 管理器重新编译成功。
- 在干净固定提交上应用原生补丁，使用 NDK 26.1.10909125 重新编译 ARMv7 su 成功。
- 用历史实机原始启动脚本生成安装/回退包并检查 shell 语法；用已有备份的只读内容验证 SHA-256、gzip 和三处分区字节数全部通过。
- 未重新连接或修改电视。发布版桥接、安装和回退的设备执行仍需按本教程逐层验证。
