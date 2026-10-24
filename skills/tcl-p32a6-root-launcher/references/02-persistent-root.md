# 2. 备份、构建与持久 Root

本节会写 `/system/xbin/su` 和 `/system/bin/install-recovery.sh`，必须已获准安装持久 Root。不是只读检查，也不是简单的桌面设置。已存在 Root 工具时先识别其安装方式，不覆盖。

已验证的原厂启动脚本 SHA-256：

```text
fba6dadc2644bda419d595751cee8a0e96cfe56f42f17ad732889042188f0453
```

公开安装生成器仅接受这一版本。它不是跨固件模板；不匹配时停止，不修改常量来强行运行。

## 2.1 关键分区备份

先只读查看 `/proc/partitions`、`/proc/mounts` 和 `df /data`，确认存在 `/system/xbin/busybox`、`/dev/block/rootsys`、`recovery`、`system`，并且没有其他维护作业。案例分区分别为 24 MiB、48 MiB、1616 MiB。先确认 `/data` 至少有约 2 GiB 额外空间；空间不足时改用经验证的流式备份，不盲目运行此落盘脚本。

```bash
adb -s "$TV_SERIAL" shell cat /proc/partitions > backup/partitions-before.txt
adb -s "$TV_SERIAL" shell df /data
adb -s "$TV_SERIAL" shell mkdir /data/local/tmp/tcl-root-skill-stage
python3 "$TV_SCRIPTS/tv_bridge.py" --serial "$TV_SERIAL" \
  --script "$TV_SCRIPTS/backup_device.sh" --execute --timeout 1800 \
  --output work/partition-backup-job.json
```

只有返回 `status: 0` 和 `BACKUP_COMPLETE_PULL_AND_VERIFY_ON_HOST` 后才继续。大作业不要因为终端等待久就重复启动。

```bash
adb -s "$TV_SERIAL" pull /data/local/tmp/tcl-root-skill-stage/backup backup/root-before
python3 "$TV_SCRIPTS/verify_backup.py" backup/root-before
```

验证器检查传输前后 SHA-256、gzip 完整性和每个分区解压字节数，通过才生成 `BACKUP_VERIFIED_ON_HOST`。备份不含用户数据、Bootloader、env 等全部分区，**不能称为整机备份，也不能随意刷到其他设备**。保存电脑端副本后，电视上的大型备份可按实际路径清理以释放空间。

## 2.2 源码与工具

本案例使用 phh Superuser 管理器 1.0.3.3、su 17，来自：

- 主仓库：`https://github.com/phhusson/Superuser`
- 主提交：`9ae9705874b9fc7d3990aac639ab9667b06519c0`
- Widgets 子模块提交：`a64044a791754284c59e19342684dfd8bac8521a`

它是较旧的 Android 兼容方案，不代表已对上游全部代码完成安全审计，也不是现代 Android 的通用推荐。

配置本机真实的 Android SDK、JDK 路径：

```bash
export TV_SDK='/本机/Android/sdk'
export TV_JAVA='/本机/JDK17'
git clone https://github.com/phhusson/Superuser.git work/phh-superuser
git -C work/phh-superuser checkout 9ae9705874b9fc7d3990aac639ab9667b06519c0
git -C work/phh-superuser submodule update --init --recursive
git -C work/phh-superuser/Widgets rev-parse HEAD
```

需要 JDK 17、Android SDK Platform 25、Build Tools 35.0.1，以及 NDK 26.1.10909125。Widgets 输出必须与上面的固定提交一致。

原生源码包含 GCC 嵌套函数，NDK Clang 无法直接编译。仓库补丁把回调移到文件作用域，并适配 SQLite `umask` 函数指针；没有有意改变授权策略。

