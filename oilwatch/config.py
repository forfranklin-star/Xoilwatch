# -*- coding: utf-8 -*-
"""统一配置入口：自动加载仓库根目录 .env，其余来自环境变量。

优先级：已存在的环境变量（GitHub Secrets / Streamlit 注入）优先于 .env 文件。
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ENV_LOADED = False


def load_dotenv(path: Path = None) -> None:
    """解析简单 KEY=VALUE 的 .env 文件，不覆盖已有环境变量。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    p = Path(path) if path else ROOT / ".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _ENV_LOADED = True


load_dotenv()


def get(key: str, default=None):
    return os.environ.get(key, default)


def x_token():
    return get("X_BEARER_TOKEN")


def mask(value: str) -> str:
    if not value:
        return ""
    return f"{value[:4]}…{value[-4:]}" if len(value) > 10 else "****"


def mirror_instances():
    """返回 (kind, base_url) 列表：NITTER_BASE / RSSHUB_BASE 可逗号分隔多个。"""
    out = []
    for kind, env_key in (("nitter", "NITTER_BASE"), ("rsshub", "RSSHUB_BASE")):
        raw = get(env_key) or ""
        for base in raw.split(","):
            base = base.strip().rstrip("/")
            if base:
                out.append((kind, base))
    return out
