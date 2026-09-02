# -*- coding: utf-8 -*-
"""把报告对象渲染成 Markdown。"""
from typing import List

from .keywords import GROUP_ORDER


def _fmt_date(value) -> str:
    if not value:
        return "-"
    s = str(value)
    return s[:16].replace("T", " ") if "T" in s else s


def _price_line(name: str, d: dict) -> str:
    if not d:
        return f"| {name} | - | - | - | - |"
    if d.get("error"):
        return f"| {name} | 取数失败 | - | - | {d['error']} |"
    arrow = ""
    if d.get("change") is not None:
        arrow = "▲" if d["change"] >= 0 else "▼"
    prev_close = d.get("prev_close")
    return (f"| {name} | {d.get('close') if d.get('close') is not None else '-'} | "
            f"{prev_close if prev_close is not None else '-'} | "
            f"{arrow} {d.get('change') if d.get('change') is not None else '-'} "
            f"（{d.get('pct_change') if d.get('pct_change') is not None else '-'}%） | "
            f"{_fmt_date(d.get('date'))} |")


def render_markdown(report: dict) -> str:
    lines: List[str] = []
    lines.append(f"# {report['title']}")
    lines.append("")
    lines.append(f"> 生成时间：{report['generated_at']}（{report['timezone']}）　"
                 f"统计窗口：最近 {report['window_hours']} 小时（自 {report['window_start']}）　"
                 f"相关性阈值：{report['min_score']}")
    lines.append("")

    # 一、价格快照
    lines.append("## 一、价格快照（WTI / Brent）")
    lines.append("")
    prices = report.get("prices")
    if prices:
        lines.append("| 品种 | 最新收盘 | 前收盘 | 涨跌 | 日期 |")
        lines.append("|---|---|---|---|---|")
        lines.append(_price_line("WTI 原油", prices.get("WTI", {})))
        lines.append(_price_line("Brent 原油", prices.get("Brent", {})))
        lines.append("")
        lines.append(f"价格来源：{prices.get('source', '')}，抓取于 {prices.get('fetched_at', '')}")
    else:
        lines.append("本次未抓取价格。")
    lines.append("")

    # 二、概览
    lines.append("## 二、今日概览")
    lines.append("")
    lines.append(f"- 监控账号：{report['accounts_total']} 个，其中 "
                 f"{report['accounts_with_items']} 个在窗口内有相关动态")
    lines.append(f"- 入选相关条目：**{report['item_count']} 条**")
    if report["group_counts"]:
        parts = [f"{g} {n}" for g, n in sorted(report["group_counts"].items(),
                                               key=lambda kv: -kv[1])]
        lines.append("- 主题分布：" + "；".join(parts))
    if report["category_counts"]:
        parts = [f"{g} {n}" for g, n in sorted(report["category_counts"].items(),
                                               key=lambda kv: -kv[1])]
        lines.append("- 类别分布：" + "；".join(parts))
    lines.append("")

    # 三、按主题分组
    lines.append("## 三、分主题动态")
    lines.append("")
    items = report["items"]
    ordered_groups = [g for g in GROUP_ORDER if any(i["primary_group"] == g for i in items)]
    ordered_groups += sorted({i["primary_group"] for i in items} - set(GROUP_ORDER))
    if not items:
        lines.append("窗口内没有达到相关性阈值的内容（可在设置中调低阈值或检查抓取源状态）。")
        lines.append("")
    for group in ordered_groups:
        group_items = [i for i in items if i["primary_group"] == group]
        lines.append(f"### {group}（{len(group_items)} 条）")
        lines.append("")
        for i in group_items:
            lines.append(_item_line(i))
        lines.append("")

    # 四、抓取状态
    lines.append("## 四、抓取源状态")
    lines.append("")
    lines.append("| 来源 | 状态 | 说明 |")
    lines.append("|---|---|---|")
    for st in report["source_status"]:
        mark = "✅" if st["ok"] else "⚠️"
        lines.append(f"| {st['source']} | {mark} | {st['detail']} |")
    lines.append("")
    lines.append("---")
    lines.append("口径：条目经关键词组打分（核心油价 3 分、其余主题 2 分、宏观 1 分），"
                 f"≥ {report['min_score']} 分入选；X 内容来自账号时间线，公开信源为 RSS 聚合，仅供研究参考，不构成投资建议。")
    return "\n".join(lines)


def _item_line(i: dict) -> str:
    src_tag = "X" if i["source_type"] == "x" else "新闻"
    who = f"[@{i['account']}]({i['account_url']})" if i["source_type"] == "x" else i["account"]
    text = " ".join(i["text"].split())
    if len(text) > 500:
        text = text[:500] + "…"
    hits = "、".join(i.get("groups", []))
    link = i.get("url") or ""
    time_tag = i.get("local_time") or ""
    eng = ""
    if i["source_type"] == "x":
        eng = f"，❤{i.get('likes', 0)} 🔁{i.get('retweets', 0)}"
    return (f"- **{src_tag}｜{who}** {time_tag}（主题：{hits}，得分 {i['score']}{eng}）\n"
            f"  {text}\n  链接：{link}")
