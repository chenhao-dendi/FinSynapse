<div align="right">

[English](./README.en.md) | **中文**

</div>

# FinSynapse 🌡️

> **个人多市场宏观流水线 + 市场温度计 + 可选 LLM 简评**，T+1 投资工作台。

[![CI](https://github.com/chenhao-dendi/FinSynapse/actions/workflows/ci.yml/badge.svg)](https://github.com/chenhao-dendi/FinSynapse/actions/workflows/ci.yml)
[![Daily](https://github.com/chenhao-dendi/FinSynapse/actions/workflows/daily.yml/badge.svg)](https://github.com/chenhao-dendi/FinSynapse/actions/workflows/daily.yml)
[![CodeQL](https://github.com/chenhao-dendi/FinSynapse/actions/workflows/codeql.yml/badge.svg)](https://github.com/chenhao-dendi/FinSynapse/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

📊 **在线看板**：<https://chenhao-dendi.github.io/FinSynapse/>（[中文](https://chenhao-dendi.github.io/FinSynapse/) ｜ [English](https://chenhao-dendi.github.io/FinSynapse/en.html)）

每日北京时间 06:00 自动更新：CN / HK / US 三市场综合温度 + 估值 / 情绪 / 流动性子分量 + 一周变化归因 + 五对硬编码背离信号 + 日度宏观简评。

---

## 1. 这是什么 / 不是什么

**是**：

- 跨市场（A/HK/US）宏观数据流水线 — Bronze/Silver/Gold 分层，幂等可重放
- 市场温度计 — 估值 / 情绪 / 流动性三维加权打分（0-100°）
- 可选 LLM 简评 — 本地跑 Ollama / DeepSeek / Anthropic，CI 不付费、不掉 key
- GitHub Actions 全自动跑通 + GitHub Pages 静态发布，**总成本 $0/月**

**不是**：

- 不是 Bloomberg / Wind 替代
- 不是实时交易 / 行情系统
- 不是回测框架
- 个股层延后到 Phase 4，主线只跑宏观

---

## 2. 5 分钟快速上手

```bash
git clone https://github.com/chenhao-dendi/FinSynapse.git
cd FinSynapse

# uv 比 pip 快 10-100x，详见 https://github.com/astral-sh/uv
uv sync --all-extras

cp .env.example .env
# .env 里只有 FRED_API_KEY 是推荐项（免费注册 https://fred.stlouisfed.org/docs/api/api_key.html）
# 没填也能跑，仅美股流动性子温度会少一个 DFII10 因子

# 拉数据（默认 lookback 5500 天 ≈ 15 年，首次 ~5 分钟）
uv run finsynapse ingest all

# bronze → silver（含百分位、健康检查、温度、背离）
uv run finsynapse transform run --layer all

# 渲染双语静态看板到 dist/
uv run finsynapse dashboard render

open dist/index.html        # macOS
# 或本地起 Streamlit 做交互式探索
uv run finsynapse dashboard serve
```

可选：本地跑 LLM 日报。

```bash
# .env 填好 DEEPSEEK_API_KEY 后
uv run finsynapse report brief --provider deepseek
# 产出 data/gold/brief/YYYY-MM-DD.md，可手动 commit 入库
```

---

## 3. 仓库结构

```
FinSynapse/
├── .github/
│   ├── workflows/         CI / 每日更新 / CodeQL 三个 workflow
│   └── ISSUE_TEMPLATE/    bug / feature / ci_failure 模板
├── config/
│   └── weights.yaml       温度计权重，可热改、立即生效（见 §5）
├── data/                  ── Medallion 分层 ──
│   ├── bronze/            原始 API 直出（gitignored，CI 重建）
│   ├── silver/            清洗 + 加工（gitignored，CI 重建）
│   └── gold/              叙事产物（入库，git 历史 = 认知历史）
│       └── brief/         每日宏观简评 .md（CI 自动 commit）
├── dist/                  双语静态看板渲染目标（gitignored，CI 推 gh-pages）
├── docs/
│   └── _local/            个人草稿与执行规划（gitignored）
├── scripts/               上游 API 探针（probe_*.py，upstream 改时复现）
├── src/finsynapse/
│   ├── config.py          pydantic-settings 读 .env
│   ├── cli.py             Typer 入口（ingest / transform / dashboard / notify / report）
│   ├── providers/         数据源抽象：akshare / yfinance / fred / multpl / treasury / hkma / hsi
│   ├── ingest/            bronze 落盘（薄壳）
│   ├── transform/         normalize → percentile → health_check → temperature → divergence
│   ├── dashboard/         Streamlit app + 双语静态 HTML 渲染（i18n + plotly）
│   ├── notify/            Bark / Telegram 状态变化推送
│   └── report/            brief 编排 + facts / llm / markdown 分层
├── tests/                 pytest + VCR 离线测试（CI 不发真实请求）
├── pyproject.toml         依赖、ruff 规则、Python 3.11+
├── .env.example           secret 清单
└── LICENSE                MIT
```

---

## 4. 数据分层

```
bronze/  原始：API 直出 + 时间戳，幂等覆盖
   ↓     （CI 每日 22:00 UTC 重建，gitignored）
silver/  加工：清洗 → 百分位 → 健康检查 → 温度 → 背离
   ↓     （同步 30 天 artifact 备份）
gold/    叙事：人类/LLM 读得懂的结论
         （入库；git log = 你的认知演化时间线）
```

| 层 | 写入方 | 是否入库 | 关键文件 |
|---|---|---|---|
| bronze | `finsynapse ingest` | ❌ | `data/bronze/{macro,flow,valuation}/<source>_<date>.parquet` |
| silver | `finsynapse transform run` | ❌ | `data/silver/{macro,percentile,temperature,divergence,health_log}_daily.parquet` |
| gold | LLM 或模板（CI / 本地） | ✅ | `data/gold/brief/YYYY-MM-DD.md` |

---

## 4.5 JSON API 端点

每日构建会同时把机器可读的 JSON 端点推到 GitHub Pages，方便外部 agent / 工具直接消费温度数据，无需爬 HTML：

| 端点 | 内容 |
|---|---|
| `/api/manifest.json` | Schema 版本 + asof + 分市场日期 + 构建时间 + 所有端点清单 |
| `/api/temperature_latest.json` | 三市场最新 overall + 子温度 + 一周变化归因 + 完整性/置信标记 |
| `/api/temperature_history.json.gz` | 全量历史时间序列（gzip） |
| `/api/indicators_latest.json` | 每个底层因子各自最新读数 + 5y/10y 滚动百分位 + 来源/陈旧天数 |
| `/api/divergence_latest.json` | 90 天内活跃背离信号，按产品强度排序 |

线上访问：`https://chenhao-dendi.github.io/FinSynapse/api/manifest.json`

当前 `schema_version = 2.0.0`。Schema 版本遵循 SemVer：新增字段是非破坏性变更，不强制 bump；删除字段、改名或改变现有字段语义才升 major。

`indicators_latest.json` v2 迁移说明：v1 的 `asof` 表示“全局最新日快照日期”，所有指标都来自同一天；v2 改为每个 indicator 输出自己的最新可用行，使用单条记录内的 `last_seen` 判断指标日期，`days_stale` 判断相对 API `asof` 滞后几天，`raw_percentile_asof` 表示 percentile 表原始最大日期。外部 consumer 如果假设所有指标同日，需要改读 `last_seen`。

---

## 5. 看板数值口径

### 5.1 市场温度计（0-100°）

每个 indicator 取**过去 N 年滚动百分位**作为基础信号。**窗口可逐指标覆盖**（[`config/weights.yaml`](./config/weights.yaml) 每个 indicator 的 `window:` 字段）：慢变量（PE / CAPE / M2 / 社融 / 实际利率）默认 `pct_10y` 锚长期均值，快变量（VIX / 信用利差 / 资金流 / DXY / 短端利率）切到 `pct_5y` 反映当前 regime；月/周频指标（CAPE / M2 / 社融 / NFCI）自动 ffill 到日度。

每个子温度的 indicator 用 `direction` 字段决定方向：

- `+` ：高分位 → 高温（如 CAPE 高 = 估值热）
- `-` ：高分位 → 低温（如 VIX 高 = 恐慌 = 冷；DXY 强 = 流动性紧 = 冷）

子温度 = 该子项下各 indicator 的加权平均；**任一指标缺失会自动按可用权重重归一**（如北向 2024-08 后停更时不会拉垮整个 CN 情绪温度，详见 §5.7）。

综合温度按市场各自的子权重合成：

| 市场 | valuation | sentiment | liquidity | 设计依据 |
|---|---:|---:|---:|---|
| CN | 0.65 | 0.20 | 0.15 | A 股估值定调；情绪四因子（北向/换手/两融/CNY压力）；M2+社融+信用脉冲+SHIBOR-1W |
| HK | 0.60 | 0.25 | 0.15 | EWH 股息率锚估值；南向+VHSI 情绪；HIBOR-1M+US 利率/DXY 流动性 |
| US | 0.35 | 0.45 | 0.20 | PE+CAPE+ERP 三因子估值；VIX+HY OAS+UMich 情绪；实际利率+DXY+NFCI+WALCL 流动性 |

**温度区间**（[`src/finsynapse/notify/state.py`](./src/finsynapse/notify/state.py)）：

- `< 30°` ❄️ 冷
- `30 - 70°` 🌤 中
- `≥ 70°` 🔥 热

完整指标 → 子温度映射见 §5.2 与 [`config/weights.yaml`](./config/weights.yaml)，改完 `transform run --layer temperature` 立刻生效，**不需要重抓 bronze**（百分位基线本身不依赖权重）。

回测验证（[`scripts/backtest_temperature.py`](./scripts/backtest_temperature.py) + [`scripts/run_validation.py`](./scripts/run_validation.py)）：从 [`backtest_pivots.yaml`](./scripts/backtest_pivots.yaml) 加载 25 个历史关键时点（US 9、CN 8、HK 8）。Gate 要求多因子在 ≥2/3 市场中击败 PE 单因子基准，且前瞻 Spearman ρ 为负（均值回归信号）。当前 gate 3/3 PASS，详见验证报告。

### 5.2 指标清单

每市场 3 个子温度由若干基础 indicator 加权。**方向** `+` = 百分位高 → 高温；`-` 反向。**窗口** `5y` 用于 regime 切换快的指标，`10y` 用于慢变量。

#### US（综合 0.35 val + 0.45 sent + 0.20 liq）

| 子温度 | 指标 | 权重 | 方向 | 窗口 | 来源 | 备注 |
|---|---|---:|---|---|---|---|
| val | `us_pe_ttm` | 0.35 | + | 10y | multpl.com | S&P500 TTM PE |
| val | `us_cape` | 0.35 | + | 10y | multpl.com | Shiller 10Y 平滑 EPS |
| val | `us_erp` | 0.30 | − | 10y | derived | `100/PE − 实际利率`，破"PE 永远高位"困境 |
| sent | `vix` | 0.40 | − | 5y | yfinance | 隐含波动率 = 恐慌 |
| sent | `us_hy_oas` | 0.35 | − | 5y | FRED `BAMLH0A0HYM2` | HY 信用利差，⚠️ FRED 自 2026-04 仅返回 3Y 滚动 |
| sent | `us_umich_sentiment` | 0.25 | + | 10y | FRED `UMCSENT` | 密歇根大学消费者信心 |
| liq | `us10y_real_yield` | 0.25 | − | 10y | FRED `DFII10` | 实际利率高 = 紧 |
| liq | `dxy` | 0.15 | − | 5y | yfinance | 美元强 = 全球流动性紧 |
| liq | `us_nfci` | 0.35 | − | 5y | FRED `NFCI` | Chicago Fed 综合金融条件 |
| liq | `us_walcl` | 0.25 | + | 5y | FRED `WALCL` | 美联储资产负债表（QE/QT 周期） |

#### CN（综合 0.65 val + 0.20 sent + 0.15 liq）

| 子温度 | 指标 | 权重 | 方向 | 窗口 | 来源 | 备注 |
|---|---|---:|---|---|---|---|
| val | `csi300_pe_ttm` | 0.50 | + | 10y | AkShare | 沪深 300 TTM PE |
| val | `csi300_pb` | 0.50 | + | 10y | AkShare | 沪深 300 PB |
| sent | `cn_north_5d` | 0.25 | + | 5y | AkShare | 北向 5d 净买入，⚠️ 监管原因 2024-08 后日频停更 |
| sent | `cn_a_turnover_5d` | 0.25 | + | 5y | AkShare | A 股总成交额 5d 均 |
| sent | `cn_margin_balance` | 0.35 | + | 5y | AkShare | SH+SZ 两融余额 |
| sent | `cn_usdcny_pressure` | 0.15 | − | 5y | derived | USD/CNY 汇率 → 人民币压力，高 = 资本外流压力 = 冷 |
| liq | `cn_m2_yoy` | 0.25 | + | 10y | AkShare | M2 同比 |
| liq | `cn_social_financing_12m` | 0.25 | + | 10y | AkShare | 社融 12M 滚动求和 |
| liq | `cn_credit_impulse` | 0.25 | + | 5y | derived | 社融 YoY 加速度，捕捉信贷扩张/收缩动能 |
| liq | `cn_dr007` | 0.25 | − | 5y | AkShare | 实为 SHIBOR-1W（DR007 无免费日频源） |

#### HK（综合 0.60 val + 0.25 sent + 0.15 liq）

| 子温度 | 指标 | 权重 | 方向 | 窗口 | 来源 | 备注 |
|---|---|---:|---|---|---|---|
| val | `hk_ewh_yield_ttm` | 1.00 | − | 10y | yfinance EWH | TTM 股息率（高 = 便宜 = 冷） |
| sent | `cn_south_5d` | 0.60 | + | 5y | AkShare | 南向 5d 净买入 |
| sent | `hk_vhsi` | 0.40 | − | 5y | AkShare | 恒指波幅指数（HK 版 VIX） |
| liq | `us10y_real_yield` | 0.30 | − | 10y | FRED `DFII10` | 联系汇率借用 US 利率 |
| liq | `dxy` | 0.20 | − | 5y | yfinance | 联系汇率借用 USD 强弱 |
| liq | `hk_hibor_1m` | 0.50 | − | 5y | AkShare | HKD 端实际融资成本 |

> **HK 原生估值因子暂未接入权重**：AkShare `stock_hk_index_value_em` 接口在当前版本中不存在，`stock_hk_index_daily_em` 仅返回价格。最新 probe 发现恒生指数公司官方 Monthly Roundup PDF 含 HSI PE Ratio / Dividend Yield 行，`hsi_monthly_valuation` 已能作为手动 collected-only source 采集月初发布的 PDF，因此 `hk_native_valuation` 已推进为 source_ready；2019-07-03..2026-05-07 live backfill 已解析 76 个月样本，但当前 archive discovery 漏 7 个发布月，生产权重暂继续使用 EWH 股息率代理，待全量 archive 覆盖、parser hardening、fixture backfill 和 gate review 通过后再切换。
> - **AH 溢价指数**：历史时间序列接口全部 404，仅 spot 接口可用（无历史回填，需自行积累月级才有信号）
> - **HSI 期权 PCR**：HKEX 不开放免费日频；详见 plan §11.6 v0.6 决策

#### 已采集但暂不加权的权威候选序列

这些序列会进入 bronze / silver，供后续回测和因子设计使用；在完成 transform 设计和 champion gate 验证前，不纳入温度计权重。

| Indicator | 来源 | 口径 | 后续用途 |
|---|---|---|---|
| `us3m_yield` | U.S. Treasury Daily Treasury Rates | 3M 名义国债收益率（百分点） | 美国短端利率 / 现金收益率锚 |
| `us_t10y3m` | FRED `T10Y3M` + U.S. Treasury Daily Treasury Rates | 10Y 美债收益率 − 3M 国库券利率（百分点） | 美国收益率曲线 / 衰退压力候选；需非单调 stress transform |
| `us_baa10y_spread` | FRED `BAA10Y` | Moody's Baa 公司债收益率 − 10Y 美债收益率（百分点） | 美国长期信用利差候选；不直接替代 HY OAS，需 transform / gate 验证 |
| `us_on_rrp` | FRED `RRPONTSYD` | Fed overnight reverse repo Treasury securities sold（USD bn） | 美国隔夜逆回购 / 准备金抽水候选；可为 0，需独立 transform |
| `us_reserve_balances` | FRED `WRESBAL` | Reserve balances with Federal Reserve Banks（USD mn） | 美国银行体系准备金候选；可与 WALCL/TGA/ON RRP 研究 net liquidity |
| `us_effr` | FRED `EFFR` | Effective Federal Funds Rate（%） | 美国无担保隔夜资金利率候选；需 spread / cycle-aware transform |
| `us_sofr` | FRED `SOFR` | Secured Overnight Financing Rate（%） | 美国担保隔夜 repo 利率候选；2018+，需 spread / cycle-aware transform |
| `us_cape_shiller` | Robert Shiller online data workbook | Shiller CAPE 原始学术数据 | `us_cape` 的权威交叉验证序列；不覆盖当前 multpl 权重源 |
| `us_tga_balance` | U.S. Treasury FiscalData DTS | Treasury General Account closing balance；旧版 Table I 用 operating-cash components 合计（USD mn） | 美国财政部现金余额 / 流动性抽水候选；live check 可取回 2007+ |
| `us_tga_deposits` | U.S. Treasury FiscalData DTS | Daily total TGA deposits（USD mn） | 美国财政现金流入候选；当前 API 2022+ |
| `us_tga_withdrawals` | U.S. Treasury FiscalData DTS | Daily total TGA withdrawals（USD mn） | 美国财政现金流出候选；当前 API 2022+ |
| `hk_aggregate_balance` | HKMA Open API | Aggregate Balance after Discount Window，HK$ mn | HKD 银行体系流动性候选 |
| `hk_monetary_base` | HKMA Open API | Total Monetary Base before Discount Window，HK$ mn | HK 货币基础长期锚 |
| `hk_hsi_pe` | Hang Seng Indexes Monthly Roundup PDF | 恒生指数 PE Ratio（Times） | HK 原生估值候选；PDF archive source，需手动 backfill 与 gate 验证 |
| `hk_hsi_dividend_yield` | Hang Seng Indexes Monthly Roundup PDF | 恒生指数 Dividend Yield（%） | HK 原生股息率候选；暂不替换 EWH proxy |

### 5.3 数据新鲜度与完整性

`silver/temperature_daily.parquet` 的原始最新日期（`raw_temperature_asof`）可能包含不完整的行（如某市场当日只有 liquidity 子温度更新）。Dashboard 会从最近 10 个交易日中选最完整的一行展示，并在每个市场卡片和 JSON API 中标注**实际使用的数据日期**（`market_asof`）和**最新完整日期**（`latest_complete_date`）。页面头部展示的是**页面生成时间**，市场数据日期按 CN/HK/US 分开显示。

`temperature_daily` 包含以下完整性字段：
- `subtemp_completeness` — 0-3，当前有多少个子温度可用
- `conf_ok` — 0/1，子温度内部置信度门槛是否通过；也会导出到每个市场的 `temperature_latest.json` payload
- `is_complete` — True 当 subtemp_completeness == 3
- `data_quality` — `ok` 或 `<sub>_unavailable`（标注缺失的子温度）

综合温度使用 **dispersion-weighted overall**：当子温度内部指标分歧大（max-min > 50pp），该子温度对综合温度的实际贡献会被削弱。分歧小的子温度获得更高置信权重。

### 5.4 一周温度变化归因

把过去 7 日 `Δoverall` 拆成 `Δval / Δsent / Δliq` 各自贡献，看板和简评里都列出来。**不用动态权重**——避免曲线拟合，权重一旦订就锁死，方向变化只来自指标本身。

### 5.5 背离信号

固定 5 对硬编码 `SignalPair`（[`src/finsynapse/transform/divergence.py`](./src/finsynapse/transform/divergence.py)）：

| 信号对 | 正常关系 | 背离含义 |
|---|---|---|
| `sp500_vix` | 反向 | 涨同时恐慌也涨 → 警惕假突破 |
| `us10y_dxy` | 同向 | 利率上美元下 → 信用 / 通胀机制切换？ |
| `gold_real_rate` | 反向 | 实际利率上金价也上 → 避险 / 去美元化主导 |
| `hsi_southbound` | 同向 | 港股涨但南向流出 → 外资主导，缺内地接力 |
| `csi300_volume` | 同向 | 上涨但缩量 → 警惕派发 |

`strength = |a%Δ| × |b%Δ| × 100`，分四档（≥ 0.5 / 0.1 / 0.01 / 其他）。这个口径优先展示“两边都发生了实质性移动”的背离，而不是一边大动、另一边几乎没动的噪声；近 90 天实测分桶为 `<0.01` 89 条、`0.01-0.1` 40 条、`0.1-0.5` 10 条、`>=0.5` 14 条，因此当前阈值先保持不变。

> 选硬编码 5 对而非统计异常检测——每对都有明确金融含义，过度通用化会淹没信号。

### 5.6 数据健康

每个 indicator 在 [`src/finsynapse/transform/health_check.py`](./src/finsynapse/transform/health_check.py) 有 plausibility bound（如 `vix: 5-200`、`us10y_yield: 0.1-25`、`csi300: 1000-20000`）：

- 越界 → `fail`，丢弃该行
- 跳跃 > 5σ → `warn`，保留但记录到 `health_log.parquet`

设计意图：抓 unit drift / 解析错误（如某天价格 ×100），不抓「极端但合法」的行情移动（那是百分位机器要识别的）。

### 5.7 数据降级标记

`temperature_daily.parquet` 的 `data_quality` 字段记录该行实际可用情况，不阻断输出：

- `ok` — 三个子温度全部产出
- `<sub>_unavailable` — 该子温度当天所有指标都缺数据（如 `liquidity_unavailable`）
- 子温度内单指标缺失：自动按可用权重重归一，不进 `data_quality`，但回退过程显式见 §5.1（如 CN 北向 2024-08+ 停更后情绪从 0.35/0.25/0.40 → 0/0.38/0.62 自动归一）

### 5.8 日报（gold/brief）

`finsynapse report brief` 优先级：`auto` 模式按 `ollama → deepseek → anthropic` 顺序尝试，**全失败时落到 deterministic Jinja 模板**，永远产出有效 .md。

CI 默认用 `deepseek-v4-pro`（2026-05-31 前折扣同 v4-flash 价位；过期后改回 v4-flash）。本地可以用 `--provider ollama` 跑离线模型零成本。

### 5.9 权重改动流程 (champion-challenger gate)

更改 `config/weights.yaml` 或 `src/finsynapse/transform/` 下任何文件时，**必须先通过本地 gate 验证**，防止退化上线。

**机械流程**：

1. **grid_search**（如改 sub_weight）：`uv run python scripts/grid_search_weights.py` 生成候选权重
2. **suite**：`uv run python -m finsynapse.eval.suite --silver tests/fixtures/eval_silver_2026Q1 --weights config/weights.yaml --out /tmp/latest.json`
3. **gate 本地 PASS**：`uv run python -m finsynapse.eval.gate --champion eval/champion.json --challenger /tmp/latest.json`
4. **开 PR**：正常提 PR
5. **CI eval-gate PASS**：PR diff 触及 eval-relevant 路径时自动跑 gate
6. **merge → promote**：merge 到 main 后在 main 分支上执行：

```bash
uv run python scripts/promote_champion.py \
    --latest /tmp/latest.json \
    --commit-sha $(git rev-parse --short HEAD) \
    --pr "https://github.com/.../pull/N" \
    --reason "简述改进原因"
```

**Gate 规则**（见 `src/finsynapse/eval/champion.py`）：

| 指标 | 方向 | 容忍度 | 级别 |
|---|---|---|---|
| `pivot_directional_rate` | higher_better | 0 | block |
| `mean_reversion_strength.3m.us` | higher_better | 0.02 | block |
| `mean_reversion_strength.3m.cn` | higher_better | 0.02 | block |
| `mean_reversion_strength.3m.hk` | higher_better | 0.02 | block |
| `pivot_strict_rate` | higher_better | 0 | warn |

> `mean_reversion_strength = -ic_mean`，把"IC 期望为负"翻译成"越大越好"。

---

## 6. GitHub Actions 与分支策略

### 6.1 三个 workflow

| Workflow | 触发 | 职责 | 写权限 |
|---|---|---|---|
| [`ci.yml`](./.github/workflows/ci.yml) | push main / PR | ruff lint + format check + pytest（py 3.11/3.12 矩阵） | 只读 |
| [`daily.yml`](./.github/workflows/daily.yml) | cron `30 9 * * 1-5` UTC（北京工作日 17:30，中港收盘后）+ `0 22 * * *` UTC（北京 06:00，美股收盘后）+ 手动 | ingest → transform → brief → render → 推 brief 回 main + 推 dist 到 gh-pages + notify + 上传 silver artifact | `contents:write` + `issues:write` |
| [`codeql.yml`](./.github/workflows/codeql.yml) | push / PR / 周一 03:00 UTC | Python 静态安全 / 质量分析（`security-and-quality`） | `security-events:write` |

`daily.yml` 失败会**自动开 issue**（label `ci-failure`），列出常见 culprit 与重跑入口；任何上游 API 改动（AkShare / multpl / yfinance / U.S. Treasury / HKMA）通常都先在这里浮现。

### 6.2 分支职责

| 分支 | 职责 | 写入方 |
|---|---|---|
| `main` | 源码 + 配置 + tests + 公开 docs + `data/gold/brief/*.md` | 人 + `daily.yml`（自动 commit + rebase 重试 ×3） |
| `gh-pages` | 纯静态站点，`dist/` 内容；`force_orphan` 不留历史 | `daily.yml` 唯一写入，**本地永不动** |
| `feature/*` | 任何变更都开新分支 → PR → main | 协作者 |

### 6.3 数据更新策略

- bronze / silver **永远 gitignored**，每天 CI 全量重抓重建（lookback 5500 天 ≈ 15 年），保证幂等可重放
- `data/gold/brief/*.md` 入库 → 历史可比对、可 git blame 追溯叙事变化
- silver 同时上传成 **30 天 artifact**（`silver-<run_id>.zip`），应急回放或本地复现用

### 6.4 Secrets 红线

| Secret | 必需？ | 用途 |
|---|---|---|
| `FRED_API_KEY` | 推荐 | US 实际利率（DFII10）+ HY 信用利差（BAMLH0A0HYM2，FRED 仅 3Y 滚动）+ 金融条件指数（NFCI 全历史）+ 收益率曲线（T10Y3M，暂不加权；同时有 keyless Treasury 交叉校验）+ Baa/10Y 信用利差候选（BAA10Y，暂不加权）+ ON RRP / reserve balances / overnight rates 流动性候选（RRPONTSYD / WRESBAL / EFFR / SOFR，暂不加权） |
| `DEEPSEEK_API_KEY` | 可选 | CI 里跑日报；不填用模板兜底 |
| `BARK_DEVICE_KEY` | 可选 | iOS 推送 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 可选 | TG 推送 |

🚫 **`ANTHROPIC_API_KEY` 与任何高价付费 LLM key 永不入 CI**。所有付费 LLM 调用一律本地跑，避免成本失控与 key 暴露。

---

## 7. 本地开发

```bash
# 装含 dev 依赖
uv sync --all-extras

# 任何子命令查 help
uv run finsynapse --help
uv run finsynapse transform --help

# 跑离线测试（VCR/fixture，不发真实请求；如果哪天联网了，CI 会超时报错——by design）
uv run pytest -q

# 提交前必跑
uv run ruff check src tests
uv run ruff format --check src tests
uv run python scripts/check_data_source_catalog.py
uv run python scripts/build_eval_fixture_manifest.py --verify
uv run python scripts/summarize_data_audit.py
# 可选：比较候选 fixture 与当前基线，生成 PR 结论
uv run python scripts/compare_eval_fixtures.py --candidate /tmp/finsynapse_candidate_fixture
# 可选：手动回填官方 HSI 月度估值 PDF（需要 pdftotext / poppler-utils）
uv run finsynapse ingest run --source hsi_monthly_valuation --lookback-days 730

# 本地交互式看板
uv run finsynapse dashboard serve --port 8501
```

详细的本地 → CI 部署指引见 [`docs/_local/2026-04-29-deploy-guide.md`](./docs/_local/2026-04-29-deploy-guide.md)（gitignored，仅作者本地可见）。

---

## 8. CONTRIBUTING

欢迎 PR。提交前请过下面这些。

### 8.1 Issue 入口

仓库已配 [issue 模板](./.github/ISSUE_TEMPLATE/)：

- 🐛 **Bug report** — 行为不符合预期
- ✨ **Feature request** — 想加新指标 / 新市场 / 新看板
- 🔥 **CI failure** — 通常 daily.yml 会自动开，无需手动

### 8.2 PR 流程

1. fork → 开 `feature/<short-slug>` 分支
2. 跑通 `uv run ruff check && uv run ruff format --check && uv run pytest -q`
3. 提 PR → main，CI 必须**全绿**才进 review
4. PR 描述里说清「改了什么 + 为什么 + 怎么验证」

### 8.3 Commit 规范

使用类型前缀：`feat / fix / chore / docs / test / refactor / ci`，正文中文 / 英文均可。

```
feat(temperature): add HK index PCR via HKEX scrape
fix(akshare): handle empty north-flow response post-2024-08
chore(deps): bump pandas to 3.0.3
```

### 8.4 代码规范

- ruff line-length 120，配置在 [`pyproject.toml`](./pyproject.toml)，编辑器请打开 format on save
- **新增 provider**：实现 [`providers/base.py`](./src/finsynapse/providers/base.py) 的统一接口，落 bronze、`return (df, path)`；同步更新 [`config/data_sources.yaml`](./config/data_sources.yaml)，并跑 `uv run python scripts/check_data_source_catalog.py`
- **新增 silver transform**：在 [`cli.py`](./src/finsynapse/cli.py) `transform run` 中显式串入 + 写一条对应 pytest
- **新增温度计 indicator**：
  1. 在 [`config/weights.yaml`](./config/weights.yaml) 加权重（子项权重和为 1.0；可选 `window: pct_5y` 覆盖默认窗口，快变量推荐 5y）
  2. 在 [`health_check.PLAUSIBLE_BOUNDS`](./src/finsynapse/transform/health_check.py) 加上下界（防 unit drift）
  3. 在 [`config/data_sources.yaml`](./config/data_sources.yaml) 标注来源、权威层级、usage（`weighted` / `collected_only` 等）
  4. 跑 [`scripts/backtest_temperature.py`](./scripts/backtest_temperature.py) 验证关键时点方向不翻车
  5. 派生指标（用其他 indicator 算出来的，如 `us_erp`）写在 [`transform/normalize.py:derive_indicators()`](./src/finsynapse/transform/normalize.py)
  6. 上游 API 不确定的指标先写 `scripts/probe_*.py` 探针验证再实现（参考 `probe_phase_b.py`）

### 8.5 测试要求

- provider PR **必须**带 VCR cassette 或 pickle fixture（CI 不发网络请求）
- transform 改动**必须**带覆盖新行为的单测
- 任何会让现有 12+ 测试变红的改动都需要在 PR 里说清楚为什么

### 8.6 不接受的内容

- 把 `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 等付费 LLM key 写进 workflow 或 GitHub Secret
- 引入需付费才能稳定访问的数据源
- 引入 Streamlit 之外的前端框架（保持「单文件 HTML 出 GitHub Pages」的最小依赖原则）
- 在 `main` 分支直接推 `data/bronze/` 或 `data/silver/`（已被 gitignore 保护，但请别 force push 绕过）

---

## 9. License & 致谢

[MIT](./LICENSE) © 2026 hg.dendi

数据与生态致谢：

- **AkShare** — A 股 / HK / 宏观数据
- **yfinance** — 美股与跨市场行情
- **FRED** — 美国宏观时间序列
- **U.S. Treasury / HKMA / Hang Seng Indexes** — 官方利率曲线、Daily Treasury Statement、香港货币基础与 HSI Monthly Roundup 数据
- **Robert Shiller online data** — Shiller CAPE 学术数据，用于交叉验证 multpl CAPE
- **multpl.com** — Shiller CAPE 历史回溯
- **DeepSeek / Anthropic / Ollama** — LLM 叙事生成
- **uv / ruff / pytest** — astral-sh 系工具链
