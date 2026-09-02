# -*- coding: utf-8 -*-
"""相关性过滤、门类归属与清单的基础测试：python -m unittest discover -s tests"""
import unittest

from oilwatch.accounts import load_accounts
from oilwatch.filter import is_relevant, score_text
from oilwatch.keywords import GROUP_SECTION
from oilwatch.sources.media_feeds import load_institutions, load_media


class TestFilter(unittest.TestCase):
    def test_core_keyword_passes(self):
        text = "Brent crude jumped after OPEC+ announced a new output cut."
        s = score_text(text)
        self.assertIn("核心油价", s.groups)
        self.assertIn("A 能源市场", s.sections)
        self.assertTrue(is_relevant(text))

    def test_chinese_text(self):
        text = "今日原油价格上涨，布伦特原油突破每桶80美元，欧佩克减产。"
        self.assertGreaterEqual(score_text(text).score, 3)
        self.assertTrue(is_relevant(text))

    def test_irrelevant_text(self):
        self.assertFalse(is_relevant("Great coffee at the office this morning."))

    def test_two_secondary_themes_pass(self):
        text = "Tanker freight rates rise as refinery runs recover in Asia."
        s = score_text(text)
        self.assertIn("航运油轮", s.groups)
        self.assertIn("库存炼厂", s.groups)
        self.assertTrue(is_relevant(text))

    def test_pure_politics_rejected(self):
        # 纯选举/政治噪音：只有政治政策组，不应入选
        text = "The president held an election rally in the capital city."
        s = score_text(text)
        self.assertEqual(s.groups, ["政治政策"])
        self.assertFalse(is_relevant(text))

    def test_war_and_politics_pass(self):
        text = ("The president announced new sanctions and missile strikes "
                "as the war over oil exports escalated.")
        s = score_text(text)
        self.assertIn("战争冲突", s.groups)
        self.assertIn("B 战争与地缘", s.sections)
        self.assertTrue(is_relevant(text))

    def test_section_mapping_complete(self):
        from oilwatch.keywords import KEYWORD_GROUPS
        for g in KEYWORD_GROUPS:
            self.assertIn(g, GROUP_SECTION)


class TestAccounts(unittest.TestCase):
    def test_load(self):
        accs = load_accounts(include_disabled=True)
        handles = [a.handle for a in accs]
        self.assertEqual(len(handles), len(set(h.lower() for h in handles)))
        self.assertIn("JavierBlas", handles)
        enabled = load_accounts()
        self.assertTrue(all(a.enabled for a in enabled))
        self.assertTrue(any(a.handle == "ReutersCommods" for a in enabled))


class TestSourcesLists(unittest.TestCase):
    def test_top30_media(self):
        media = load_media()
        self.assertEqual(len(media), 30)
        top = load_media(include_disabled=True)
        self.assertGreaterEqual(len(top), 40)
        self.assertTrue(all(m.feeds for m in top))

    def test_institutions(self):
        inst = load_institutions()
        self.assertGreaterEqual(len(inst), 10)
        names = " ".join(m.name for m in inst)
        self.assertIn("OPEC", names)
        self.assertIn("Federal Reserve", names)


if __name__ == "__main__":
    unittest.main()
