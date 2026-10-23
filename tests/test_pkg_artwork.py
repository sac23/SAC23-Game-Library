"""Offline integration tests: actual public game icon, fallback downloads, and safety."""
from unittest import TestCase, mock
from pathlib import Path
import tempfile, os, struct, zlib, sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
os.environ['SAC23_DATA_DIR'] = tempfile.mkdtemp(prefix='sac23-v21-test-')
sys.path.insert(0, str(ROOT))
import game_library as lib
import pkg_art
import metadata


def tiny_png():
    w, h = 128, 128
    # A real PNG, not a signature-only mocked image.
    scanlines = b''.join(b'\x00' + bytes(value for x in range(w) for value in ((x + y) % 256, (x * 3) % 256, (y * 7) % 256)) for y in range(h))
    def chunk(name, body):
        return struct.pack('>I', len(body)) + name + body + struct.pack('>I', zlib.crc32(name + body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


def sfo_bytes():
    keys = b'TITLE\0TITLE_ID\0'
    values = [b'Marvel Spider-Man Remastered\0', b'CUSA00123\0']
    key_offset = 20 + 16 * 2
    value_offset = key_offset + len(keys)
    entry1 = struct.pack('<HHIII', 0, 0x204, len(values[0]), len(values[0]), 0)
    entry2 = struct.pack('<HHIII', 6, 0x204, len(values[1]), len(values[1]), len(values[0]))
    return struct.pack('<5I', 0x46535000, 0x101, key_offset, value_offset, 2) + entry1 + entry2 + keys + b''.join(values)


def make_pkg(path):
    icon, sfo = tiny_png(), sfo_bytes()
    items = [(0x1000, 0x300, sfo), (0x1200, 0x900, icon)]
    buf = bytearray(0x900 + len(icon) + 100)
    buf[:4] = b'\x7fCNT'
    struct.pack_into('>I', buf, 0x10, 2)
    struct.pack_into('>I', buf, 0x18, 0x200)
    for i, (item_id, pos, data) in enumerate(items):
        struct.pack_into('>6I', buf, 0x200+i*32, item_id, 0, 0, 0, pos, len(data))
        buf[pos:pos+len(data)] = data
    path.write_bytes(buf)
    return icon


class PkgArtworkTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / 'covers'
        self.old_cache, lib.COVER_CACHE = lib.COVER_CACHE, self.cache
        self.addCleanup(setattr, lib, 'COVER_CACHE', self.old_cache)

    def test_pkg_icon_and_real_title_read_without_modifying_pkg(self):
        path = Path(self.temp.name)/'MARVEL.SPIDER.MAN.CUSA00123.pkg'
        icon = make_pkg(path)
        unchanged = path.read_bytes()
        data = pkg_art.read_ps4_pkg_details(path)
        self.assertEqual(data['title'], 'Marvel Spider-Man Remastered')
        self.assertEqual(data['title_id'], 'CUSA00123')
        self.assertEqual(data['icon'], icon)
        self.assertEqual(path.read_bytes(), unchanged)

    def test_pkg_embedded_icon_survives_all_online_sources_failing(self):
        path = Path(self.temp.name)/'MARVEL.SPIDER.MAN.CUSA00123.pkg'
        make_pkg(path)
        g = {'id': '0abcdef123456789', 'title': 'Collection English 4', 'platform': 'PS4',
             'files': [{'path': str(path), 'category': 'Game'}]}
        with mock.patch('metadata.find_libretro_cover', side_effect=OSError('no connection')), \
             mock.patch('metadata.find_steam_art', side_effect=OSError('no connection')):
            r = lib.lookup_enrichment(g, {'auto_trailers': False, 'wiki_fallback': False})
        self.assertTrue(r['cover_cached'])
        self.assertTrue(lib.cached_cover(g['id']).is_file())
        self.assertEqual(r['identified_title'], 'Marvel Spider-Man Remastered')
        self.assertTrue(r['cover_error'])
        self.assertEqual(r['cover_quality'], 'icon')

    def test_online_cover_download_cached_not_just_a_broken_url(self):
        g = {'id': '1234567890abcdef', 'title': 'Elden Ring', 'platform': 'PS5',
             'cover_url': 'https://invalid.example/404.jpg', 'files': []}
        png = tiny_png()
        with mock.patch('metadata.find_steam_art', return_value={
             'cover_candidates': ['https://static.example/elden-ring.png'], 'source': 'Steam',
             'matched_name': 'Elden Ring'}), mock.patch('metadata.image_bytes', side_effect=[
              ValueError('HTTP 404'), (png, '.png')]):
            r = lib.lookup_enrichment(g, {'auto_trailers': False, 'wiki_fallback': False})
        self.assertTrue(r['cover_cached'])
        self.assertEqual(lib.cached_cover(g['id']).read_bytes(), png)
        self.assertEqual(r['source'], 'Steam')
        self.assertTrue(lib.game_has_cover(g))

    def test_v2_recent_failure_still_retried_and_remote_url_not_counted(self):
        g = {'id': 'abcdef1234567890', 'title': 'Unknown', 'platform': 'PS4',
             'artwork_v2_checked': datetime.now().astimezone().isoformat(),
             'cover_url': 'https://invalid.example/404.jpg'}
        self.assertTrue(lib.needs_enrichment(g))
        self.assertFalse(lib.game_has_cover(g))

    def test_malformed_pkg_is_noop(self):
        path = Path(self.temp.name)/'broken.pkg'
        path.write_bytes(b'not a playstation package')
        self.assertEqual(pkg_art.read_ps4_pkg_details(path), {})

if __name__ == '__main__':
    import unittest
    unittest.main()
