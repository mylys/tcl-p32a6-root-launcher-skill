#!/usr/bin/env python3
"""Explicit-target, bounded maintenance through an already accessible TCL ADB.

No discovery, network scanning, reboot or persistent installation is implicit.
Long jobs publish a completion marker; a timeout never triggers a second job.
"""
import argparse
import json
import re
import shlex
import socket
import subprocess
import tempfile
import time
import uuid
from pathlib import Path


class Bridge:
    def __init__(self, serial, adb="adb", method="sserver"):
        if not serial or not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", serial):
            raise ValueError("Specify one ADB serial/IP:port; wildcards are not accepted")
        self.serial, self.binary, self.method = serial, adb, method
        self.port = None

    def adb(self, *args, timeout=30):
        p = subprocess.run([self.binary, "-s", self.serial, *map(str, args)],
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode:
            raise RuntimeError(p.stderr.strip() or p.stdout.strip())
        return p.stdout.strip()

    def check_device(self):
        facts = {k: self.adb("shell", "getprop " + k) for k in
                 ("ro.product.device", "ro.build.version.sdk", "ro.build.version.incremental")}
        if facts["ro.product.device"] != "p32a6" or facts["ro.build.version.sdk"] != "22":
            raise RuntimeError("Outside verified p32a6/API22 scope: " + repr(facts))
        return facts

    def request(self, command):
        if self.method == "su":
            return self.adb("shell", "su -c " + shlex.quote(command))
        if self.port is None:
            self.port = int(self.adb("forward", "tcp:0", "localfilesystem:/dev/socket/sserver"))
        if len(command.encode()) >= 512:
            raise ValueError("sserver request too long; push a script instead")
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as sock:
            sock.sendall(command.encode())
            return sock.recv(64).decode(errors="replace")

    def run(self, script, timeout=180):
        self.check_device()
        remote = "/data/local/tmp/tcl-skill-" + uuid.uuid4().hex
        self.adb("shell", "umask 077; mkdir " + remote)
        result = {"remote_directory": remote, "completed": False}
        try:
            self.adb("push", Path(script).resolve(), remote + "/run.sh")
            # Publish readable output before atomically publishing the exit status.
            dispatch = (f"#!/system/bin/sh\numask 077\n"
                        f"sh {remote}/run.sh >{remote}/out 2>&1\nresult=$?\n"
                        f"chown 2000:2000 {remote}/out\n"
                        f"echo $result >{remote}/status.tmp\n"
                        f"chown 2000:2000 {remote}/status.tmp\n"
                        f"mv {remote}/status.tmp {remote}/status\n")
            with tempfile.TemporaryDirectory() as local:
                f = Path(local) / "dispatch.sh"
                f.write_text(dispatch)
                self.adb("push", f, remote + "/dispatch.sh")
            # Fully detach from the socket; compilation may take minutes.
            self.request(f"(sh {remote}/dispatch.sh </dev/null >/dev/null 2>&1) &")
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                status = self.adb("shell", f"if [ -f {remote}/status ]; then cat {remote}/status; fi")
                if re.fullmatch(r"[0-9]+", status):
                    result.update(completed=True, status=int(status),
                                  output=self.adb("shell", "cat " + remote + "/out"))
                    if result["status"] == 0:
                        self.request("rm -rf " + remote)
                        result["temporary_files_removed"] = True
                    return result
                time.sleep(1)
            result["error"] = "Timed out; job may still run. Inspect this directory; do not repeat the mutation."
            return result
        finally:
            if self.port is not None:
                try:
                    self.adb("forward", "--remove", "tcp:" + str(self.port))
                finally:
                    self.port = None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--serial", required=True)
    p.add_argument("--adb", default="adb")
    p.add_argument("--method", choices=("sserver", "su"), default="sserver")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--probe", action="store_true", help="Root identity only; no persistent changes")
    group.add_argument("--script", type=Path)
    p.add_argument("--execute", action="store_true", help="Required to run a supplied maintenance script")
    p.add_argument("--timeout", type=int, default=180)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    if args.timeout <= 0:
        p.error("--timeout must be positive")
    if args.script and not args.execute:
        p.error("Read the script and obtain task authorization, then pass --execute")
    bridge = Bridge(args.serial, args.adb, args.method)
    with tempfile.TemporaryDirectory() as local:
        script = args.script
        if args.probe:
            script = Path(local) / "identity.sh"
            script.write_text("id\n")
        result = bridge.run(script, args.timeout)
    if args.probe:
        result["root_verified"] = bool(re.search(r"\buid=0\(root\)", result.get("output", "")))
    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data + "\n")
        args.output.chmod(0o600)
    print(data)
    return 0 if result.get("status") == 0 and (not args.probe or result["root_verified"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
