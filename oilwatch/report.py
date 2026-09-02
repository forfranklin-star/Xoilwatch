# -*- coding: utf-8 -*-
"""把报告对象渲染成 Markdown（按四大门类组织）。"""
from typing import List

from .keywords import GROUP_ORDER, SECTION_ORDER

SOURCE_LABEL = {"x": "X", "media": "媒体", "institution": "机构"}


def _price_line(name: str, d: dict) -> str:
    if not d:
        return f"| {name} | - | - | - | - |"
    if d.get("error"):
        return f"| {name} | 取数失败 | - | - | {d['error']} |"
    arrow = "▲" if (d.get("change") or 0) >= 0 else "▼"
    return (f"| {name} | {d.get('close') if d.get('close') is not None else '-'} | "
            f"{d.get('prev_close') or '-'} | {arrow} "
            f"{d.get('change') if d.get('change') is not None else '-'} "
            f"（{d.get('pct_change') if d.get('pct_change') is not None else '-'}%） | "
            f"{_fmt_date(d.get('date'))} |")


def _fmt_date(value) -> str:
    if not value:
        return "-"
    s = str(value)
    return s[:16].replace("T", " ") if "T" in s else s


def _item_line(i: dict) -> str:
    tag = SOURCE_LABEL.get(i["source_type"], i["source_type"])
    if i["source_type"] == "x":
        who = f"[@{i['account']}]({i['account_url']})"
        eng = f"，❤{i.get('likes', 0)} 🔁{i.get('retweets', 0)}"
    else:
        who = (f"[{i['account']}]({i.get('account_url') or i.get('url') or '#'})"
               if i.get("account_url") else i["account"])
        region = i.get("region")
        who = f"{who}（{region}）" if region and region != "聚合" else who
        eng = ""
    text = " ".join(i.get("text", "").split())
    if len(text) > 450:
        text = text[:450] + "…"
    hits = "、".join(i.get("groups", []))
    return (f"- **{tag}｜{who}** {i.get('local_time', '')} "
            f"（{hits}，{i['score']}分{eng}）\n  {text}\n  链接：{i.get('url', '')}")


def render_markdown(report: dict) -> str:
    lines: List[str] = []
    lines.append(f"# {report['title']}")
    lines.append("")
    lines.append(
        f"> 生成：{report['generated_at']}（{report['timezone']}）｜窗口：最近 "
        f"{report['window_hours']} 小时（自 {report['window_start']}）｜阈值："
        f"{report['min_score']} 分｜监控：{report.get('accounts_total', 0)} 个 X 账号、"
        f"{report.get('media_total', 0)} 家媒体、{report.get('institutions_total', 0)} 家机构")
    lines.append("")

    # 一、价格快照
    lines.append("## 一、价格快照（WTI / Brent）")
    lines.append("")
    prices = report.get("prices")
    if prices:
        lines += ["| 品种 | 最新 | 前收 | 涨跌 | 时间 |",
                  "|---|---|---|---|---|",
                  _price_line("WTI 原油", prices.get("WTI", {})),
                  _price_line("Brent 原油", prices.get("Brent", {})), "",
                  f"价格来源：{prices.get('source', '')}（抓取于 {prices.get('fetched_at', '')}）", ""]
    else:
        lines += ["本次未抓取价格。", ""]

    # 二、概览
    lines.append("## 二、今日概览")
    lines.append("")
    tc = report.get("type_counts", {})
    lines.append(f"- 入选相关内容 **{report['item_count']} 条**："
                 f"X {tc.get('x', 0)}、媒体 {tc.get('media', 0)}、"
                 f"机构 {tc.get('institution', 0)}")
    sc = report.get("section_counts", {})
    lines.append("- 门类分布：" + "；".join(f"{k} {v}" for k, v in sc.items() if v))
    gc = report.get("group_counts", {})
    if gc:
        lines.append("- 主题分布：" + "；".join(
            f"{g} {n}" for g, n in sorted(gc.items(), key=lambda kv: -kv[1])))
    tops = report.get("top_outlets", [])[:8]
    if tops:
        lines.append("- 高产信源：" + "；".join(f"{n} {c}" for n, c in tops))
    lines.append("")

    # 三~六、按四大门类分节
    items = report["items"]
    sec_no = {"A 能源市场": "三", "B 战争与地缘": "四",
              "C 宏观经济": "五", "D 政治政策": "六"}
    for section in SECTION_ORDER:
        sec_items = [i for i in items if i.get("primary_section") == section]
        lines.append(f"## {sec_no.get(section, '附')}、{section}（{len(sec_items)} 条）")
        lines.append("")
        if not sec_items:
            lines.append("_本门类窗口内无达到阈值的内容。_")
            lines.append("")
            continue
        groups_here = [g for g in GROUP_ORDER
                       if any(i["primary_group"] == g for i in sec_items)]
        for group in groups_here:
            gi = [i for i in sec_items if i["primary_group"] == group]
            lines.append(f"### {group}（{len(gi)}）")
            lines.append("")
            for i in gi:
                lines.append(_item_line(i))
            lines.append("")

    # 附：抓取状态（折叠为紧凑表格，只列失败与汇总）
    lines.append("## 附、抓取源状态")
    lines.append("")
    failed = [s for s in report["source_status"] if not s["ok"]]
    summary = [s for s in report["source_status"]
               if str(s["source"]).endswith("汇总")]
    lines.append("| 来源 | 状态 | 说明 |")
    lines.append("|---|---|---|")
    for s in summary:
        lines.append(f"| {s['source']} | {'✅' if s['ok'] else '⚠️'} | {s['detail']} |")
    for s in failed[:25]:
        lines.append(f"| {s['source']} | ⚠️ | {s['detail']} |")
    if len(failed) > 25:
        lines.append(f"| … | ⚠️ | 另有 {len(failed) - 25} 个源失败（详见 JSON） |")
    lines.append("")
    lines.append("---")
    lines.append("口径：关键词组打分（核心油价3、供需/库存/需求/航运/战争/制裁2、"
                 "宏观/政治1），≥阈值且至少命中一个油价直接相关组才入选；"
                 "同一标题跨源去重；媒体取 24h 窗口、机构取 72h 窗口。"
                 "内容仅供研究参考，不构成投资建议。")
    return "\n".join(lines)
