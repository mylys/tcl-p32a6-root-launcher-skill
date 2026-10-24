#!/usr/bin/env python3
"""Read or set HOME with the small, user-built Android 5 Java helper."""
import argparse
import re
import shlex
import subprocess
import uuid
from pathlib import Path

LEANBACK = "com.amazon.tv.leanbacklauncher/com.amazon.tv.leanbacklauncher.MainActivity"
STOCK = "com.tcl.cyberui/com.tcl.cyberui.MainActivity"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--serial", required=True)
    p.add_argument("--adb", default="adb")
    p.add_argument("--jar", type=Path, required=True)
    p.add_argument("--set", choices=("leanback", "stock"))
    p.add_argument("--execute", action="store_true")
    p.add_argument("--snapshot", type=Path, help="New local directory required for mutation")
    a = p.parse_args()
    if a.set and (not a.execute or a.snapshot is None):
        p.error("Setting HOME requires --execute and --snapshot NEW_DIRECTORY")
    if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", a.serial):
        p.error("Invalid explicit target")
    adb = [a.adb, "-s", a.serial]
    def call(*args):
        r = subprocess.run(adb + list(map(str, args)), check=True,
                           capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    def root(command):
        return call("shell", "su -c " + shlex.quote(command))
    if call("shell", "getprop ro.product.device") != "p32a6" or call("shell", "getprop ro.build.version.sdk") != "22":
        raise RuntimeError("Outside verified p32a6/API22 scope")
    remote = "/data/local/tmp/tcl-home-helper-" + uuid.uuid4().hex + ".jar"
    call("push", a.jar.resolve(), remote)
    command = "CLASSPATH=" + remote + " app_process /system/bin HomePreference"
    try:
        before = root(command)
        print(before)
        if not a.set:
            return
        a.snapshot.mkdir(parents=True, exist_ok=False, mode=0o700)
        (a.snapshot / "home-before.txt").write_text(before + "\n")
        old_component = call("shell", "getprop persist.sys.launcher.component")
        (a.snapshot / "component-before.txt").write_text(old_component + "\n")
        (a.snapshot / "package-restrictions.xml").write_text(root("cat /data/system/users/0/package-restrictions.xml") + "\n")
        target = LEANBACK if a.set == "leanback" else STOCK
        after = root(command + " " + shlex.quote(target))
        print(after)
        if "Preferred after: ComponentInfo{" + target + "}" not in after:
            raise RuntimeError("System did not confirm preferred HOME; persistent property unchanged")
        root("setprop persist.sys.launcher.component " + shlex.quote(target))
        if call("shell", "getprop persist.sys.launcher.component") != target:
            raise RuntimeError("Preferred HOME changed, persistent property failed; restore using snapshot")
        (a.snapshot / "home-after.txt").write_text(after + "\n")
        # No injected HOME or reboot: caller decides when to perform visible verification.
    finally:
        root("rm -f " + remote)


if __name__ == "__main__":
    main()
