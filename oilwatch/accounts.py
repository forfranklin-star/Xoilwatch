# -*- coding: utf-8 -*-
"""关注账号清单读取。主清单 data/accounts.csv，界面新增账号写入 data/accounts_local.csv。"""
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "accounts.csv"
LOCAL_CSV = ROOT / "data" / "accounts_local.csv"

FIELDS = ["handle", "display_name", "category", "priority", "enabled", "notes"]


@dataclass
class Account:
    handle: str
    display_name: str
    category: str = ""
    priority: str = "medium"
    enabled: bool = True
    notes: str = ""

    @property
    def url(self) -> str:
        return f"https://x.com/{self.handle}"


def _parse_bool(v: str) -> bool:
    return str(v).strip().lower() not in ("0", "false", "no", "off", "")


def load_accounts(extra_csv: Optional[Path] = None,
                  include_disabled: bool = False) -> List[Account]:
    """读取账号。extra_csv 默认追加读取本地自建清单；重复 handle 以后出现者忽略。"""
    paths = [DEFAULT_CSV]
    if extra_csv is None and LOCAL_CSV.exists():
        paths.append(LOCAL_CSV)
    elif extra_csv is not None:
        paths.append(Path(extra_csv))

    out: List[Account] = []
    seen = set()
    for path in paths:
        if not Path(path).exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                handle = (row.get("handle") or "").strip().lstrip("@")
                if not handle or handle.lower() in seen:
                    continue
                enabled = _parse_bool(row.get("enabled", "1"))
                seen.add(handle.lower())
                if not enabled and not include_disabled:
                    continue
                out.append(Account(
                    handle=handle,
                    display_name=(row.get("display_name") or "").strip(),
                    category=(row.get("category") or "").strip(),
                    priority=(row.get("priority") or "medium").strip(),
                    enabled=enabled,
                    notes=(row.get("notes") or "").strip(),
                ))
    return out


def append_local_account(handle: str, display_name: str = "",
                         category: str = "能源原油", priority: str = "medium",
                         notes: str = "") -> Path:
    """在界面中新增账号，追加到 accounts_local.csv（已存在则忽略）。"""
    LOCAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    handle = handle.strip().lstrip("@")
    existing = {a.handle.lower() for a in load_accounts(include_disabled=True)}
    if handle.lower() in existing:
        raise ValueError(f"账号 @{handle} 已存在")
    new_file = not LOCAL_CSV.exists()
    with open(LOCAL_CSV, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow({
            "handle": handle, "display_name": display_name or handle,
            "category": category, "priority": priority,
            "enabled": "1", "notes": notes,
        })
    return LOCAL_CSV
