# -*- coding: utf-8 -*-
"""config 与 twitter_mirror 的离线测试。"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from oilwatch import config
from oilwatch.sources import twitter_mirror


class TestConfig(unittest.TestCase):
    def test_dotenv_parse(self):
        content = 'FOO_BAR="hello world"\n# comment\nBAZ=123\nexport QUX=x\n'
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False,
                                         encoding="utf-8") as f:
            f.write(content)
            path = f.name
        config._ENV_LOADED = False  # 允许重新加载
        config.load_dotenv(path)
        self.assertEqual(os.environ.get("FOO_BAR"), "hello world")
        self.assertEqual(os.environ.get("BAZ"), "123")
        self.assertEqual(os.environ.get("QUX"), "x")
        os.environ.pop("FOO_BAR", None)
        os.environ.pop("BAZ", None)
        os.environ.pop("QUX", None)

    def test_mask(self):
        self.assertEqual(config.mask(""), "")
        self.assertTrue(config.mask("AAAAAAAAAAAAAAAA1234").endswith("1234"))

    def test_mirror_instances(self):
        with mock.patch.dict(os.environ, {"NITTER_BASE": "https://a.test, https://b.test"},
                             clear=False):
            kinds = config.mirror_instances()
            self.assertIn(("nitter", "https://a.test"), kinds)
            self.assertIn(("nitter", "https://b.test"), kinds)


class TestMirror(unittest.TestCase):
    def test_feed_url(self):
        self.assertEqual(twitter_mirror.feed_url("nitter", "https://n.x/", "abc"),
                         "https://n.x/abc/rss")
        self.assertEqual(twitter_mirror.feed_url("rsshub", "https://r.x", "abc"),
                         "https://r.x/twitter/user/abc")

    def test_status_id(self):
        link = "https://n.x/JavierBlas/status/18273645/"
        self.assertEqual(twitter_mirror._status_id(link, "fb"), "18273645")
        self.assertEqual(twitter_mirror._status_id("", "fallback"), "fallback")

    def test_fetch_one_parses_entries(self):
        from datetime import datetime, timedelta, timezone
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        tt = one_hour_ago.utctimetuple()
        entry = SimpleNamespace(
            title="Brent crude jumps on OPEC cut",
            summary="<p>crude oil supply details</p>",
            link="https://n.x/acc/status/999",
            id="x", published_parsed=tt)
        fake = SimpleNamespace(entries=[entry], bozo=0)
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        with mock.patch.object(twitter_mirror.feedparser, "parse", return_value=fake):
            posts, err = twitter_mirror.fetch_one("nitter", "https://n.x", "acc", since)
        self.assertIsNone(err)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["id"], "999")
        self.assertEqual(posts[0]["source_type"], "x")
        self.assertIn("Brent crude", posts[0]["text"])


if __name__ == "__main__":
    unittest.main()
