"""Offline regression tests for the 21 report-specific artwork fixes in v2.3."""
import os
import sys
import struct
import tempfile
import zlib
from pathlib import Path
from unittest import TestCase, mock

BASE = Path(__file__).resolve().parents[1]
os.environ.setdefault('SAC23_DATA_DIR', tempfile.mkdtemp(prefix='sac23-v23-tests-'))
sys.path.insert(0, str(BASE))
import artwork_rescue as rescue
import game_library as lib
import metadata


def png():
    w, h = 256, 384
    def chunk(name, body):
        return (struct.pack('>I', len(body)) + name + body +
                struct.pack('>I', zlib.crc32(name + body)))
    pixel = b'\x00' + b'\x40\x50\x60' * w
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w,h,8,2,0,0,0)) +
            chunk(b'IDAT', zlib.compress(pixel*h)) + chunk(b'IEND', b''))


# Report supplied on 2026-10-20; all names represent game-artwork queries,
# not files, directories, or paths to be downloaded or altered.
REPORT_MISSING = [
    ('Assassins Creed Black Flag Resynced', ''),
    ('Call of Duty Black Ops II incl', ''),
    ('Call of Duty Black Ops incl', ''),
    ('Call of Duty Modern Warfare 3 PROPER', 'PPSA01649'),
    ('Cyberpunk 2077 120 000 4 xx+', 'PPSA04029'),
    ('EA SPORTS FC 27', ''),
    ('Far Cry 6 of the Year Edition', ''),
    ('God of War III Remastered Playable', ''),
    ('God Of War Ragnarok incl', 'PPSA08331'),
    ('God of War Sons of Sparta Deluxe Edition only', 'PPSA28997'),
    ('God of War Sons of Sparta PROOPER', 'PPSA28997'),
    ('Halo Campaign Evolved Premium Edition', ''),
    ('Hogwarts Legacy LIZARD', 'PPSA01603'),
    ('Horizon Forbidden West Complete Edition incl', ''),
    ('LEGO Party', 'PPSA29141'),
    ('Marvels Spider Man Miles Morales incl', ''),
    ('Marvels Spider Man Remastered LIZARD', 'PPSA01467'),
    ('Marvels Wolverine', 'PPSA03671'),
    ('METAL GEAR SOLID V GROUND ZEROES', 'CUSA00218'),
    ('Ready or Not Deluxe Edition', 'PPSA18605'),
    ('Resident Evil 4 Remake LIZARD', 'PPSA07411'),
]


