# -*- coding: utf-8 -*-
"""X(Twitter) API v2 抓取。

需要在环境变量中配置 X_BEARER_TOKEN（X Developer Portal 的 Bearer Token，
至少 Basic 级以上套餐才可读取用户时间线）。未配置 token 时优雅降级，
返回空结果与状态说明，由公开信源(public_feeds)兜底。
"""
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

API_ROOT = "https://api.twitter.com/2"
_USER_FIELDS = "tweet.fields=created_at,lang,public_metrics,entities&exclude=retweets,replies"


class XClient:
    def __init__(self, bearer_token: str, timeout: int = 20):
        self.token = bearer_token
        self.timeout = timeout
        self._id_cache: Dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {bearer_token}"

    def _get(self, url: str, params: Optional[dict] = None) -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            return None, f"网络错误: {exc}"
        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset")
            return None, f"触发限流(429)，reset={reset}"
        if resp.status_code in (401, 403):
            return None, f"鉴权失败({resp.status_code})，请检查 X_BEARER_TOKEN 与套餐权限"
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        try:
            return resp.json(), None
        except ValueError as exc:
            return None, f"响应解析失败: {exc}"

    def user_id(self, handle: str) -> Tuple[Optional[str], Optional[str]]:
        if handle in self._id_cache:
            return self._id_cache[handle], None
        data, err = self._get(f"{API_ROOT}/users/by/username/{handle}")
        if err:
            return None, err
        if not data or "data" not in data:
            return None, f"未找到账号 @{handle}"
        uid = data["data"]["id"]
        self._id_cache[handle] = uid
        return uid, None

    def user_tweets(self, handle: str, since_utc: datetime,
                    max_results: int = 40) -> Tuple[List[dict], Optional[str]]:
        uid, err = self.user_id(handle)
        if err:
            return [], err
        params = {
            "max_results": min(max(max_results, 5), 100),
            "start_time": since_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        url = f"{API_ROOT}/users/{uid}/tweets?{_USER_FIELDS}"
        data, err = self._get(url, params=params)
        if err:
            return [], err
        posts = []
        for tw in (data or {}).get("data", []) or []:
            metrics = tw.get("public_metrics", {}) or {}
            posts.append({
                "source_type": "x",
                "account": handle,
                "account_url": f"https://x.com/{handle}",
                "id": tw.get("id"),
                "created_at": tw.get("created_at"),
                "text": tw.get("text", ""),
                "url": f"https://x.com/{handle}/status/{tw.get('id')}",
                "lang": tw.get("lang"),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "likes": metrics.get("like_count", 0),
                "quotes": metrics.get("quote_count", 0),
            })
        return posts, None


def fetch_all(accounts, since_utc: datetime, bearer_token: Optional[str],
              pause: float = 0.6) -> Tuple[List[dict], List[dict]]:
    """批量抓取。返回 (posts, statuses)，statuses 记录每个账号成功/失败原因。"""
    if not bearer_token:
        return [], [{
            "source": "X API", "ok": False,
            "detail": "未配置 X_BEARER_TOKEN，跳过 X 抓取（仅使用公开信源）",
        }]
    client = XClient(bearer_token)
    posts: List[dict] = []
    statuses: List[dict] = []
    for i, acc in enumerate(accounts):
        user_posts, err = client.user_tweets(acc.handle, since_utc)
        if err:
            statuses.append({"source": f"x:@{acc.handle}", "ok": False, "detail": err})
        else:
            posts.extend(user_posts)
            statuses.append({
                "source": f"x:@{acc.handle}", "ok": True,
                "detail": f"{len(user_posts)} 条窗口内推文",
            })
        if i < len(accounts) - 1:
            time.sleep(pause)
    return posts, statuses
