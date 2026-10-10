import hashlib
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import szu_autologin as app  # noqa: E402


class JsonpTests(unittest.TestCase):
    def test_parse_callback(self):
        self.assertEqual(app.parse_jsonp('dr123({"result":1})'), {"result": 1})

    def test_parse_plain_json(self):
        self.assertEqual(app.parse_jsonp('{"result":"ok"}'), {"result": "ok"})

    def test_invalid_jsonp(self):
        with self.assertRaises(app.PortalError):
            app.parse_jsonp("not valid")

    def test_result_helpers(self):
        self.assertTrue(app.result_ok(1))
        self.assertTrue(app.result_ok("1"))
        self.assertTrue(app.result_ok("ok"))
        self.assertFalse(app.result_ok(0))


class PasswordTests(unittest.TestCase):
    def test_password_cut_front(self):
        password = "abcdefghijklmnopqrstuvwxyz"
        self.assertEqual(
            app.EportalClient._prepare_password(password, {"password_cut": 1}),
            password[:8],
        )

    def test_password_cut_back(self):
        password = "abcdefghijklmnopqrstuvwxyz"
        self.assertEqual(
            app.EportalClient._prepare_password(password, {"password_cut": 2}),
            password[-8:],
        )

    def test_md5_mode_matches_portal_layout(self):
        password = "password"
        expected = hashlib.md5(("1" + password + "12345678").encode()).hexdigest()
        self.assertEqual(
            app.EportalClient._prepare_password(password, {"en_md5": 1}),
            expected + "12345678" + "1",
        )


class ConfigTests(unittest.TestCase):
    def test_write_and_read_private_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            value = {"username": "student", "password": "secret"}
            app.write_private_json(path, value)
            self.assertEqual(app.read_json_file(path), value)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), value)

    def test_timeout_precedence(self):
        args = Namespace(timeout=None)
        self.assertEqual(app.select_timeout(args, {"timeout": 9}), 9.0)
        args = Namespace(timeout=3)
        self.assertEqual(app.select_timeout(args, {"timeout": 9}), 3.0)


if __name__ == "__main__":
    unittest.main()
