"""Read only the small, public metadata section of a supported PS4-format PKG.

Only seek/read operations are used; game packages are never extracted, decrypted,
written to, renamed, or loaded into RAM. Unsupported formats simply return {}.
The PS4 PKG header/file-entry layout is documented by the shadPS4 project.
"""
from __future__ import annotations

import struct
from pathlib import Path

PNG = b'\x89PNG\r\n\x1a\n'
MAX_ITEMS = 100_000
MAX_TABLE = 4_000_000
MAX_ICON = 6_000_000
MAX_SFO = 1_000_000


def sfo_details(data: bytes) -> dict:
    if len(data) < 20 or data[:4] != b'\x00PSF':
        return {}
    try:
        _, _version, keys_start, values_start, count = struct.unpack_from('<IIIII', data, 0)
        if count > 300 or 20 + count * 16 > len(data):
            return {}
        result = {}
        for i in range(count):
            key_off, fmt, length, max_length, value_off = struct.unpack_from('<HHIII', data, 20 + i * 16)
            kp, vp = keys_start + key_off, values_start + value_off
            if not (0 <= kp < len(data) and 0 <= vp <= len(data)):
                continue
            if length > 4096 or vp + length > len(data):
                continue
            key = data[kp:kp + 90].split(b'\x00', 1)[0].decode('utf-8', 'replace')
            if key in ('TITLE', 'TITLE_ID'):
                result[key] = data[vp:vp + length].split(b'\x00', 1)[0].decode('utf-8', 'replace').strip()
        return {'title': result.get('TITLE', ''), 'title_id': result.get('TITLE_ID', '')}
    except (ValueError, struct.error, IndexError):
        return {}


def read_ps4_pkg_details(filename: str | Path) -> dict:
    """Try reading the genuine game icon and title, limiting every seek/read.

    Returns {'icon': bytes, 'title': ..., 'title_id': ...} when available,
    or {} when the package uses another layout/encrypted metadata.
    """
    try:
        path = Path(filename)
        with path.open('rb') as f:
            f.seek(0, 2)
            file_size = f.tell()
            if file_size < 0x120:
                return {}
            f.seek(0)
            header = f.read(0x20)
            if header[:4] != b'\x7fCNT':
                return {}
            count = struct.unpack_from('>I', header, 0x10)[0]
            table_start = struct.unpack_from('>I', header, 0x18)[0]
            table_size = count * 0x20
            if not (0 < count <= MAX_ITEMS and 0x20 <= table_start <= file_size
                    and table_size <= MAX_TABLE and table_start + table_size <= file_size):
                return {}
            f.seek(table_start)
            table = f.read(table_size)
            locations = {}
            for off in range(0, len(table), 0x20):
                item_id, _filename_off, flags1, flags2, position, size = struct.unpack_from('>6I', table, off)
                if ((item_id == 0x1000 and size <= MAX_SFO) or
                        (item_id in (0x1006, 0x1220) or 0x1200 <= item_id <= 0x121f) and size <= MAX_ICON):
                    if size and position + size <= file_size and position >= 0x20:
                        locations[item_id] = (position, size)
            meta = {}
            if 0x1000 in locations:
                pos, size = locations[0x1000]
                f.seek(pos)
                meta.update(sfo_details(f.read(size)))
            # If the ordinary game icon is absent, try genuine game preview
            # images (pic0/pic1). Do not read the game payload itself.
            for item_id in list(range(0x1200, 0x1220)) + [0x1220, 0x1006]:
                if item_id not in locations:
                    continue
                pos, size = locations[item_id]
                f.seek(pos)
                contents = f.read(size)
                if (len(contents) == size and contents.startswith(PNG) and len(contents) > 256
                        and len(contents) >= 24 and 24 <= int.from_bytes(contents[16:20], 'big') <= 4096
                        and 24 <= int.from_bytes(contents[20:24], 'big') <= 4096):
                    meta['icon'] = contents
                    break
            return meta
    except (OSError, ValueError, struct.error, OverflowError):
        return {}
