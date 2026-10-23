"""Verify local HTTP server host/origin protection."""
import os, pathlib, sys, tempfile, unittest
from types import SimpleNamespace
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
os.environ.setdefault('SAC23_DATA_DIR', tempfile.mkdtemp(prefix='sac23-http-security-'))
from game_library import Handler

class LocalSecurityTests(unittest.TestCase):
    def handler(self, headers):
        h = object.__new__(Handler)
        h.server = SimpleNamespace(server_address=('127.0.0.1', 49182))
        h.headers = headers
        return h
    def test_good_local_host(self):
        self.assertIsNone(self.handler({'Host':'127.0.0.1:49182'}).local_request_error())
    def test_bad_host(self):
        self.assertIsNotNone(self.handler({'Host':'evil.example:49182'}).local_request_error())
    def test_good_local_post(self):
        self.assertIsNone(self.handler({'Host':'localhost:49182','Origin':'http://localhost:49182','Content-Type':'application/json'}).local_request_error(True))
    def test_external_origin_rejected(self):
        self.assertIsNotNone(self.handler({'Host':'127.0.0.1:49182','Origin':'https://evil.example','Content-Type':'application/json'}).local_request_error(True))
    def test_form_post_rejected(self):
        self.assertIsNotNone(self.handler({'Host':'127.0.0.1:49182','Content-Type':'text/plain'}).local_request_error(True))
