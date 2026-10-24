#!/system/bin/sh
# Push as /data/local/tmp/tcl-home-stage/install.sh, execute through tv_bridge.
set -e
BB=/system/xbin/busybox
STAGE=/data/local/tmp/tcl-home-stage
TARGET=com.amazon.tv.leanbacklauncher
[ "$("$BB" id -u)" = 0 ]
[ "$(getprop ro.product.device)" = p32a6 ]
[ "$(getprop ro.build.version.sdk)" = 22 ]
[ "$(getprop persist.sys.matrix.mi.enable)" = 0 ]
pm path "$TARGET" | "$BB" grep '^package:'
cd "$STAGE"
"$BB" sha256sum -c SHA256SUMS
previous=$(getprop sys.currentlauncher)
case "$previous" in
    com.tcl.cyberui|com.amazon.tv.leanbacklauncher) ;;
    *) echo UNEXPECTED_SIGNATURE_REFERENCE_STOP; exit 1 ;;
esac
restore_reference() { setprop sys.currentlauncher "$previous"; }
trap restore_reference EXIT
trap 'exit 130' HUP INT TERM
setprop sys.currentlauncher "$TARGET"
pm install -r "$STAGE/leanback-home-local.apk" > "$STAGE/install.log" 2>&1
cat "$STAGE/install.log"
"$BB" grep -q '^Success' "$STAGE/install.log"
# Android pm sometimes exits 0 even when it prints Failure. Do not trust exit alone.
