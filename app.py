# -*- coding: utf-8 -*-
"""原油多源每日报告 —— Streamlit 前端。
来源：X 关注账号 + 全球 30 家主流媒体 + 14 家权威机构 + 公共聚合 + 价格。
部署：本文件位于仓库根目录，Streamlit Community Cloud 直接选择 app.py。
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from oilwatch import accounts as accounts_mod, config
from oilwatch import pipeline, report as report_mod, storage
from oilwatch.prices import snapshot as price_snapshot
from oilwatch.sources import media_feeds
from oilwatch.sources.x_api import XClient

# Streamlit Secrets -> 环境变量，使 config 层在云端也能读到配置
try:
    for _k, _v in st.secrets.items():
        os.environ.setdefault(_k, str(_v))
except Exception:
    pass

st.set_page_config(page_title="原油观察日报", page_icon="🛢", layout="wide")
TZ = config.get("REPORT_TZ", "Asia/Shanghai")


def now_local() -> datetime:
    return datetime.now(ZoneInfo(TZ))


@st.cache_data(ttl=300, show_spinner=False)
def cached_price_snapshot():
    return price_snapshot()


def generate(window_hours, min_score, use_x, use_media, use_institutions,
             use_feeds, use_prices) -> str:
    rep = pipeline.run(
        window_hours=window_hours, min_score=min_score,
        use_x=use_x, use_media=use_media, use_institutions=use_institutions,
        use_feeds=use_feeds, use_prices=use_prices,
    )
    md = report_mod.render_markdown(rep)
    return storage.save_report(rep, md)


def price_metric(col, name, data):
    if not data or data.get("error"):
        col.metric(name, "取数失败")
        return
    delta = data.get("pct_change")
    col.metric(f"{name}（美元/桶）", f"{data.get('close')}",
               None if delta is None else f"{delta}%")


# ---------------------------------------------------------------- 侧边栏
st.sidebar.title("🛢 原油观察日报")
_token = config.x_token()
if _token:
    st.sidebar.markdown(f"**X 抓取**：✅ Token 已配置（`{config.mask(_token)}`）")
    if st.sidebar.button("🔑 检测 Token 有效性", width="stretch"):
        with st.sidebar.spinner("校验中…"):
            ok, msg = XClient(_token).verify_token()
        (st.sidebar.success if ok else st.sidebar.error)(msg)
elif config.mirror_instances():
    st.sidebar.markdown("**X 抓取**：🪞 镜像 RSS（无需 Token）")
else:
    st.sidebar.markdown("**X 抓取**：⚠️ 未配置 Token（媒体/机构仍正常）")

st.sidebar.subheader("信源开关")
use_x = st.sidebar.checkbox("X 关注账号（35个）", value=True)
use_media = st.sidebar.checkbox("全球主流媒体（30家）", value=True)
use_institutions = st.sidebar.checkbox("权威机构（14家）", value=True)
use_feeds = st.sidebar.checkbox("公共聚合（Google News 等）", value=True)
use_prices = st.sidebar.checkbox("WTI/Brent 价格", value=True)

st.sidebar.subheader("抓取参数")
window_hours = st.sidebar.slider("统计窗口（小时）", 6, 48, 24, step=1)
min_score = st.sidebar.slider(
    "相关性阈值（分）", 1, 10, 3, step=1,
    help="核心油价3分；供需/库存/需求/航运/战争/制裁2分；宏观/政治1分；"
         "且至少命中一个油价直接相关组")

if st.sidebar.button("⚡ 立即生成报告", type="primary", width="stretch"):
    with st.spinner("正在抓取多源内容并生成报告…"):
        rid = generate(window_hours, min_score, use_x, use_media,
                       use_institutions, use_feeds, use_prices)
    st.sidebar.success(f"已生成：{rid}")
    st.session_state["selected_id"] = rid

auto_run = st.sidebar.checkbox("打开时若当天 10:00 后无报告则自动补生成", value=False)
st.sidebar.caption("定时由 GitHub Actions 每天 10:00（按 REPORT_TZ，默认北京时间）执行并提交仓库。")

if auto_run and not st.session_state.get("auto_ran"):
    today = now_local().strftime("%Y-%m-%d")
    has_today = any(m["report_date"] == today for m in storage.list_reports())
    if not has_today and now_local().hour >= 10:
        with st.spinner("自动补生成今日报告…"):
            rid = generate(window_hours, min_score, use_x, use_media,
                           use_institutions, use_feeds, use_prices)
            st.session_state["selected_id"] = rid
    st.session_state["auto_ran"] = True

tab_latest, tab_archive, tab_sources, tab_accounts, tab_help = st.tabs(
    ["📄 报告阅读", "🗄 报告档案", "📰 媒体与机构", "👥 X 关注账号", "ℹ️ 说明与部署"])

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
        chosen = st.selectbox(
            "选择报告", ids, index=default_idx,
            format_func=lambda r: next(f"{m['title']}（{m['item_count']}条）"
                                       for m in metas if m["id"] == r))
        st.session_state["selected_id"] = chosen
        rep = storage.load_report(chosen)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("入选条目", rep.get("item_count", 0))
        tc = rep.get("type_counts", {})
        c2.metric("X/媒体/机构",
                  f"{tc.get('x',0)}/{tc.get('media',0)}/{tc.get('institution',0)}")
        prices = rep.get("prices") or {}
        price_metric(c3, "WTI", prices.get("WTI"))
        price_metric(c4, "Brent", prices.get("Brent"))
        sec = rep.get("section_counts", {})
        c5.metric("能源/地缘", f"{sum(v for k,v in sec.items() if k.startswith(('A','B')))}")
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
            file_name=f"{chosen2}.json", mime="application/json", width="stretch")
        cc3.download_button(
            "⬇ 导出该份 .zip（md+json）", data=storage.export_zip(chosen2),
            file_name=f"{chosen2}.zip", mime="application/zip", width="stretch")

        with st.form("rename_form"):
            new_title = st.text_input("重命名（新的报告标题）", value=meta2["title"])
            if st.form_submit_button("确认重命名"):
                new_id = storage.rename_report(chosen2, new_title)
                st.session_state["selected_id"] = new_id
                st.success(f"已重命名，新ID：{new_id}")
                st.rerun()

        st.write("")
        if st.button("🗑 删除该报告"):
            st.session_state["confirm_delete"] = chosen2
        if st.session_state.get("confirm_delete") == chosen2:
            st.warning("确认删除？此操作不可恢复（删除前可先导出备份）。")
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

# ---------------------------------------------------------------- 媒体与机构
with tab_sources:
    st.caption("媒体清单 data/media.csv（按全球影响力排序，top30 默认启用，"
               "extra 为可选补充）；机构清单 data/institutions.csv。")
    media = media_feeds.load_media(include_disabled=True)
    mdf = pd.DataFrame([{
        "排名": s.tier, "媒体": s.name, "地区": s.region_or_category,
        "栏目Feed数": len(s.feeds), "启用": "是" if s.enabled else "否",
        "主页": s.homepage,
    } for s in media])
    st.write(f"**全球媒体（共 {len(media)}，启用 {sum(s.enabled for s in media)}）**")
    st.dataframe(mdf, width="stretch", hide_index=True)

    insts = media_feeds.load_institutions(include_disabled=True)
    idf = pd.DataFrame([{
        "机构": s.name, "类别": s.region_or_category,
        "Feed数": len(s.feeds), "主页": s.homepage,
    } for s in insts])
    st.write(f"**权威机构（{len(insts)} 家）**")
    st.dataframe(idf, width="stretch", hide_index=True)

# ---------------------------------------------------------------- X 账号
with tab_accounts:
    st.caption("主清单 data/accounts.csv；界面新增账号写入 data/accounts_local.csv。")
    accs = accounts_mod.load_accounts(include_disabled=True)
    adf = pd.DataFrame([{
        "Handle": "@" + a.handle, "名称": a.display_name, "类别": a.category,
        "优先级": a.priority, "启用": "是" if a.enabled else "否",
        "备注": a.notes, "主页": a.url,
    } for a in accs])
    st.dataframe(adf, width="stretch", hide_index=True)
    st.write(f"共 {len(accs)} 个 X 账号，启用 {sum(a.enabled for a in accs)} 个。")
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
                    accounts_mod.append_local_account(h, name, cat, pri, note)
                    st.success("已添加")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

# ---------------------------------------------------------------- 说明
with tab_help:
    st.subheader("工作机制")
    st.markdown(
        "1. **四类信源**：35 个 X 账号、30 家全球主流媒体（BBC/NYT/路透/半岛电视台等）、"
        "14 家权威机构（OPEC/IEA/EIA/美联储/白宫/北约等）、Google News 聚合骨干。\n"
        "2. **四大门类**：A 能源市场（油价/供需/库存/需求/航运/油气产品）、"
        "B 战争与地缘（战争冲突/制裁博弈）、C 宏观经济（央行/美元/通胀/衰退）、"
        "D 政治政策（选举/政府/外交/能源政策）。\n"
        "3. **相关性规则**：中英双语关键词打分，≥阈值且至少命中一个油价直接相关组；"
        "纯政治/泛社会噪音自动剔除；同一标题跨源去重。\n"
        "4. **定时**：GitHub Actions 每天 10:00（JST）生成并提交仓库；网页可随时手动生成。\n"
        "5. **存档**：.json + .md 成对保存，支持导出/重命名/删除。")
    st.subheader("数据源自检")
    if st.button("测试 WTI/Brent 价格源"):
        st.json(cached_price_snapshot())
    st.subheader("部署要点")
    st.markdown(
        "- 可选配置 `X_BEARER_TOKEN`（X 账号抓取；媒体/机构无需任何 key）。\n"
        "- Streamlit Community Cloud 连接仓库、入口 `app.py` 部署。\n"
        "- 个别媒体 RSS 在部分网络下可能失败，程序逐源容错并在报告末尾列出状态；"
        "长期存档以 Actions 提交到 Git 的副本为准。\n详见 README.md 与 X_TOKEN配置指南.md。")
