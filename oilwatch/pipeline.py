# -*- coding: utf-8 -*-
"""每日报告编排：多源抓取 -> 相关性过滤 -> 按门类分组 -> 组装报告对象。"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from . import accounts as accounts_mod, config
from . import prices as prices_mod
from .filter import score_text
from .keywords import GROUP_SECTION, SECTION_ORDER
from .sources import media_feeds, public_feeds, twitter_mirror, x_api

DEFAULT_TZ = config.get("REPORT_TZ", "Asia/Shanghai")


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
        use_x: bool = True, use_media: bool = True, use_institutions: bool = True,
        use_feeds: bool = True, use_prices: bool = True,
        x_token: Optional[str] = None, now: Optional[datetime] = None,
        tz_name: str = DEFAULT_TZ) -> dict:
    now = now or get_now(tz_name)
    since = now - timedelta(hours=window_hours)
    tz = ZoneInfo(tz_name)
    since_utc = since.astimezone(ZoneInfo("UTC"))

    accounts = accounts_mod.load_accounts()
    media_sources = media_feeds.load_media()
    inst_sources = media_feeds.load_institutions()

    statuses = []
    raw_items = []

    # 1) X 关注账号：官方 Token -> 镜像 -> 跳过
    if use_x:
        token = x_token if x_token is not None else config.x_token()
        if token:
            posts, st = x_api.fetch_all(accounts, since_utc, token)
        elif config.mirror_instances():
            posts, st = twitter_mirror.fetch_all(accounts, since_utc)
        else:
            posts, st = x_api.fetch_all(accounts, since_utc, None)
        raw_items.extend(posts)
        statuses.extend(st)

    # 2) 全球主流媒体
    if use_media:
        m_items, m_st = media_feeds.fetch_sources(media_sources, "media", since_utc)
        raw_items.extend(m_items)
        statuses.extend(m_st)

    # 3) 权威机构
    if use_institutions:
        i_items, i_st = media_feeds.fetch_sources(inst_sources, "institution", since_utc)
        raw_items.extend(i_items)
        statuses.extend(i_st)

    # 4) 公共聚合骨干（Google News/OilPrice/EIA）
    if use_feeds:
        try:
            feed_items = public_feeds.fetch_feeds(since_utc)
            raw_items.extend(feed_items)
            statuses.append({"source": "公共聚合", "ok": True,
                             "detail": f"{len(feed_items)} 条聚合条目"})
        except Exception as exc:
            statuses.append({"source": "公共聚合", "ok": False, "detail": str(exc)[:200]})

    price_data = prices_mod.snapshot() if use_prices else None

    # 5) 相关性过滤与打分（按标题去重，多媒体可能重复报道同一新闻）
    kept = []
    dedup_titles = set()
    for item in raw_items:
        sc = score_text(item.get("text", ""))
        if sc.score < min_score:
            continue
        if not any(g != "政治政策" for g in sc.groups):
            continue  # 纯政治噪音不入选
        title_key = (item.get("title") or item.get("text", ""))[:60].lower()
        if title_key and title_key in dedup_titles:
            continue
        dedup_titles.add(title_key)
        item = dict(item)
        item["score"] = sc.score
        item["groups"] = sc.groups
        item["sections"] = sc.sections
        item["hits"] = sc.hits
        item["primary_group"] = sc.groups[0]
        item["primary_section"] = GROUP_SECTION.get(item["primary_group"], "其他")
        created = _parse_dt(item.get("created_at"))
        item["local_time"] = (created.astimezone(tz).strftime("%m-%d %H:%M")
                              if created else "")
        kept.append(item)

    kept.sort(key=lambda x: (
        -x["score"],
        -(x.get("likes", 0) + x.get("retweets", 0)),
        x.get("created_at") or "",
    ))

    section_counts = Counter(i["primary_section"] for i in kept)
    group_counts = Counter(i["primary_group"] for i in kept)
    type_counts = Counter(i["source_type"] for i in kept)
    outlet_counts = Counter(i["account"] for i in kept)

    report = {
        "schema_version": 2,
        "title": f"原油观察日报 {now.strftime('%Y-%m-%d')}",
        "report_date": now.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": tz_name,
        "window_hours": window_hours,
        "window_start": since.isoformat(timespec="seconds"),
        "min_score": min_score,
        "prices": price_data,
        "accounts_total": len(accounts),
        "media_total": len(media_sources),
        "institutions_total": len(inst_sources),
        "source_status": statuses,
        "item_count": len(kept),
        "section_counts": {s: section_counts.get(s, 0) for s in SECTION_ORDER},
        "group_counts": dict(group_counts),
        "type_counts": dict(type_counts),
        "top_outlets": outlet_counts.most_common(10),
        "items": kept,
    }
    return report
