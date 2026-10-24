import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/tcl-p32a6-root-launcher/scripts"
sys.path.insert(0, str(SCRIPTS))
import prepare_root
import tv_bridge
import verify_backup


class RootPayloadTests(unittest.TestCase):
    def test_patch_keeps_every_oem_byte_after_shebang(self):
        original = b"#!/system/bin/sh\n# OEM recovery\ncheck_recovery\nwatchdog\n"
        with patch.object(prepare_root, "OEM_SHA256", prepare_root.sha(original)):
            result = prepare_root.patch(original)
        self.assertEqual(result.replace(prepare_root.BLOCK, b"", 1), original)
        self.assertEqual(result.count(prepare_root.BLOCK), 1)

    def test_unknown_firmware_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_root.patch(b"#!/system/bin/sh\nunknown_firmware\n")

    def test_generated_install_and_rollback_parse_and_preserve_input(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            original = b"#!/system/bin/sh\n# synthetic OEM fixture\necho watchdog\n"
            source = p / "original.sh"
            source.write_bytes(original)
            su = p / "su"
            elf = bytearray(64)
            elf[:6] = b"\x7fELF\x01\x01"
            elf[18:20] = b"\x28\x00"
            su.write_bytes(elf)
            with patch.object(prepare_root, "OEM_SHA256", prepare_root.sha(original)):
                prepare_root.prepare(source, su, p / "out")
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual((p / "out/install-recovery.original.sh").read_bytes(), original)
            for name in ("install.sh", "rollback.sh"):
                subprocess.run(["sh", "-n", str(p / "out" / name)], check=True)
            with self.assertRaises(ValueError):
                prepare_root.prepare(source, su, p / "out")

    def test_foreign_architecture_does_not_generate_payload(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            source, su = p / "original", p / "su"
            source.write_bytes(b"#!/system/bin/sh\necho OEM\n")
            su.write_bytes(b"not an ARM ELF")
            with patch.object(prepare_root, "OEM_SHA256", prepare_root.sha(source.read_bytes())):
                with self.assertRaises(ValueError):
                    prepare_root.prepare(source, su, p / "out")
            self.assertFalse((p / "out").exists())


class BackupTests(unittest.TestCase):
    def fixture(self, p, compressed_payload=b"partition"):
        (p / "init.rc").write_bytes(b"init fixture")
        (p / "install-recovery.sh").write_bytes(b"OEM fixture")
        for name in verify_backup.SIZES:
            (p / name).write_bytes(gzip.compress(compressed_payload))
        names = ["init.rc", "install-recovery.sh", *verify_backup.SIZES]
        (p / "SHA256SUMS").write_text("".join(verify_backup.digest(p / n) + "  " + n + "\n" for n in names))

    def test_receipt_only_after_complete_gzip_size_and_hash_validation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.fixture(p)
            sizes = {n: 9 for n in verify_backup.SIZES}
            with patch.object(verify_backup, "SIZES", sizes), patch.object(verify_backup, "OEM_SHA256", verify_backup.digest(p / "install-recovery.sh")):
                result = verify_backup.verify(p)
            self.assertEqual(result["system.img.gz"]["uncompressed_bytes"], 9)
            self.assertEqual(json.loads((p / "BACKUP_VERIFIED_ON_HOST").read_text()), result)

    def test_corruption_removes_stale_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.fixture(p)
            (p / "BACKUP_VERIFIED_ON_HOST").write_text("stale success")
            (p / "init.rc").write_bytes(b"corrupted")
            with self.assertRaises(ValueError):
                verify_backup.verify(p)
            self.assertFalse((p / "BACKUP_VERIFIED_ON_HOST").exists())

    def test_short_partition_rejected_even_when_compressed_hash_matches(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            self.fixture(p, b"short")
            with patch.object(verify_backup, "SIZES", {n: 9 for n in verify_backup.SIZES}):
                with self.assertRaises(ValueError):
                    verify_backup.verify(p)
            self.assertFalse((p / "BACKUP_VERIFIED_ON_HOST").exists())


class FakeBridge(tv_bridge.Bridge):
    def __init__(self, status="0", device="p32a6"):
        super().__init__("fixture-device")
        self.status, self.device = status, device
        self.calls, self.requests = [], []

    def adb(self, *args, timeout=30):
        self.calls.append(args)
        if args[:1] == ("shell",):
            command = args[1]
            if command == "getprop ro.product.device":
                return self.device
            if command == "getprop ro.build.version.sdk":
                return "22"
            if command.startswith("if [ -f"):
                return self.status
            if command.startswith("cat "):
                return "uid=0(root) gid=0(root)"
        return ""

    def request(self, command):
        self.port = 12345
        self.requests.append(command)
        return "ok"


class BridgeTests(unittest.TestCase):
    def test_rejects_shell_metacharacters_in_target(self):
        for target in ("", "host;id", "$(id)", "*"):
            with self.assertRaises(ValueError):
                tv_bridge.Bridge(target)

    def test_other_platform_stops_before_staging(self):
        b = FakeBridge(device="other-device")
        with self.assertRaises(RuntimeError):
            b.run(Path("fixture.sh"))
        self.assertFalse(b.requests)
        self.assertFalse(any(c[0] == "push" for c in b.calls))

    def test_success_removes_only_unique_job_directory_and_forward(self):
        b = FakeBridge()
        result = b.run(Path("fixture.sh"))
        self.assertTrue(result["completed"])
        self.assertEqual(result["status"], 0)
        self.assertEqual(b.requests[-1], "rm -rf " + result["remote_directory"])
        self.assertIn(("forward", "--remove", "tcp:12345"), b.calls)

    def test_timeout_preserves_job_and_does_not_repeat_execution(self):
        b = FakeBridge(status="")
        with patch.object(tv_bridge.time, "monotonic", side_effect=[0, 2]):
            result = b.run(Path("fixture.sh"), timeout=1)
        self.assertFalse(result["completed"])
        self.assertEqual(len(b.requests), 1)
        self.assertIn(("forward", "--remove", "tcp:12345"), b.calls)

    def test_nonzero_status_is_not_reported_as_success_or_cleaned(self):
        b = FakeBridge(status="7")
        result = b.run(Path("fixture.sh"))
        self.assertEqual(result["status"], 7)
        self.assertNotIn("temporary_files_removed", result)
        self.assertEqual(len(b.requests), 1)


if __name__ == "__main__":
    unittest.main()
