# X_BEARER_TOKEN 配置指南（解决"未配置 Token，跳过 X 抓取"）

> 结论先行：**X（原 Twitter）官方 API 的免费套餐只能发推、不能读取任何时间线**。
> 要让本程序抓到 35 个关注账号的推文，必须在下面 **三条路线中选一条**。推荐路线 A。

---

## 路线 A：官方 X API（推荐，稳定合规）

### A1. 2026 年计费规则（开通前必读）

X 已从订阅制改为**按次付费（pay-per-use）**，新开发者没有月费门槛、用多少付多少：

| 操作 | 单价 | 本项目是否产生 |
|---|---|---|
| 查询用户（handle→ID） | $0.010 / 次 | 仅首次，之后被 `data/x_user_ids.json` 缓存，35 个账号一次性约 **$0.35** |
| 读取推文 | 约 $0.005 / 条 | 每天一次，按实际返回条数计费 |
| 免费套餐 | $0 | **读取数为 0**，无法用于本项目 |

**本项目月度成本估算**（35 账号、每天 10:00 跑一次、窗口 24 小时）：
`月费用 ≈ 账号数 × 每账号日均推文数 × 30 × $0.005 + $0.35`

- 每账号日均 3 条：约 **$16/月**
- 每账号日均 10 条：约 **$53/月**

费用只与 X 返回的条数有关，与本程序关键词过滤后保留多少无关（过滤在本地进行）。
新开发者账号可能有少量试用额度，以开发者门户实际显示为准。

### A2. 获取 Bearer Token 步骤

1. 打开 <https://developer.x.com/en/portal>，用你的 X 账号登录，申请开发者账号（可能需要用途说明审核）。
2. 进入后选择按次付费（Pay-per-use），绑定付款方式并充值少量额度（建议先充 $5 测试）。
3. **Create Project / App**（如 `oil-watch`），在 App 的 **Keys and tokens** 页找到
   **Bearer Token（OAuth 2.0, App only）**，点 Generate / Regenerate 复制——它是一长串
   `AAAAAAAAAAAAAAAAAAAA...` 字符串，**只显示一次，务必当场保存**。
4. 本项目只用"读"，不需要 API Key/Secret 和 Access Token，别把它们混进来。

### A3. 把 Token 配到三个位置（按你的运行方式选）

**① 本地运行**：在仓库根目录复制样例文件并填入：
```bash
cp .env.example .env
# 编辑 .env：X_BEARER_TOKEN=AAAAAAAAAAAAAAAAAAAA...
```
程序启动时自动加载，无需 export。

**② GitHub Actions（每天 10 点自动跑）**：
仓库页面 → Settings → Secrets and variables → Actions → New repository secret：
- Name：`X_BEARER_TOKEN`
- Value：粘贴 Token
工作流已写好读取逻辑，下次运行自动生效。

**③ Streamlit Community Cloud（网页端手动生成）**：
应用页面 → Settings → Secrets，粘贴：
```toml
X_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAA..."
```
保存后 Rerun。

### A4. 验证是否生效

```bash
python -m oilwatch.cli check-token
```
成功输出示例：`[ok] 有效，认证账号 @你的用户名（名称）`。
Streamlit 侧栏也有「🔑 检测 Token 有效性」按钮。之后再跑
`python -m oilwatch.cli daily`，报告"抓取源状态"里会出现每个账号的取数条数。

---

## 路线 B：第三方读取 API / v2 兼容网关（更便宜，需自行甄别）

有一批第三方服务商以更低单价提供推文读取（按调用计费、注册常送少量额度）。
- 若该服务提供**与 X v2 兼容的接口根地址**，只需额外配置：
  - `X_API_BASE`：网关地址（要包含到 `/2`）
  - `X_API_EXTRA_HEADERS`：网关要求的鉴权头（JSON 字符串），例如 `{"x-api-key":"xxx"}`
- 配置位置同样是 `.env` / GitHub Secrets / Streamlit Secrets，程序其余部分无需改动，
  `check-token` 会显示当前接入点。
- 若该服务接口格式与 X v2 不同，则不能直接接入，需要自行写适配器。

> 第三方服务在价格、稳定性与合规性上差异较大，请自行评估其信誉与条款。

## 路线 C：自建 RSS 镜像（零 Token，尽力而为，不保证稳定）

通过 Nitter 或 RSSHub 实例的 RSS 读取账号时间线：
- `NITTER_BASE=https://你的nitter实例`（可逗号分隔多个）
- `RSSHUB_BASE=https://你的RSSHub实例`

注意：2024 年以来**公共 Nitter 实例基本全部关闭**，公共 RSSHub 的 twitter 路由也多要求
自备凭证；这条路线通常需要你自行部署实例，仅作为技术兜底。配置后程序会自动按
"Nitter→RSSHub"顺序尝试，取不到就回落到公开新闻信源。

---

## 什么都不配会怎样？

程序不会报错：自动使用 OilPrice、EIA、Google News（中英文）等**公开 RSS 信源**出报告，
WTI/Brent 价格也正常，只是没有这 35 个 X 账号的逐条推文。

---

## 常见错误排查（check-token / 报告状态里的提示）

| 提示 | 原因与处理 |
|---|---|
| 鉴权失败(401) | Token 复制错/被重置；重新 Generate 后更新三处配置 |
| 鉴权失败(403) | 账号仍是免费套餐（无读取权限），或 App 未开通按次付费 |
| 触发限流(429) | 短时间请求过多；本程序已对账号间加 0.6s 间隔，等 15 分钟再试 |
| 未找到账号 @xxx | handle 写错或账号已改名；核对 `data/accounts.csv` |
| 网络错误 / timeout | 运行环境访问 api.twitter.com 受限；本地检查代理，云端换用网关 |
| 本地能用、Actions 不行 | 忘了在 GitHub 仓库 Secrets 添加 `X_BEARER_TOKEN`（.env 不会被提交） |

## 参考来源（计费规则，2026 年）

- X Developer Portal：<https://developer.x.com/en/portal>
- Is the Twitter API Free in 2026（费率表）：<https://www.getxapi.com/blogs/is-twitter-api-free>
- X/Twitter API Pricing Guide 2026：<https://www.blotato.com/blog/twitter-api-pricing>
- TwitterAPI.io 成本说明：<https://twitterapi.io/blog/x-api-cost-breakdown-2026>
