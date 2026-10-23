"""Regression tests for the 125/125 report's two remaining identical-title-ID variants."""
from __future__ import annotations
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

os.environ.setdefault('SAC23_DATA_DIR', tempfile.mkdtemp(prefix='sac23-final-cover-data-'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import game_library as lib


def png():
    width, height = 64, 96
    def chunk(typ, data):
        return struct.pack('>I',len(data))+typ+data+struct.pack('>I',zlib.crc32(typ+data))
    raw=b''.join(b'\x00' + bytes(((x+y) % 255 for x in range(width*3))) for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


class FinalTwoCoverRepairTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        for field,path in [('DATA_HOME',root),('DATA_FILE',root/'library.json'),('COVER_CACHE',root/'covers')]:
            original=getattr(lib,field)
            setattr(lib,field,path)
            self.addCleanup(setattr,lib,field,original)
        original_state=lib.state
        lib.state=lib.empty_state()
        self.addCleanup(setattr,lib,'state',original_state)
        self.root=root

    def test_exact_two_missing_become_covered_without_network_or_game_file_mutation(self):
        all_games=[]
        for title,variant,tid in [
            ('Hogwarts Legacy','Hogwarts Legacy LIZARD','PPSA01603'),
            ('Marvels Spider Man Remastered','Marvels Spider Man Remastered LIZARD','PPSA01467'),
        ]:
            gid_src = lib.game_id('PS5',title,tid)
            gid_dst = lib.game_id('PS5',variant,tid)
            content = png()
            self.assertTrue(lib.cache_cover_bytes(gid_src,content,extension='.png'))
            payload_path=self.root/(tid+'.rar')
            payload_path.write_bytes(b'ARCHIVE REMAINS UNMODIFIED')
            all_games += [
                {'id':gid_src,'title':title,'title_id':tid,'platform':'PS5', 'source':'Steam'},
                {'id':gid_dst,'title':variant,'title_id':tid,'platform':'PS5',
                 'favorite':True,'trailer_url':'https://www.youtube.com/watch?v=abc12345678',
                 'files':[{'path':str(payload_path)}], 'cover_error':'old error'},
            ]
        lib.state['games']=all_games
        with mock.patch('metadata.image_bytes',side_effect=AssertionError('network forbidden')):
            repaired=lib.repair_cached_duplicate_covers()
        self.assertEqual(len(repaired),2)
        self.assertEqual({x[1] for x in repaired},{'PPSA01603','PPSA01467'})
        self.assertEqual(sum(lib.game_has_cover(x) for x in all_games),4)
        for src,target in zip(all_games[::2],all_games[1::2]):
            self.assertEqual(lib.cached_cover(src['id']).read_bytes(),lib.cached_cover(target['id']).read_bytes())
            self.assertTrue(target['favorite'])
            self.assertEqual(target['cover_error'],'')
            self.assertTrue(target['trailer_url'].startswith('https://www.youtube.com/'))
            self.assertEqual((self.root/(target['title_id']+'.rar')).read_bytes(),b'ARCHIVE REMAINS UNMODIFIED')
        self.assertEqual(lib.repair_cached_duplicate_covers(), [])
        self.assertEqual(len(json.loads(lib.DATA_FILE.read_text())['games']),4)

    def test_unknown_id_or_cross_platform_never_copies(self):
        good={'id':'1'*16,'title':'Game','title_id':'PPSA11111','platform':'PS5'}
        wrong_id={'id':'2'*16,'title':'Game Repacked','title_id':'PPSA11112','platform':'PS5'}
        wrong_platform={'id':'3'*16,'title':'Game Repacked','title_id':'PPSA11111','platform':'PS4'}
        self.assertTrue(lib.cache_cover_bytes(good['id'],png(),extension='.png'))
        lib.state['games']=[good,wrong_id,wrong_platform]
        self.assertEqual(lib.repair_cached_duplicate_covers(),[])
        self.assertFalse(lib.game_has_cover(wrong_id))
        self.assertFalse(lib.game_has_cover(wrong_platform))

    def test_do_not_override_existing_custom_art(self):
        donor={'id':'a'*16,'title':'Hogwarts Legacy','title_id':'PPSA01603','platform':'PS5'}
        existing={'id':'b'*16,'title':'Hogwarts Legacy LIZARD','title_id':'PPSA01603','platform':'PS5'}
        self.assertTrue(lib.cache_cover_bytes(donor['id'],png()))
        self.assertTrue(lib.cache_cover_bytes(existing['id'],png()))
        old=lib.cached_cover(existing['id']).read_bytes()
        lib.state['games']=[donor,existing]
        self.assertEqual(lib.repair_cached_duplicate_covers(),[])
        self.assertEqual(lib.cached_cover(existing['id']).read_bytes(),old)

if __name__ == '__main__': unittest.main()
