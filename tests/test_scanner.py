"""Minimal no-dependency checks, run `python tests/test_scanner.py`."""
import importlib.util, os, pathlib, tempfile, unittest
root = pathlib.Path(__file__).resolve().parents[1]
os.environ['SAC23_DATA_DIR']=tempfile.mkdtemp(prefix='sac23-test-data-')
spec=importlib.util.spec_from_file_location('game_library', root/'game_library.py')
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class GameLibraryTests(unittest.TestCase):
  def test_scene_title(self):
    s='[SuperPSX]-Rayman.Legends-CUSA00069-USA-Game-(5.05)-PS4'
    self.assertEqual(m.human_title(s),'Rayman Legends')
    self.assertEqual(m.file_platform(s,'AUTO'),'PS4')
    self.assertEqual(m.classification('Rayman.Legends-CUSA00069-Update.pkg',()),'Update')
  def test_scan_and_group(self):
    with tempfile.TemporaryDirectory() as d:
      base=pathlib.Path(d)
      game=(base/'PS4'/'Rayman Legends')
      (game/'Game').mkdir(parents=True)
      (game/'Updates').mkdir()
      (game/'DLC').mkdir()
      (game/'cover.jpg').write_bytes(b'fake image')
      (game/'Game'/'Rayman.Legends-CUSA00069-USA-Game.pkg').write_bytes(b'\0'*60)
      (game/'Updates'/'Rayman.Legends-CUSA00069-Update.pkg').write_bytes(b'\0'*20)
      (game/'DLC'/'Rayman.Legends-CUSA00069-DLC.zip').write_bytes(b'\0'*10)
      p5=(base/'PS5'/'Ratchet & Clank Rift Apart')
      p5.mkdir(parents=True)
      (p5/'Ratchet.And.Clank.Rift.Apart-PPSA01446-PS5.pkg').write_bytes(b'\0'*100)
      with m.KEY_LOCK:
        m.state['folders']=[{'path':str(base/'PS4'),'platform':'AUTO','id':'ps4'},{'path':str(base/'PS5'),'platform':'AUTO','id':'ps5'}]
        m.state['games']=[]
      m.scan_worker()
      games=m.state['games']
      self.assertEqual(len(games),2,repr(games))
      rayman=next(g for g in games if g['platform']=='PS4')
      self.assertEqual(rayman['title'],'Rayman Legends')
      self.assertEqual(rayman['game_count'],1)
      self.assertEqual(rayman['update_count'],1)
      self.assertEqual(rayman['dlc_count'],1)
      self.assertEqual(rayman['size'],90)
      self.assertEqual(len(rayman['files']),3)
      self.assertTrue(rayman['local_cover'].endswith('cover.jpg'))
      ratchet=next(g for g in games if g['platform']=='PS5')
      self.assertEqual(ratchet['title'],'Ratchet & Clank Rift Apart')

if __name__=='__main__':unittest.main()
