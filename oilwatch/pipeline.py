# -*- coding: utf-8 -*-
"""每日报告编排：抓取 -> 相关性过滤 -> 分组 -> 组装报告对象。"""
import os
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from . import accounts as accounts_mod
from . import prices as prices_mod
from .filter import score_text
from .sources import public_feeds, x_api

DEFAULT_TZ = os.environ.get("REPORT_TZ", "Asia/Tokyo")


def get_now(tz_name: str = DEFAULT_TZ) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def run(window_hours: int = 24, min_score: int = 3,
        use_x: bool = True, use_feeds: bool = True, use_prices: bool = True,
        x_token: Optional[str] = None, now: Optional[datetime] = None,
        tz_name: str = DEFAULT_TZ) -> dict:
    now = now or get_now(tz_name)
    since = now - timedelta(hours=window_hours)
    tz = ZoneInfo(tz_name)

    accounts = accounts_mod.load_accounts()
    statuses: List[dict] = []
    raw_items: List[dict] = []

    if use_x:
        token = x_token if x_token is not None else os.environ.get("X_BEARER_TOKEN")
        posts, x_status = x_api.fetch_all(accounts, since.astimezone(ZoneInfo("UTC")), token)
        raw_items.extend(posts)
        statuses.extend(x_status)

    if use_feeds:
        try:
            feed_items = public_feeds.fetch_feeds(since.astimezone(ZoneInfo("UTC")))
            raw_items.extend(feed_items)
            statuses.append({"source": "public_feeds", "ok": True,
                             "detail": f"{len(feed_items)} 条公开信源条目"})
        except Exception as exc:
            statuses.append({"source": "public_feeds", "ok": False, "detail": str(exc)[:200]})

    price_data = prices_mod.snapshot() if use_prices else None

    # 相关性过滤与打分
    kept: List[dict] = []
    for item in raw_items:
        sc = score_text(item.get("text", ""))
        if sc.score < min_score:
            continue
        item = dict(item)
        item["score"] = sc.score
        item["groups"] = sc.groups
        item["hits"] = sc.hits
        item["primary_group"] = sc.groups[0] if sc.groups else "其他"
        created = _parse_dt(item.get("created_at"))
        if created:
            item["local_time"] = created.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        else:
            item["local_time"] = ""
        kept.append(item)

    # 排序：相关分降序 -> 互动量降序 -> 时间降序
    kept.sort(key=lambda x: (
        -x["score"],
        -(x.get("likes", 0) + x.get("retweets", 0)),
        x.get("created_at") or "",
    ))

    group_counts = Counter(i["primary_group"] for i in kept)
    category_lookup = {a.handle.lower(): a.category for a in accounts}
    cat_counts = Counter(category_lookup.get(i["account"].lower(), "公开信源") for i in kept)

    acc_with_items = len({i["account"] for i in kept if i["source_type"] == "x"})
    report = {
        "schema_version": 1,
        "title": f"原油观察日报 {now.strftime('%Y-%m-%d')}",
        "report_date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": tz_name,
        "window_hours": window_hours,
        "window_start": since.isoformat(timespec="seconds"),
        "min_score": min_score,
        "prices": price_data,
        "accounts_total": len(accounts),
        "accounts_with_items": acc_with_items,
        "source_status": statuses,
        "item_count": len(kept),
        "group_counts": dict(group_counts),
        "category_counts": dict(cat_counts),
        "items": kept,
    }
    return report
