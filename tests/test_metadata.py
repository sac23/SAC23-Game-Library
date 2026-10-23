"""Offline tests: artwork title matching, trailer HTML, and cache validation."""
import importlib.util
from unittest import mock
import json
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
os.environ['SAC23_DATA_DIR'] = tempfile.mkdtemp(prefix='sac23-v2-test-')
import sys
sys.path.insert(0, str(HERE))
import game_library as lib
import metadata


class MetadataTests(unittest.TestCase):
    def test_matches_exact_game_not_sequel(self):
        self.assertEqual(metadata.similarity('Elden Ring', 'ELDEN RING'), 1.0)
        self.assertGreater(metadata.similarity('Cyberpunk 2077', 'Cyberpunk 2077'), .99)
        self.assertLess(metadata.similarity('Far Cry 6', 'Far Cry 5'), .78)

    def test_public_steam_search_without_key(self):
        matches = {'items': [
            {'name': 'Elden Ring Nightreign', 'id': 2622380, 'type': 'app'},
            {'name': 'ELDEN RING', 'id': 1245620, 'type': 'app'},
        ]}
        with mock.patch('metadata.get_json', return_value=matches) as mocked:
            result = metadata.find_steam_art('Elden Ring')
        self.assertTrue(mocked.called)
        self.assertIn('/1245620/', result['cover_candidates'][0])
        self.assertEqual(result['source'], 'Steam')

    def test_youtube_result_parsing_ranks_official_trailer(self):
        data = {'contents': [{'videoRenderer': {
            'videoId': 'abcdefghi01', 'title': {'runs': [{'text': 'Elden Ring funny reaction'}]},
            'ownerText': {'runs': [{'text': 'Fan Channel'}]}
        }}, {'videoRenderer': {
            'videoId': 'abcdefghi02',
            'title': {'runs': [{'text': 'ELDEN RING - Official Launch Trailer'}]},
            'ownerText': {'runs': [{'text': 'BANDAI NAMCO Entertainment'}]}
        }}]}
        html = '<script>var ytInitialData = ' + json.dumps(data) + ';</script>'
        self.assertEqual(metadata.parse_youtube_search(html, 'Elden Ring'), 'abcdefghi02')

    def test_image_cache_never_touches_game_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib.COVER_CACHE = Path(tmp) / 'cache'
            gamefile = Path(tmp) / 'Elden Ring.pkg'
            gamefile.write_bytes(b'original package, untouched')
            jpg = b'\xff\xd8\xff' + b'x' * 6000
            with mock.patch('metadata.image_bytes', return_value=(jpg, '.jpg')):
                ok = lib.cache_cover_urls('1234567890abcdef', ['https://example.org/cover.jpg'])
            self.assertTrue(ok)
            self.assertTrue(lib.cached_cover('1234567890abcdef').is_file())
            self.assertEqual(gamefile.read_bytes(), b'original package, untouched')

    def test_legacy_settings_upgrade_keeps_api_keys(self):
        base = lib.empty_state()
        self.assertTrue(base['settings']['auto_artwork'])
        self.assertTrue(base['settings']['auto_trailers'])
        self.assertIn('steamgriddb_key', base['settings'])

if __name__ == '__main__':
    unittest.main()