```bash
git -C work/phh-superuser apply --check "$TV_SCRIPTS/patches/phh-ndk26.patch"
git -C work/phh-superuser apply "$TV_SCRIPTS/patches/phh-ndk26.patch"
(
  cd work/phh-superuser/Superuser
  "$TV_SDK/ndk/26.1.10909125/ndk-build" \
    APP_ABI=armeabi-v7a APP_PLATFORM=android-22 \
    APP_ALLOW_MISSING_DEPS=true APP_CFLAGS=-fcommon -j4
)
python3 "$TV_SCRIPTS/build_manager.py" \
  --source work/phh-superuser --sdk "$TV_SDK" --java-home "$TV_JAVA" \
  --output work/manager
```

输出 `work/manager/Superuser-local.apk`，包名 `me.phh.superuser`。管理器构建目录里新生成的签名密钥和密码文件要私下保留，后续更新必须沿用密钥；不要提交仓库。此脚本用于首次构建，会拒绝覆盖已有输出目录。

## 2.3 准备精确回退包

```bash
python3 "$TV_SCRIPTS/prepare_root.py" \
  --original backup/root-before/install-recovery.sh \
  --su work/phh-superuser/Superuser/libs/armeabi-v7a/su \
  --output work/root-payload
```

该命令只在电脑上生成：

- 原厂与修改后的启动脚本；修改仅是在 shebang 后插入 5 行 daemon 启动段。
- `su`、各文件哈希、安装脚本 `install.sh`、回退脚本 `rollback.sh`。

检查 diff，必须保留原厂 recovery 校验和 watchdog 全部原内容。安装后的 `su` 是 `root:root 0755`，**不设置 setuid 位**，授权由开机 Root daemon 处理。没有改 boot/recovery 镜像，没有替换 app_process，也没有降低 SELinux 设置。

## 2.4 安装

先安装管理器；普通 APK 安装受厂商普通安装开关限制时，只使用已核实的开发者设置，不反复强试。使用 `adb install` 的日志确认 Success。

```bash
adb -s "$TV_SERIAL" install -r work/manager/Superuser-local.apk
adb -s "$TV_SERIAL" push work/root-payload/su /data/local/tmp/tcl-root-skill-stage/su
adb -s "$TV_SERIAL" push work/root-payload/install-recovery.patched.sh /data/local/tmp/tcl-root-skill-stage/install-recovery.patched.sh
adb -s "$TV_SERIAL" push backup/root-before/BACKUP_VERIFIED_ON_HOST /data/local/tmp/tcl-root-skill-stage/BACKUP_VERIFIED_ON_HOST
python3 "$TV_SCRIPTS/tv_bridge.py" --serial "$TV_SERIAL" \
  --script work/root-payload/install.sh --execute --timeout 180 \
  --output work/persistent-root-install.json
```

必须核对退出状态为 0、输出有 `INSTALLED_REBOOT_AND_VERIFY_AUTHORIZATION`。脚本以哈希校验当前原厂文件、待写 su 和启动脚本，拒绝覆盖已存在的 su / 回退副本。写入通过临时文件与重命名完成，退出时把 `/system` 恢复只读。失败有尽力回退逻辑，但断电等情况不能靠 shell trap 保证恢复，电脑备份仍然必要。

## 2.5 重启及普通应用授权

按 [验证与恢复](04-validation-recovery.md) 的调试连接说明，安排一次正常重启。重启后检查：

```bash
adb -s "$TV_SERIAL" shell 'su -c id'
adb -s "$TV_SERIAL" shell 'su -c "cat /proc/mounts"'
adb -s "$TV_SERIAL" shell 'su -c "ls -l /system/xbin/su /system/bin/install-recovery.sh"'
```

核验 Root、system 只读、daemon 自动运行及实际文件哈希与本地一致。**ADB shell UID 2000 在此上游实现中自动允许**，所以这一检查不代表普通 App 的授权弹窗已验证。

使用你信任、可清理的普通测试 App 请求 `su -c id`：先拒绝，确认 Permission denied；再允许，确认 `uid=0(root)`；检查管理器默认行为为“提示”，不要设置自动允许全部应用。不同授权有效期要分别测试；不要声称没测过的过期策略也正常。最后清理测试 App 及其授权记录，不删除其他应用的记录。

恢复见 [4.3 移除本次持久 Root](04-validation-recovery.md#43-移除本次持久-root)。
