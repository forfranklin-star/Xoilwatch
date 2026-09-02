# -*- coding: utf-8 -*-
"""免 Token 镜像兜底：通过 Nitter / RSSHub 实例的 RSS 读取账号时间线。

启用方式（环境变量，可逗号分隔多个实例，按顺序尝试）：
  NITTER_BASE=https://nitter.example.com
  RSSHUB_BASE=https://rsshub.example.com
说明：
- 2024 年后公共 Nitter 实例大量关闭、RSSHub 公共实例的 twitter 路由多需自备
  凭证，稳定性远不如官方 API，本模块仅作为「尽力而为」的兜底。
- 输出结构与 x_api 对齐（source_type="x"），下游过滤/分组无需改动。
"""
import calendar
import html
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import feedparser

from .. import config

_TAG_RE = re.compile(r"<[^>]+>")
_STATUS_RE = re.compile(r"(?:status|statuses)/(\d+)")


def feed_url(kind: str, base: str, handle: str) -> str:
    if kind == "rsshub":
        return f"{base.rstrip('/')}/twitter/user/{handle}"
    return f"{base.rstrip('/')}/{handle}/rss"


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub(" ", text or "")).strip()


def _field(entry, name, default=None):
    """feedparser 条目同时支持属性与字典访问，这里统一兜底。"""
    val = getattr(entry, name, None)
    if val is None and hasattr(entry, "get"):
        val = entry.get(name)
    return val if val is not None else default


def _entry_time(entry) -> Optional[datetime]:
    tt = _field(entry, "published_parsed") or _field(entry, "updated_parsed")
    if not tt:
        return None
    return datetime.fromtimestamp(calendar.timegm(tt), tz=timezone.utc)


def _status_id(link: str, fallback: str) -> str:
    m = _STATUS_RE.search(link or "")
    return m.group(1) if m else fallback


def fetch_one(kind: str, base: str, handle: str, since_utc: datetime
              ) -> Tuple[List[dict], Optional[str]]:
    url = feed_url(kind, base, handle)
    try:
        parsed = feedparser.parse(url, request_headers={"User-Agent": "oilwatch/1.0"})
    except Exception as exc:
        return [], f"{kind} 抓取异常: {exc}"
    if getattr(parsed, "bozo", False) and not parsed.entries:
        return [], f"{kind} 实例无数据（{base}）"
    posts = []
    for e in parsed.entries:
        published = _entry_time(e)
        if published and published < since_utc - timedelta(hours=2):
            continue
        sid = _status_id(_field(e, "link", ""), _field(e, "id", ""))
        text = _clean(f"{_field(e, 'title', '')} {_field(e, 'summary', '')}")
        posts.append({
            "source_type": "x",
            "via": f"mirror:{kind}",
            "account": handle,
            "account_url": f"https://x.com/{handle}",
            "id": sid,
            "created_at": published.isoformat() if published else None,
            "text": text,
            "url": f"https://x.com/{handle}/status/{sid}",
            "lang": None,
            "retweets": 0, "replies": 0, "likes": 0, "quotes": 0,
        })
    return posts, None


def fetch_all(accounts, since_utc: datetime) -> Tuple[List[dict], List[dict]]:
    instances = config.mirror_instances()
    if not instances:
        return [], [{
            "source": "X 镜像", "ok": False,
            "detail": "未配置 X_BEARER_TOKEN，且未设置 NITTER_BASE/RSSHUB_BASE 镜像，"
                      "X 账号抓取跳过（公开新闻 RSS 仍正常）",
        }]
    posts: List[dict] = []
    statuses: List[dict] = []
    for acc in accounts:
        got, last_err = [], None
        for kind, base in instances:
            got, last_err = fetch_one(kind, base, acc.handle, since_utc)
            if got:
                break
        if got:
            posts.extend(got)
            statuses.append({"source": f"mirror:@{acc.handle}", "ok": True,
                             "detail": f"{len(got)} 条（{got[0]['via']}）"})
        else:
            statuses.append({"source": f"mirror:@{acc.handle}", "ok": False,
                             "detail": last_err or "镜像无窗口内数据"})
    ok_n = sum(1 for s in statuses if s["ok"])
    statuses.insert(0, {"source": "X 镜像汇总", "ok": ok_n > 0,
                        "detail": f"镜像实例 {len(instances)} 个，"
                                  f"{ok_n}/{len(accounts)} 个账号取到数据"})
    return posts, statuses
