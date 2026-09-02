# -*- coding: utf-8 -*-
"""命令行入口，供 GitHub Actions / 本地 cron 调用。

用法：
  python -m oilwatch.cli daily                # 生成最近24小时日报并存档
  python -m oilwatch.cli daily --window-hours 24 --min-score 3
  python -m oilwatch.cli accounts             # 打印关注账号清单
  python -m oilwatch.cli list                 # 列出已存档报告
"""
import argparse
import sys

from . import accounts as accounts_mod
from . import pipeline, report as report_mod, storage


def cmd_daily(args) -> int:
    rep = pipeline.run(
        window_hours=args.window_hours,
        min_score=args.min_score,
        use_x=not args.no_x,
        use_feeds=not args.no_feeds,
        use_prices=not args.no_prices,
    )
    md = report_mod.render_markdown(rep)
    rid = storage.save_report(rep, md)
    print(f"[ok] 报告已生成: {rid}  入选条目 {rep['item_count']} 条")
    failed = [s for s in rep["source_status"] if not s["ok"]]
    for s in failed:
        print(f"  [warn] {s['source']}: {s['detail']}", file=sys.stderr)
    return 0


def cmd_accounts(_args) -> int:
    rows = accounts_mod.load_accounts(include_disabled=True)
    for a in rows:
        flag = " " if a.enabled else "x"
        print(f"[{flag}] @{a.handle:<18} {a.category:<6} {a.priority:<6} {a.display_name}")
    print(f"共 {len(rows)} 个账号")
    return 0


def cmd_list(_args) -> int:
    for meta in storage.list_reports():
        print(f"{meta['id']:<24} {meta['item_count']:>3} 条  {meta['title']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="oilwatch", description="原油关注账号每日报告")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_daily = sub.add_parser("daily", help="生成并保存日报")
    p_daily.add_argument("--window-hours", type=int, default=24)
    p_daily.add_argument("--min-score", type=int, default=3)
    p_daily.add_argument("--no-x", action="store_true", help="不抓取 X")
    p_daily.add_argument("--no-feeds", action="store_true", help="不抓取公开 RSS")
    p_daily.add_argument("--no-prices", action="store_true", help="不抓取价格")
    p_daily.set_defaults(func=cmd_daily)

    p_acc = sub.add_parser("accounts", help="打印账号清单")
    p_acc.set_defaults(func=cmd_accounts)

    p_list = sub.add_parser("list", help="列出存档报告")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
