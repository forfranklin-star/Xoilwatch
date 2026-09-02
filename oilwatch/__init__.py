"""oilwatch —— 原油关注账号每日动态抓取与报告生成。

模块划分：
- accounts: 关注账号清单
- keywords/filter: 原油相关性关键词与打分
- sources.x_api: X(Twitter) API v2 抓取
- sources.public_feeds: 免鉴权公开信源（RSS）兜底/补充
- prices: WTI/Brent 价格快照
- pipeline: 汇总编排
- report: Markdown 渲染
- storage: 报告存档/重命名/删除/导出
- cli: 命令行入口（供 GitHub Actions 定时调用）
"""

__version__ = "1.0.0"
