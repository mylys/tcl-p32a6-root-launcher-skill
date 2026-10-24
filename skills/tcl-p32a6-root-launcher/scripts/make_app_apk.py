"""Create a local LeanbackOnFire application-mode package, retaining original code.

Removes only the HOME category XML element and obsolete signing records.
The result must be zipaligned and signed with a local key before installation.
Upstream: https://github.com/tsynik/LeanbackLauncher/releases/tag/v1.63
"""
import struct
import zipfile
import copy
import sys
from pathlib import Path

import argparse, hashlib
parser=argparse.ArgumentParser(description='Remove exactly one HOME category; preserve other APK content')
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
SOURCE, OUTPUT=args.source,args.output
if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!='98824777eb845204fc82022a88b82dbce9940a802eaa0f55a28b58cdb9e5cacc':
    raise SystemExit('Expected verified official LeanbackOnFire 1.63 APK; source hash mismatch')
if OUTPUT.exists():
    raise SystemExit('Output already exists; choose a new path')
OUTPUT.parent.mkdir(parents=True,exist_ok=True)

with zipfile.ZipFile(SOURCE) as original:
    xml = original.read('AndroidManifest.xml')
    strings = []
    chunks = []
    pos = 8
    while pos < len(xml):
        kind, header_size, size = struct.unpack_from('<HHI', xml, pos)
        assert size >= header_size and pos + size <= len(xml)
        if kind == 1:
            count, _, flags, start, _ = struct.unpack_from('<IIIII', xml, pos + 8)
            def length(offset, wide=False):
                if wide:
                    value = struct.unpack_from('<H', xml, offset)[0]
                    if value & 0x8000:
                        return ((value & 0x7fff) << 16) | struct.unpack_from('<H', xml, offset + 2)[0], offset + 4
                    return value, offset + 2
                value = xml[offset]
                if value & 0x80:
                    return ((value & 0x7f) << 8) | xml[offset + 1], offset + 2
                return value, offset + 1
            for i in range(count):
                offset = pos + start + struct.unpack_from('<I', xml, pos + header_size + i * 4)[0]
                if flags & 0x100:
                    _, offset = length(offset)
                    n, offset = length(offset)
                    strings.append(xml[offset:offset+n].decode('utf-8'))
                else:
                    n, offset = length(offset, True)
                    strings.append(xml[offset:offset+n*2].decode('utf-16le'))
        chunks.append((pos, kind, size))
        pos += size
    removed = set()
    matches = 0
    for i, (pos, kind, size) in enumerate(chunks):
        if kind != 0x102:
            continue
        tag = strings[struct.unpack_from('<I', xml, pos + 20)[0]]
        if tag != 'category':
            continue
        attr_start, attr_size, attr_count = struct.unpack_from('<HHH', xml, pos + 24)
        for j in range(attr_count):
            offset = pos + 16 + attr_start + j * attr_size
            name_idx, raw_idx = struct.unpack_from('<II', xml, offset + 4)
            value_idx = raw_idx if raw_idx != 0xffffffff else struct.unpack_from('<I', xml, offset + 16)[0]
            if strings[name_idx] == 'name' and strings[value_idx] == 'android.intent.category.HOME':
                next_pos, next_kind, _ = chunks[i+1]
                assert next_kind == 0x103
                assert strings[struct.unpack_from('<I', xml, next_pos + 20)[0]] == 'category'
                removed.update((i, i+1))
                matches += 1
    assert matches == 1, f'Expected exactly one HOME category, found {matches}'
    result = bytearray(xml[:8] + b''.join(xml[p:p+n] for i, (p, _, n) in enumerate(chunks) if i not in removed))
    struct.pack_into('<I', result, 4, len(result))
    def signing_record(name):
        name = name.upper()
        return name.startswith('META-INF/') and (name.endswith(('.RSA', '.DSA', '.EC', '.SF')) or name == 'META-INF/MANIFEST.MF')
    with zipfile.ZipFile(OUTPUT, 'w') as out:
        for entry in original.infolist():
            if not signing_record(entry.filename):
                out.writestr(copy.copy(entry), result if entry.filename == 'AndroidManifest.xml' else original.read(entry.filename))
    with zipfile.ZipFile(OUTPUT) as out:
        changed = [name for name in out.namelist() if original.read(name) != out.read(name)]
        assert changed == ['AndroidManifest.xml'], changed
    print(f'Created {OUTPUT.name}; removed one HOME element; all code and resources unchanged.')
