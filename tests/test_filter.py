# -*- coding: utf-8 -*-
"""相关性打分与账号清单的基础测试：python -m unittest discover -s tests"""
import unittest

from oilwatch.accounts import load_accounts
from oilwatch.filter import is_relevant, score_text


class TestFilter(unittest.TestCase):
    def test_core_keyword_passes(self):
        text = "Brent crude jumped after OPEC+ announced a new output cut."
        s = score_text(text)
        self.assertIn("核心油价", s.groups)
        self.assertGreaterEqual(s.score, 3)
        self.assertTrue(is_relevant(text))

    def test_chinese_text(self):
        s = score_text("今日原油价格上涨，布伦特原油突破每桶80美元，欧佩克减产。")
        self.assertGreaterEqual(s.score, 3)
        self.assertTrue(is_relevant("今日原油价格上涨，布伦特原油突破每桶80美元"))

    def test_irrelevant_text(self):
        self.assertFalse(is_relevant("Great coffee at the office this morning."))

    def test_two_secondary_themes_pass(self):
        s = score_text("Tanker freight rates rise as refinery runs recover in Asia.")
        self.assertIn("航运油轮", s.groups)
        self.assertIn("库存炼厂", s.groups)
        self.assertTrue(s.score >= 3)


class TestAccounts(unittest.TestCase):
    def test_load(self):
        accs = load_accounts(include_disabled=True)
        handles = [a.handle for a in accs]
        self.assertEqual(len(handles), len(set(h.lower() for h in handles)))
        self.assertIn("JavierBlas", handles)
        enabled = load_accounts()
        self.assertTrue(all(a.enabled for a in enabled))
        # @ReutersCommods 已经用户核对确认，应处于启用状态
        self.assertTrue(any(a.handle == "ReutersCommods" for a in enabled))


if __name__ == "__main__":
    unittest.main()
