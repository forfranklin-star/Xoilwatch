# -*- coding: utf-8 -*-
"""原油相关性打分与过滤。"""
from dataclasses import dataclass, field
from typing import Dict, List

from .keywords import KEYWORD_GROUPS


@dataclass
class Score:
    score: int = 0
    groups: List[str] = field(default_factory=list)
    hits: Dict[str, List[str]] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"score": self.score, "groups": self.groups, "hits": self.hits}


def score_text(text: str) -> Score:
    """对一段文本打分：命中某组第一个词得该组 weight 分，同组每多一个词 +1。"""
    t = (text or "").lower()
    s = Score()
    for gname, g in KEYWORD_GROUPS.items():
        matched = [term for term in g["terms"] if term.lower() in t]
        if matched:
            s.score += int(g["weight"]) + len(matched) - 1
            s.groups.append(gname)
            s.hits[gname] = matched
    return s


def is_relevant(text: str, min_score: int = 3) -> bool:
    """默认阈值 3：命中一个核心油价词，或两个次级主题，或次级+宏观即入选。"""
    return score_text(text).score >= min_score
