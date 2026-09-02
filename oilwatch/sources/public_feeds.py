# -*- coding: utf-8 -*-
"""免鉴权公开信源（RSS），作为 X 不可用时的兜底与补充。

- OilPrice.com：油气行业新闻
- EIA Today in Energy：美国能源署专栏
- Google News RSS：按原油关键词检索过去 1 天的中英文新闻
"""
import calendar
import html
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import quote

import feedparser

_TAG_RE = re.compile(r"<[^>]+>")

FEEDS = [
    ("OilPrice.com", "https://oilprice.com/rss/main"),
    ("EIA Today in Energy", "https://www.eia.gov/rss/todayinenergy.xml"),
    ("Google News 原油(英)",
     "https://news.google.com/rss/search?q="
     + quote("crude oil OR brent OR wti OR opec when:1d")
     + "&hl=en-US&gl=US&ceid=US:en"),
    ("Google News 原油(中)",
     "https://news.google.com/rss/search?q="
     + quote("原油 OR 油价 OR 欧佩克 when:1d")
     + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]


def _clean(text: str) -> str:
    text = _TAG_RE.sub(" ", text or "")
    return html.unescape(text).strip()


def _entry_time(entry) -> Optional[datetime]:
    tt = entry.get("published_parsed") or entry.get("updated_parsed")
    if not tt:
        return None
    return datetime.fromtimestamp(calendar.timegm(tt), tz=timezone.utc)


def fetch_feeds(since_utc: datetime, feeds=None, timeout: int = 15) -> List[dict]:
    items: List[dict] = []
    for name, url in (feeds or FEEDS):
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": "oilwatch/1.0"})
        except Exception:
            continue
        for e in parsed.entries:
            published = _entry_time(e)
            if published and published < since_utc - timedelta(hours=2):
                continue
            title = _clean(e.get("title", ""))
            summary = _clean(e.get("summary", ""))[:600]
            items.append({
                "source_type": "feed",
                "account": name,
                "account_url": url,
                "id": e.get("id") or e.get("link"),
                "created_at": published.isoformat() if published else None,
                "text": f"{title}\n{summary}".strip(),
                "title": title,
                "url": e.get("link"),
                "lang": None,
                "likes": 0, "retweets": 0, "replies": 0, "quotes": 0,
            })
    return items
