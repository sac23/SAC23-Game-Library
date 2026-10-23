"""Best-effort read-only extraction of *small artwork files* from ZIP game archives.

Never extract or unpack the actual game. Only open matching small entries by name,
with strict uncompressed size, compression ratio, count and image-header checks.
Unsupported/corrupt archives are simply ignored by the caller.
"""
from __future__ import annotations
import re
import struct
import zipfile
from pathlib import Path

MAX_ENTRIES = 55000
MAX_IMAGE_SIZE = 6_000_000
MAX_COMPRESSED = 8_000_000
MAX_RATIO = 140


def image_kind(data):
    if len(data) < 256:
        return None
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 24:
        w, h = struct.unpack_from('>II', data, 16)
        if 64 <= w <= 8192 and 64 <= h <= 8192:
            return '.png'
    if data[:3] == b'\xff\xd8\xff' and data[-2:] == b'\xff\xd9':
        return '.jpg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    return None


def rank_image(name):
    path = name.replace('\\', '/').lower().strip('/')
    if path.count('/') > 9 or '/__macosx/' in '/' + path:
        return -1
    tail = path.rsplit('/', 1)[-1]
    if re.fullmatch(r'(?:cover|boxart|box_art|front|poster)(?:[_-](?:ps4|ps5|front))?\.(?:jpe?g|png|webp)', tail):
        return 10 if 'update' not in path and '/dlc/' not in path else 4
    if tail in ('folder.jpg', 'folder.png', 'game.jpg', 'game.png'):
        return 8
    if tail in ('icon0.png', 'icon0_00.png'):
        return 7 if '/sce_sys/' in '/' + path else 6
    if tail in ('thumbnail.png', 'thumbnail.jpg', 'icon.png'):
        return 3
    return -1


def read_zip_cover(filename):
    """Return {'icon': bytes, 'cover_quality': 'icon'|'portrait'}, or {}."""
    try:
        with zipfile.ZipFile(Path(filename), 'r') as zf:
            entries = zf.infolist()
            if len(entries) > MAX_ENTRIES:
                return {}
            matches = []
            for item in entries:
                if item.is_dir() or (item.flag_bits & 0x1):
                    continue  # never prompt for archive passwords
                rating = rank_image(item.filename)
                if (rating < 0 or not 256 <= item.file_size <= MAX_IMAGE_SIZE or
                    item.compress_size > MAX_COMPRESSED or item.compress_size < 1 or
                    item.file_size / item.compress_size > MAX_RATIO):
                    continue
                matches.append((rating, item))
            for rating, item in sorted(matches, key=lambda p: (-p[0], p[1].file_size))[:12]:
                try:
                    with zf.open(item, 'r') as infile:
                        contents = infile.read(MAX_IMAGE_SIZE + 1)
                    if image_kind(contents):
                        return {'icon': contents,
                                'cover_quality': 'icon' if rating <= 7 else 'portrait',
                                'source': 'Artwork inside ZIP (local)'}
                except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
                    continue
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile):
        pass
    return {}
