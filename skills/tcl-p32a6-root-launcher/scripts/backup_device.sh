#!/system/bin/sh
# Read-only partition acquisition; writes only to a new staging directory.
set -e
set -o pipefail
umask 077
BB=/system/xbin/busybox
[ "$("$BB" id -u)" = 0 ]
[ "$(getprop ro.product.device)" = p32a6 ]
[ "$(getprop ro.build.version.sdk)" = 22 ]
cd /data/local/tmp/tcl-root-skill-stage
mkdir backup
cp -p /system/bin/install-recovery.sh backup/install-recovery.sh
cp /init.rc backup/init.rc
for part in rootsys recovery system; do
    [ -b "/dev/block/$part" ]
    "$BB" dd if="/dev/block/$part" bs=1048576 | "$BB" gzip -1 > "backup/$part.img.gz.partial"
    "$BB" gzip -t "backup/$part.img.gz.partial"
    mv "backup/$part.img.gz.partial" "backup/$part.img.gz"
done
cd backup
"$BB" sha256sum init.rc install-recovery.sh rootsys.img.gz recovery.img.gz system.img.gz > SHA256SUMS
cd ..
chown -R 2000:2000 backup
echo BACKUP_COMPLETE_PULL_AND_VERIFY_ON_HOST
