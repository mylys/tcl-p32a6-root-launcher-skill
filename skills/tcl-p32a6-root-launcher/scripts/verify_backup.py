#!/usr/bin/env python3
"""Verify copied partition archives, then issue a local installation prerequisite."""
import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path
from prepare_root import OEM_SHA256

SIZES = {"rootsys.img.gz": 25165824, "recovery.img.gz": 50331648,
         "system.img.gz": 1694498816}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(folder):
    receipt = folder / "BACKUP_VERIFIED_ON_HOST"
    receipt.unlink(missing_ok=True)
    entries = {}
    for line in (folder / "SHA256SUMS").read_text().splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_.-]+)", line)
        if not match or match[2] in entries:
            raise ValueError("Invalid/duplicate checksum entry")
        entries[match[2]] = match[1]
    if set(entries) != set(SIZES) | {"init.rc", "install-recovery.sh"}:
        raise ValueError("Missing or unexpected backup members")
    result = {}
    for name, expected in entries.items():
        path = folder / name
        if path.is_symlink() or digest(path) != expected:
            raise ValueError("Backup SHA-256 mismatch: " + name)
        row = {"sha256": expected, "bytes": path.stat().st_size}
        if name in SIZES:
            count = 0
            with gzip.open(path, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    count += len(chunk)
                    if count > SIZES[name]:
                        raise ValueError("Unexpected partition size: " + name)
            if count != SIZES[name]:
                raise ValueError("Truncated partition: " + name)
            row["uncompressed_bytes"] = count
        result[name] = row
    if entries["install-recovery.sh"] != OEM_SHA256:
        raise ValueError("Unverified OEM startup version; do not install")
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    receipt.chmod(0o600)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(verify(parser.parse_args().directory), indent=2))
