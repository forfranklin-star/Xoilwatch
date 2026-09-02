# -*- coding: utf-8 -*-
"""原油关注账号每日报告 —— Streamlit 前端。

部署：本文件位于仓库根目录，Streamlit Community Cloud 直接选择 app.py 即可。
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from oilwatch import accounts as accounts_mod
from oilwatch import pipeline, report as report_mod, storage
from oilwatch.prices import snapshot as price_snapshot

st.set_page_config(page_title="原油观察日报", page_icon="🛢", layout="wide")
TZ = os.environ.get("REPORT_TZ", "Asia/Tokyo")


# ---------------------------------------------------------------- 基础工具
def now_local() -> datetime:
    return datetime.now(ZoneInfo(TZ))


@st.cache_data(ttl=300, show_spinner=False)
def cached_price_snapshot():
    return price_snapshot()


def generate(window_hours: int, min_score: int, use_x: bool,
             use_feeds: bool, use_prices: bool) -> str:
    rep = pipeline.run(
        window_hours=window_hours, min_score=min_score,
        use_x=use_x, use_feeds=use_feeds, use_prices=use_prices,
    )
    md = report_mod.render_markdown(rep)
    return storage.save_report(rep, md)


def price_metric(col, name: str, data: dict):
    if not data or data.get("error"):
        col.metric(name, "取数失败")
        return
    delta = data.get("pct_change")
    col.metric(f"{name}（美元/桶）",
               f"{data.get('close')}",
               None if delta is None else f"{delta}%")


# ---------------------------------------------------------------- 侧边栏
st.sidebar.title("🛢 原油观察日报")
x_ok = bool(os.environ.get("X_BEARER_TOKEN"))
st.sidebar.markdown(
    f"**数据源状态**：X API {'✅ 已配置 Token' if x_ok else '⚠️ 未配置（仅公开信源）'}")

st.sidebar.subheader("抓取参数")
window_hours = st.sidebar.slider("统计窗口（小时）", 6, 48, 24, step=1)
min_score = st.sidebar.slider("相关性阈值（分）", 1, 8, 3, step=1,
                              help="核心油价词3分，供需/库存/地缘/航运2分，宏观1分")
use_x = st.sidebar.checkbox("抓取 X 关注账号", value=True)
use_feeds = st.sidebar.checkbox("抓取公开新闻 RSS", value=True)
use_prices = st.sidebar.checkbox("抓取 WTI/Brent 价格", value=True)

if st.sidebar.button("⚡ 立即生成报告", type="primary", width="stretch"):
    with st.spinner("正在抓取并生成报告…"):
        rid = generate(window_hours, min_score, use_x, use_feeds, use_prices)
    st.sidebar.success(f"已生成：{rid}")
    st.session_state["selected_id"] = rid

auto_run = st.sidebar.checkbox(
    "打开应用时，若当天 10:00 后仍无今日报告则自动补生成", value=False)
st.sidebar.caption("定时自动生成由 GitHub Actions 每天 10:00（JST）执行并提交到仓库，"
                   "此处仅为会话内补生成。")

# 会话级自动补生成（只跑一次）
if auto_run and not st.session_state.get("auto_ran"):
    today = now_local().strftime("%Y-%m-%d")
    has_today = any(m["report_date"] == today for m in storage.list_reports())
    if not has_today and now_local().hour >= 10:
        with st.spinner("自动补生成今日报告…"):
            rid = generate(window_hours, min_score, use_x, use_feeds, use_prices)
            st.session_state["selected_id"] = rid
    st.session_state["auto_ran"] = True


tab_latest, tab_archive, tab_accounts, tab_help = st.tabs(
    ["📄 报告阅读", "🗄 报告档案（导出/重命名/删除）", "👥 关注账号", "ℹ️ 说明与部署"])

# ---------------------------------------------------------------- 报告阅读
with tab_latest:
    metas = storage.list_reports()
    if not metas:
        st.info("还没有存档报告。点击左侧「立即生成报告」，或等待 GitHub Actions 定时生成。")
    else:
        ids = [m["id"] for m in metas]
        default_idx = 0
        if st.session_state.get("selected_id") in ids:
            default_idx = ids.index(st.session_state["selected_id"])
        chosen = st.selectbox("选择报告", ids, index=default_idx,
                              format_func=lambda r: next(
                                  f"{m['title']}（{m['item_count']}条）"
                                  for m in metas if m["id"] == r))
        st.session_state["selected_id"] = chosen
        rep = storage.load_report(chosen)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("入选条目", rep.get("item_count", 0))
        c2.metric("监控账号", rep.get("accounts_total", 0))
        prices = rep.get("prices") or {}
        price_metric(c3, "WTI", prices.get("WTI"))
        price_metric(c4, "Brent", prices.get("Brent"))
        st.divider()
        st.markdown(storage.read_markdown(chosen))
        st.download_button(
            "下载该报告 Markdown", data=storage.read_markdown(chosen).encode("utf-8"),
            file_name=f"{chosen}.md", mime="text/markdown")

# ---------------------------------------------------------------- 报告档案
with tab_archive:
    st.caption("所有报告保存在仓库 reports/ 目录；可导出到本地、重命名或删除。")
    metas = storage.list_reports()
    if metas:
        df = pd.DataFrame([{
            "报告ID": m["id"], "标题": m["title"], "报告日期": m["report_date"],
            "生成时间": m["generated_at"], "条目数": m["item_count"],
            "大小KB": m["size_kb"],
        } for m in metas])
        st.dataframe(df, width="stretch", hide_index=True)

        st.subheader("单份管理")
        chosen2 = st.selectbox("选择要管理的报告", [m["id"] for m in metas],
                               key="archive_select")
        cc1, cc2, cc3 = st.columns(3)
        meta2 = next(m for m in metas if m["id"] == chosen2)
        cc1.download_button(
            "⬇ 导出 .md", data=storage.read_markdown(chosen2).encode("utf-8"),
            file_name=f"{chosen2}.md", mime="text/markdown", width="stretch")
        cc2.download_button(
            "⬇ 导出 .json",
            data=json.dumps(storage.load_report(chosen2), ensure_ascii=False, indent=2
                            ).encode("utf-8"),
            file_name=f"{chosen2}.json", mime="application/json",
            width="stretch")
        cc3.download_button(
            "⬇ 导出该份 .zip（md+json）",
            data=storage.export_zip(chosen2),
            file_name=f"{chosen2}.zip", mime="application/zip",
            width="stretch")

        with st.form("rename_form"):
            new_title = st.text_input("重命名（新的报告标题）", value=meta2["title"])
            if st.form_submit_button("确认重命名"):
                new_id = storage.rename_report(chosen2, new_title)
                st.session_state["selected_id"] = new_id
                st.success(f"已重命名，新ID：{new_id}")
                st.rerun()

        st.write("")
        if st.button("🗑 删除该报告", type="secondary"):
            st.session_state["confirm_delete"] = chosen2
        if st.session_state.get("confirm_delete") == chosen2:
            st.warning(f"确认删除 {chosen2}？此操作不可恢复（删除前可先导出备份）。")
            cdel1, cdel2 = st.columns(2)
            if cdel1.button("确认删除", type="primary"):
                storage.delete_report(chosen2)
                st.session_state.pop("confirm_delete", None)
                st.rerun()
            if cdel2.button("取消"):
                st.session_state.pop("confirm_delete", None)
                st.rerun()

        st.divider()
        st.download_button(
            "📦 一键导出全部存档（ZIP，下载到本地电脑）",
            data=storage.export_zip(),
            file_name=f"oilwatch_reports_{now_local().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip")
    else:
        st.info("暂无存档。")

# ---------------------------------------------------------------- 关注账号
with tab_accounts:
    st.caption("主清单来自 data/accounts.csv（源自截图整理）；此处新增的账号写入 "
               "data/accounts_local.csv。")
    accs = accounts_mod.load_accounts(include_disabled=True)
    adf = pd.DataFrame([{
        "Handle": "@" + a.handle, "名称": a.display_name, "类别": a.category,
        "优先级": a.priority, "启用": "是" if a.enabled else "否（待核对）",
        "备注": a.notes, "主页": a.url,
    } for a in accs])
    st.dataframe(adf, width="stretch", hide_index=True)
    st.write(f"共 {len(accs)} 个账号，其中启用 "
             f"{sum(1 for a in accs if a.enabled)} 个。")

    with st.expander("➕ 新增关注账号"):
        with st.form("add_acc", clear_on_submit=True):
            fc1, fc2 = st.columns(2)
            h = fc1.text_input("X Handle（不带@）")
            name = fc2.text_input("显示名称")
            fc3, fc4 = st.columns(2)
            cat = fc3.selectbox("类别", ["能源原油", "航运油轮", "宏观市场", "地缘情报"])
            pri = fc4.selectbox("优先级", ["high", "medium", "low"])
            note = st.text_input("备注")
            if st.form_submit_button("添加"):
                try:
                    path = accounts_mod.append_local_account(
                        h, name, cat, pri, note)
                    st.success(f"已添加到 {path.name}")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

# ---------------------------------------------------------------- 说明
with tab_help:
    st.subheader("工作机制")
    st.markdown(
        "1. **账号清单**：35 个来自截图的 X 账号（能源原油/航运油轮/宏观市场/地缘情报）。\n"
        "2. **抓取**：配置 `X_BEARER_TOKEN` 后走 X API v2 读取各账号时间线；"
        "未配置时使用 OilPrice、EIA、Google News 等免鉴权 RSS 兜底。\n"
        "3. **筛选**：中英双语关键词组对每条内容打分，只保留与原油价格及其影响因素"
        "（供需、库存、需求、地缘制裁、油轮航运、宏观金融）相关的内容。\n"
        "4. **定时**：GitHub Actions 按 cron `0 1 * * *`（UTC，即日本时间 10:00）"
        "自动运行并把报告提交回仓库；Streamlit 读取 reports/ 展示。\n"
        "5. **存档**：每份报告同时保存 .json 与 .md，可在「报告档案」页导出、重命名、删除。")
    st.subheader("数据源连通性自检")
    if st.button("测试 WTI/Brent 价格源"):
        snap = cached_price_snapshot()
        st.json({k: v for k, v in snap.items()})
    st.subheader("部署要点")
    st.markdown(
        "- GitHub 仓库 Secrets 中添加 `X_BEARER_TOKEN`（可选但推荐）。\n"
        "- Streamlit Community Cloud 连接该仓库、入口文件 `app.py` 部署。\n"
        "- Streamlit 云端本地文件会在容器重建时重置，长期存档以 Actions 提交到 "
        "Git 的副本为准；重要改名/删除后请用「导出全部 ZIP」在本地留档。\n"
        "详见 README.md。")