class V23ArtworkTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.original_cache = lib.COVER_CACHE
        lib.COVER_CACHE = self.root / 'covers'
        self.addCleanup(setattr, lib, 'COVER_CACHE', self.original_cache)
        self.original_state = lib.state
        lib.state = {**lib.empty_state(), 'games': []}
        self.addCleanup(setattr, lib, 'state', self.original_state)

    def test_all_21_missing_titles_have_exact_official_source_and_direct_image(self):
        self.assertEqual(len(REPORT_MISSING), 21)
        for title, title_id in REPORT_MISSING:
            with self.subTest(title=title):
                game = {'title': title, 'title_id': title_id, 'platform': 'PS5'}
                key = rescue.verified_match(game)
                self.assertIn(key, rescue.VERIFIED_SOURCES)
                urls = rescue.direct_verified_cover(game)
                self.assertTrue(urls.get('cover_candidates'))
                self.assertTrue(all(u.startswith('https://image.api.playstation.com/') for u in urls['cover_candidates']))

    def test_black_ops_2_never_borrows_black_ops_1_artwork(self):
        one = {'id': 'a'*16,'title': 'Call of Duty Black Ops incl','platform': 'PS5'}
        two = {'id': 'b'*16,'title': 'Call of Duty Black Ops II incl','platform': 'PS5'}
        self.assertNotEqual(rescue.verified_match(one), rescue.verified_match(two))
        self.assertEqual(rescue.matching_cover_games(two, [one]), [])

    def test_covered_same_title_id_is_reused_without_online_network_or_modifying_files(self):
        previous = {'id':'a'*16,'title':'Hogwarts Legacy','platform':'PS5',
                    'title_id':'PPSA01603','files':[],'cover_quality':'portrait'}
        missing = {'id':'b'*16,'title':'Hogwarts Legacy LIZARD','platform':'PS5',
                   'title_id':'PPSA01603','files':[],'favorite':True}
        pkg = self.root / 'base-game.pkg'
        pkg.write_bytes(b'not modified')
        missing['files'] = [{'path': str(pkg), 'category':'Game'}]
        lib.state['games'] = [previous, missing]
        self.assertTrue(lib.cache_cover_bytes(previous['id'], png()))
        with mock.patch.object(metadata,'image_bytes', side_effect=AssertionError('must use cached art')):
            with mock.patch.object(lib,'find_embedded_pkg_art', return_value={}):
                ret = lib.lookup_enrichment(missing, lib.state['settings'], artwork_only=True)
        self.assertTrue(ret['cover_cached'])
        self.assertEqual(ret['source'], 'Shared existing artwork')
        self.assertTrue(lib.cached_cover(missing['id']).is_file())
        self.assertEqual(lib.cached_cover(missing['id']).read_bytes(), png())
        self.assertEqual(pkg.read_bytes(), b'not modified')
        self.assertTrue(missing['favorite'])

    def test_edition_same_base_reuses_same_existing_artwork(self):
        covered = {'id':'a'*16,'title':'Far Cry 6','platform':'PS5','files':[],'cover_quality':'portrait'}
        missing = {'id':'b'*16,'title':'Far Cry 6 of the Year Edition','platform':'PS5','files':[]}
        lib.state['games'] = [covered, missing]
        self.assertTrue(lib.cache_cover_bytes(covered['id'], png()))
        with mock.patch.object(metadata,'image_bytes',side_effect=AssertionError('no network')):
            result = lib.lookup_enrichment(missing, lib.state['settings'], artwork_only=True)
        self.assertEqual(result['source'], 'Shared existing artwork')
        self.assertTrue(lib.cached_cover(missing['id']).is_file())

    def test_a_verified_sony_image_is_written_to_cache_and_reported(self):
        game = {'id':'c'*16,'title':'Metal Gear Solid V Ground Zeroes',
                'title_id':'CUSA00218','platform':'PS4','files':[]}
        with mock.patch.object(metadata,'image_bytes', return_value=(png(),'.png')) as download:
            result=lib.lookup_enrichment(game, lib.state['settings'], artwork_only=True)
        self.assertTrue(download.called)
        self.assertIn('image.api.playstation.com', download.call_args.args[0])
        self.assertTrue(result['cover_cached'])
        self.assertEqual(result['source'],'Verified PlayStation Store artwork')
        self.assertEqual(lib.cached_cover(game['id']).read_bytes(),png())

    def test_broken_official_url_not_counted_as_downloaded_cover(self):
        game={'id':'d'*16,'title':'Marvels Wolverine','platform':'PS5','files':[]}
        with mock.patch.object(metadata,'image_bytes',side_effect=OSError('HTTP 404')):
            with mock.patch.object(rescue,'fetch_official_images',side_effect=OSError('HTTP 429')):
                with mock.patch.object(metadata,'find_steam_art',return_value={}):
                    with mock.patch.object(metadata,'find_gog_cover',return_value={}):
                        result=lib.lookup_enrichment(game, {**lib.state['settings'],'wiki_fallback':False}, artwork_only=True)
        self.assertFalse(lib.game_has_cover(game))
        self.assertFalse(result.get('cover_cached'))
        self.assertIn('HTTP 404',result['cover_error'])

    def test_manually_chosen_cover_is_never_replaced(self):
        game={'id':'e'*16,'title':'Marvels Wolverine','platform':'PS5','files':[]}
        local=self.root/'personal.jpg'
        local.write_bytes(b'\xff\xd8\xff'+b'J'*1024)
        game['custom_cover']=str(local)
        with mock.patch.object(metadata,'image_bytes',side_effect=AssertionError('must not download')):
            with mock.patch.object(rescue,'fetch_official_images',side_effect=AssertionError('must not fetch')):
                result=lib.lookup_enrichment(game,{**lib.state['settings'],'wiki_fallback':False}, artwork_only=True)
        self.assertFalse(result.get('cover_cached'))
        self.assertEqual(local.read_bytes(), b'\xff\xd8\xff'+b'J'*1024)

    def test_site_html_parser_ignores_unrelated_images_and_untrusted_hosts(self):
        html = '''<img alt="Other game" src="https://image.api.playstation.com/vulcan/ap/rnd/xxx.png" />
        <img alt="Hogwarts Legacy" src="https://bad.example.com/x.jpg" />
        <img alt="Hogwarts Legacy" src="https://image.api.playstation.com/vulcan/ap/rnd/202208/0921/cover.png?thumb=true&w=54" />'''
        self.assertEqual(rescue.parse_official_images(html,'Hogwarts Legacy'),
                         ['https://image.api.playstation.com/vulcan/ap/rnd/202208/0921/cover.png'])

    def test_sony_image_url_cleaned_not_any_malicious_redirect(self):
        self.assertEqual(rescue._sanitize_sony_url('https://evil.example/cover.jpg'), '')
        url='https://image.api.playstation.com/vulcan/ap/rnd/2022/artwork.jpg?thumb=true&w=48'
        self.assertEqual(rescue._sanitize_sony_url(url),url.split('?')[0])
