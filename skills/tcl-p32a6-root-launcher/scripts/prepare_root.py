#!/usr/bin/env python3
"""Generate local startup patch and guarded install/rollback scripts, without ADB."""
import argparse
import hashlib
import json
from pathlib import Path

OEM_SHA256 = "fba6dadc2644bda419d595751cee8a0e96cfe56f42f17ad732889042188f0453"
BLOCK = (b"# BEGIN tcl-p32a6-root-launcher: phh daemon\n"
         b"if [ -x /system/xbin/su ]; then\n"
         b"    /system/xbin/su --daemon </dev/null >/dev/null 2>&1 &\n"
         b"fi\n# END tcl-p32a6-root-launcher\n")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch(original):
    if sha(original) != OEM_SHA256:
        raise ValueError("OEM startup hash differs from verified firmware; stop and inspect it")
    first, remainder = original.split(b"\n", 1)
    if first != b"#!/system/bin/sh":
        raise ValueError("Unexpected startup interpreter")
    return first + b"\n" + BLOCK + remainder


def prepare(original, su, output):
    if output.exists():
        raise ValueError("Use a new output directory; never overwrite an existing rollback package")
    raw, binary = original.read_bytes(), su.read_bytes()
    patched = patch(raw)
    # Only the verified 32-bit little-endian ARM executable family is accepted.
    if binary[:6] != b"\x7fELF\x01\x01" or binary[18:20] != b"\x28\x00":
        raise ValueError("su must be a locally reviewed ARM32 little-endian ELF")
    output.mkdir(parents=True, mode=0o700)
    for name, data in (("install-recovery.original.sh", raw), ("install-recovery.patched.sh", patched), ("su", binary)):
        (output / name).write_bytes(data)
    hashes = {"original": sha(raw), "patched": sha(patched), "su": sha(binary)}
    common = f'''#!/system/bin/sh
set -e
BB=/system/xbin/busybox
ORIG=/system/bin/install-recovery.sh.pre-tcl-skill
START=/system/bin/install-recovery.sh
check_hash() {{ echo "$1  $2" | "$BB" sha256sum -c -; }}
[ "$("$BB" id -u)" = 0 ]
[ "$(getprop ro.product.device)" = p32a6 ]
[ "$(getprop ro.build.version.sdk)" = 22 ]
'''
    install = common + f'''
STAGE=/data/local/tmp/tcl-root-skill-stage
[ -f "$STAGE/BACKUP_VERIFIED_ON_HOST" ]
check_hash {hashes['original']} "$START"
check_hash {hashes['su']} "$STAGE/su"
check_hash {hashes['patched']} "$STAGE/install-recovery.patched.sh"
pm path me.phh.superuser | "$BB" grep '^package:'
[ ! -e "$ORIG" ] && [ ! -L "$ORIG" ]
[ ! -e /system/xbin/su ] && [ ! -L /system/xbin/su ]
[ ! -e /system/xbin/su.tcl-new ]
[ ! -e "$START.tcl-new" ]
MODIFIED=0
finish() {{
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ] && [ "$MODIFIED" = 1 ]; then
        cp "$ORIG" "$START.tcl-new"
        chown 0:0 "$START.tcl-new"
        chmod 750 "$START.tcl-new"
        mv -f "$START.tcl-new" "$START"
        rm -f /system/xbin/su /system/xbin/su.tcl-new
        echo INSTALL_FAILED_RESTORED_OEM_STARTUP
    fi
    sync
    "$BB" mount -o remount,ro /system || result=1
    exit "$result"
}}
"$BB" mount -o remount,rw /system
trap finish EXIT
cp "$START" "$ORIG"
chown 0:0 "$ORIG"
chmod 600 "$ORIG"
MODIFIED=1
cp "$STAGE/su" /system/xbin/su.tcl-new
chown 0:0 /system/xbin/su.tcl-new
chmod 755 /system/xbin/su.tcl-new
check_hash {hashes['su']} /system/xbin/su.tcl-new
mv /system/xbin/su.tcl-new /system/xbin/su
cp "$STAGE/install-recovery.patched.sh" "$START.tcl-new"
chown 0:0 "$START.tcl-new"
chmod 750 "$START.tcl-new"
mv -f "$START.tcl-new" "$START"
check_hash {hashes['patched']} "$START"
echo INSTALLED_REBOOT_AND_VERIFY_AUTHORIZATION
'''
    rollback = common + f'''
check_hash {hashes['original']} "$ORIG"
check_hash {hashes['patched']} "$START"
check_hash {hashes['su']} /system/xbin/su
[ ! -e "$START.tcl-restore" ]
"$BB" mount -o remount,rw /system
trap 'sync; "$BB" mount -o remount,ro /system' EXIT
cp "$ORIG" "$START.tcl-restore"
chown 0:0 "$START.tcl-restore"
chmod 750 "$START.tcl-restore"
mv -f "$START.tcl-restore" "$START"
check_hash {hashes['original']} "$START"
rm /system/xbin/su
rm "$ORIG"
echo OEM_STARTUP_RESTORED_REBOOT_TO_STOP_ROOT_DAEMON
'''
    (output / "install.sh").write_text(install)
    (output / "rollback.sh").write_text(rollback)
    (output / "hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return hashes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original", required=True, type=Path)
    p.add_argument("--su", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(prepare(a.original, a.su, a.output), indent=2))


if __name__ == "__main__":
    main()
