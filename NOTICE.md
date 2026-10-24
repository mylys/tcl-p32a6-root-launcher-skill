# 来源与许可

本仓库文档和维护脚本采用 GPL-3.0-or-later；完整许可见 LICENSE。

`skills/tcl-p32a6-root-launcher/scripts/patches/phh-ndk26.patch` 是针对
[phhusson/Superuser](https://github.com/phhusson/Superuser) 指定提交的编译兼容补丁：

- `Superuser/jni/su/binds.c` 原作者 Pierre-Hugues Husson，GPL-3.0-or-later。
- `Superuser/jni/su/daemon.c` 原有声明包括 Adam Shanks、Zinx Verituse，Apache-2.0。
- `Superuser/jni/sqlite3/sqlite3.c` 为上游随附 SQLite 源码。

请保留上游各文件的版权和许可。此仓库不重新许可上游项目。

管理器来自 phhusson/Superuser 与 phhusson/Widgets；桌面来自
[tsynik/LeanbackLauncher](https://github.com/tsynik/LeanbackLauncher)。构建辅助脚本仅处理用户自行下载的指定 APK；不随仓库发布上游 APK、电视固件、反编译源码或二进制补丁。

仓库不包含用户的签名私钥、ADB 密钥、授权数据库、固件分区备份、设备地址和完整设备属性。

Apache-2.0 许可全文见 [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt)。
