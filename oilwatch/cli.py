# -*- coding: utf-8 -*-
"""命令行入口，供 GitHub Actions / 本地 cron 调用。

用法：
  python -m oilwatch.cli daily                # 生成最近24小时日报并存档
  python -m oilwatch.cli daily --window-hours 24 --min-score 3
  python -m oilwatch.cli check-token          # 校验 X_BEARER_TOKEN 是否有效
  python -m oilwatch.cli accounts             # 打印 X 关注账号清单
  python -m oilwatch.cli sources              # 打印媒体/机构信源清单
  python -m oilwatch.cli list                 # 列出已存档报告
"""
import argparse

from . import accounts as accounts_mod, config
from . import pipeline, report as report_mod, storage
from .sources import media_feeds
from .sources.x_api import XClient


def cmd_daily(args) -> int:
    rep = pipeline.run(
        window_hours=args.window_hours,
        min_score=args.min_score,
        use_x=not args.no_x,
        use_media=not args.no_media,
        use_institutions=not args.no_institutions,
        use_feeds=not args.no_feeds,
        use_prices=not args.no_prices,
    )
    md = report_mod.render_markdown(rep)
    rid = storage.save_report(rep, md)
    print(f"[ok] 报告已生成: {rid}  入选 {rep['item_count']} 条 "
          f"(X {rep['type_counts'].get('x', 0)}/媒体 {rep['type_counts'].get('media', 0)}"
          f"/机构 {rep['type_counts'].get('institution', 0)})")
    for s in rep["source_status"]:
        if not s["ok"]:
            print(f"  [warn] {s['source']}: {s['detail']}")
    return 0


def cmd_check_token(_args) -> int:
    token = config.x_token()
    print(f"接入点 X_API_BASE: {config.get('X_API_BASE') or 'https://api.twitter.com/2（官方）'}")
    mirrors = config.mirror_instances()
    print(f"镜像实例: {mirrors if mirrors else '未配置（NITTER_BASE / RSSHUB_BASE）'}")
    if not token:
        print("[fail] 未读取到 X_BEARER_TOKEN。请按 X_TOKEN配置指南.md 在 .env / "
              "GitHub Secrets / Streamlit Secrets 三处之一配置。")
        return 2
    print(f"Token: {config.mask(token)}，正在调用 /2/users/me 校验…")
    ok, msg = XClient(token).verify_token()
    print(("[ok] " if ok else "[fail] ") + msg)
    return 0 if ok else 1


def cmd_accounts(_args) -> int:
    rows = accounts_mod.load_accounts(include_disabled=True)
    for a in rows:
        flag = " " if a.enabled else "x"
        print(f"[{flag}] @{a.handle:<18} {a.category:<6} {a.priority:<6} {a.display_name}")
    print(f"共 {len(rows)} 个 X 账号")
    return 0


def cmd_sources(_args) -> int:
    media = media_feeds.load_media(include_disabled=True)
    inst = media_feeds.load_institutions(include_disabled=True)
    print("== 全球媒体 ==")
    for m in media:
        flag = " " if m.enabled else "x"
        print(f"[{flag}] {m.tier:<6} {m.name:<26} {m.region_or_category:<10} {len(m.feeds)} feeds")
    print(f"媒体共 {len(media)} 家（启用 {sum(m.enabled for m in media)}）")
    print("== 权威机构 ==")
    for m in inst:
        print(f"[ ] {m.name:<28} {m.region_or_category:<10} {len(m.feeds)} feeds")
    print(f"机构共 {len(inst)} 家")
    return 0


def cmd_list(_args) -> int:
    for meta in storage.list_reports():
        print(f"{meta['id']:<24} {meta['item_count']:>3} 条  {meta['title']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="oilwatch", description="原油多源每日报告")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_daily = sub.add_parser("daily", help="生成并保存日报")
    p_daily.add_argument("--window-hours", type=int, default=24)
    p_daily.add_argument("--min-score", type=int, default=3)
    p_daily.add_argument("--no-x", action="store_true", help="不抓取 X")
    p_daily.add_argument("--no-media", action="store_true", help="不抓取全球媒体")
    p_daily.add_argument("--no-institutions", action="store_true", help="不抓取机构")
    p_daily.add_argument("--no-feeds", action="store_true", help="不抓取聚合骨干")
    p_daily.add_argument("--no-prices", action="store_true", help="不抓取价格")
    p_daily.set_defaults(func=cmd_daily)

    p_chk = sub.add_parser("check-token", help="校验 X Token / 接入配置")
    p_chk.set_defaults(func=cmd_check_token)

    p_acc = sub.add_parser("accounts", help="打印 X 账号清单")
    p_acc.set_defaults(func=cmd_accounts)

    p_src = sub.add_parser("sources", help="打印媒体/机构信源清单")
    p_src.set_defaults(func=cmd_sources)

    p_list = sub.add_parser("list", help="列出存档报告")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
