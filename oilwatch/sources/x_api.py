# -*- coding: utf-8 -*-
"""X(Twitter) API v2 抓取。

认证与接入方式（三选一，自动识别）：
1. 官方 API：环境变量 X_BEARER_TOKEN（X Developer Portal，按次付费读取）。
2. v2 兼容网关：另设 X_API_BASE 指向网关根（需包含 /2），必要时用
   X_API_EXTRA_HEADERS 传 JSON 格式的额外请求头。
3. 无 Token 时由 twitter_mirror 走 Nitter/RSSHub 镜像兜底。

用户名→用户ID 的映射持久缓存到 data/x_user_ids.json，避免重复付费查询。
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from .. import config
from ..accounts import ROOT

ID_CACHE_FILE = ROOT / "data" / "x_user_ids.json"
_TWEET_FIELDS = ("tweet.fields=created_at,lang,public_metrics,entities"
                 "&exclude=retweets,replies")


class XClient:
    def __init__(self, bearer_token: Optional[str] = None,
                 base_url: Optional[str] = None, timeout: int = 20):
        self.token = bearer_token if bearer_token is not None else config.x_token()
        self.base = (base_url or config.get("X_API_BASE")
                     or "https://api.twitter.com/2").rstrip("/")
        self.timeout = timeout
        self._id_cache = self._load_id_cache()
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"
        extra = config.get("X_API_EXTRA_HEADERS")
        if extra:
            try:
                self.session.headers.update(json.loads(extra))
            except json.JSONDecodeError:
                pass

    # ---------------------------------------------------------- ID 缓存
    def _load_id_cache(self) -> Dict[str, str]:
        if ID_CACHE_FILE.exists():
            try:
                return json.loads(ID_CACHE_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_id_cache(self) -> None:
        ID_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        ID_CACHE_FILE.write_text(
            json.dumps(self._id_cache, ensure_ascii=False, indent=2),
            encoding="utf-8")

    # ---------------------------------------------------------- HTTP
    def _get(self, url: str, params: Optional[dict] = None
             ) -> Tuple[Optional[dict], Optional[str]]:
        if not self.token:
            return None, "缺少 X_BEARER_TOKEN"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            return None, f"网络错误: {exc}"
        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset")
            return None, f"触发限流(429)，reset={reset}"
        if resp.status_code in (401, 403):
            return None, (f"鉴权失败({resp.status_code})：Token 无效/过期，"
                          f"或当前套餐无读取权限（免费套餐不能读时间线）")
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:200]}"
        try:
            return resp.json(), None
        except ValueError as exc:
            return None, f"响应解析失败: {exc}"

    def verify_token(self) -> Tuple[bool, str]:
        """调用 /2/users/me 校验 Token 是否有效。"""
        data, err = self._get(f"{self.base}/users/me",
                              params={"user.fields": "username,name,id"})
        if err:
            return False, err
        me = (data or {}).get("data", {})
        return True, f"有效，认证账号 @{me.get('username')}（{me.get('name')}）"

    def user_id(self, handle: str) -> Tuple[Optional[str], Optional[str]]:
        if handle in self._id_cache:
            return self._id_cache[handle], None
        data, err = self._get(f"{self.base}/users/by/username/{handle}")
        if err:
            return None, err
        if not data or "data" not in data:
            return None, f"未找到账号 @{handle}"
        uid = data["data"]["id"]
        self._id_cache[handle] = uid
        self._save_id_cache()
        return uid, None

    def user_tweets(self, handle: str, since_utc: datetime,
                    max_results: int = 40) -> Tuple[List[dict], Optional[str]]:
        uid, err = self.user_id(handle)
        if err:
            return [], err
        params = {
            "max_results": min(max(max_results, 5), 100),
            "start_time": since_utc.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
        }
        url = f"{self.base}/users/{uid}/tweets?{_TWEET_FIELDS}"
        data, err = self._get(url, params=params)
        if err:
            return [], err
        posts = []
        for tw in (data or {}).get("data", []) or []:
            metrics = tw.get("public_metrics", {}) or {}
            posts.append({
                "source_type": "x",
                "via": "x_api",
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


def fetch_all(accounts, since_utc: datetime, bearer_token: Optional[str] = None,
              pause: float = 0.6) -> Tuple[List[dict], List[dict]]:
    """批量抓取。返回 (posts, statuses)，statuses 记录每个账号成功/失败原因。"""
    token = bearer_token if bearer_token is not None else config.x_token()
    if not token:
        return [], [{
            "source": "X API", "ok": False,
            "detail": "未配置 X_BEARER_TOKEN，跳过官方 X 抓取（详见 X_TOKEN配置指南.md）",
        }]
    client = XClient(token)
    posts: List[dict] = []
    statuses: List[dict] = []
    failed = 0
    for i, acc in enumerate(accounts):
        user_posts, err = client.user_tweets(acc.handle, since_utc)
        if err:
            failed += 1
            statuses.append({"source": f"x:@{acc.handle}", "ok": False, "detail": err})
        else:
            posts.extend(user_posts)
            statuses.append({
                "source": f"x:@{acc.handle}", "ok": True,
                "detail": f"{len(user_posts)} 条窗口内推文",
            })
        if i < len(accounts) - 1:
            time.sleep(pause)
    statuses.insert(0, {
        "source": "X API 汇总", "ok": failed == 0,
        "detail": f"共 {len(accounts)} 个账号，失败 {failed} 个，"
                  f"取得 {len(posts)} 条（接入点：{client.base}）"})
    return posts, statuses
