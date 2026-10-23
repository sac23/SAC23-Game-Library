"""Offline regression tests for artwork rescue in v2.2."""
import os
import sys
import struct
import tempfile
import zipfile
import zlib
from pathlib import Path
from unittest import TestCase, mock

BASE = Path(__file__).resolve().parents[1]
os.environ.setdefault('SAC23_DATA_DIR', tempfile.mkdtemp(prefix='sac23-v22-data-'))
sys.path.insert(0, str(BASE))
import archive_art
import game_library as lib
import metadata


def cover_png():
    w, h = 256, 384
    def chunk(typ, body):
        return struct.pack('>I', len(body)) + typ + body + struct.pack('>I', zlib.crc32(typ + body))
    pixels = b''.join(b'\0' + (bytes([y % 255, 40, 80]) * w) for y in range(h))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w,h,8,2,0,0,0)) + chunk(b'IDAT',zlib.compress(pixels)) + chunk(b'IEND',b'')


class CoverRescueTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        previous = lib.COVER_CACHE
        lib.COVER_CACHE = Path(self.temp.name) / 'covers'
        self.addCleanup(setattr, lib, 'COVER_CACHE', previous)

    def test_zip_art_is_found_without_unpacking_archive(self):
        target = Path(self.temp.name) / 'Elden Ring.zip'
        cover = cover_png()
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('ELDEN_RING/cover.png', cover)
            z.writestr('ELDEN_RING/file.pkg', b'THIS MUST NEVER GET EXTRACTED')
        unchanged = target.read_bytes()
        found = archive_art.read_zip_cover(target)
        self.assertEqual(found['icon'], cover)
        self.assertEqual(found['cover_quality'], 'portrait')
        self.assertEqual(target.read_bytes(), unchanged)
        self.assertFalse((Path(self.temp.name) / 'ELDEN_RING').exists())

    def test_zip_cover_fallback_wins_when_online_sources_all_fail(self):
        target = Path(self.temp.name) / 'Horizon Forbidden West.zip'
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('Horizon Forbidden West/sce_sys/icon0.png', cover_png())
        g = {'id':'55aa55aa55aa55aa','title':'Horizon Forbidden West',
             'platform':'PS5','files':[{'path':str(target), 'category':'Game'}]}
        with mock.patch('metadata.find_steam_art', side_effect=OSError('offline')), \
             mock.patch('metadata.find_gog_cover', side_effect=OSError('offline')):
            result = lib.lookup_enrichment(g, {'auto_trailers':False, 'wiki_fallback':False}, artwork_only=True)
        self.assertTrue(result['cover_cached'])
        self.assertTrue(lib.game_has_cover(g))
        self.assertEqual(result['source'], 'Artwork inside ZIP (local)')
        self.assertEqual(result['cover_quality'], 'icon')

    def test_gog_match_must_be_exact_enough(self):
        with mock.patch('metadata.get_json', return_value={'products':[
            {'title':'The Last of Us Part I', 'covers':{'vertical':'https://images.example/last1.jpg'}},
            {'title':'The Last of Us Part II', 'covers':{'vertical':'https://images.example/last2.jpg'}}
        ]}):
            chosen = metadata.find_gog_cover('The Last of Us Part II')
            self.assertEqual(chosen['matched_name'], 'The Last of Us Part II')
            self.assertEqual(chosen['cover_candidates'][0], 'https://images.example/last2.jpg')
            self.assertEqual(metadata.find_gog_cover('The Last of Us Part III'), {})

    def test_only_missing_skips_covered_games_and_preserves_existing(self):
        gid_a, gid_b = 'aaaa5555aaaa5555', 'bbbb6666bbbb6666'
        self.assertTrue(lib.cache_cover_bytes(gid_a, cover_png(), '.png'))
        games = [
            {'id':gid_a,'title':'Already Covered','platform':'PS4','files':[], 'favorite':True},
            {'id':gid_b,'title':'Needs Art','platform':'PS5','files':[]},
        ]
        previous = lib.state
        lib.state = {**lib.empty_state(), 'games':games}
        self.addCleanup(setattr, lib, 'state', previous)
        attempts = []
        def fake_lookup(game, artwork_only=False):
            attempts.append((game['title'], artwork_only))
            return {'cover_error':'Not in public sources'}
        with mock.patch.object(lib, 'enrich_one', side_effect=fake_lookup):
            lib.enrich_worker(force=True, missing_only=True, artwork_only=True)
        self.assertEqual(attempts, [('Needs Art', True)])
        self.assertTrue(games[0]['favorite'])
        self.assertTrue(lib.game_has_cover(games[0]))

    def test_batch_cover_inbox_matches_cusa_id_and_reuses_local_art(self):
        cache = Path(self.temp.name) / 'covers'
        inbox = Path(self.temp.name) / 'Cover Inbox'
        inbox.mkdir()
        original_inbox = lib.ARTWORK_INBOX
        lib.ARTWORK_INBOX = inbox
        self.addCleanup(setattr, lib, 'ARTWORK_INBOX', original_inbox)
        photo = inbox / 'CUSA00900.png'
        photo.write_bytes(cover_png())
        game = {'id':'1212121212121212','title':'Weird Collection English',
                'title_id':'CUSA00900','platform':'PS4'}
        self.assertTrue(lib.import_inbox_cover(game))
        self.assertEqual(lib.cached_cover(game['id']).read_bytes(), cover_png())
        self.assertTrue(photo.is_file())
        self.assertTrue(lib.game_has_cover(game))

    def test_malformed_zip_is_ignored(self):
        filename = Path(self.temp.name) / 'bad.zip'
        filename.write_bytes(b'not a zip file')
        self.assertEqual(archive_art.read_zip_cover(filename), {})
