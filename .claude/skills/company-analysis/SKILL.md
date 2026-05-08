---
name: company-analysis
description: 撰写一份遵循 FinSynapse 公司分析模板规范的个股研究报告。当用户要求"写一份 X 公司的分析报告"、"做 XX (ticker) 的深度研究"、"按公司分析模板写一下 XXX"、"/company-analysis"时触发。
---

# Company Analysis Skill

本 skill **不复刻模板内容**——所有规则、字段、章节、checklist 都在 `research/templates/` 下，每次执行都重新读取。

## 流程

### 1. 强制读取（每次执行必做，不允许使用记忆中的旧版本）

按顺序读取：
1. `research/templates/company-analysis.md`（主 spec）
2. `research/templates/report-frontmatter.md`（frontmatter 字段）
3. `research/templates/references/data-source-policy.md`（数据规范）
4. `research/templates/references/industry-metrics.md`（行业 packs，按公司行业引用对应章节）
5. `research/templates/references/cross-market-policy.md`（仅当 `markets` 含 ≥2 市场时读，如 AH/ADR 双股）
6. `research/templates/references/valuation-methods.md`（估值方法规范）
7. `research/templates/assets/report-quality-checklist.md`（自检清单与 Gate 类型）

### 2. 前置验证输出（v0.2 引入）

完成第 1 步读取后，在开始撰写前输出以下验证清单（向用户显式展示所有前置条件已满足）：

```
前置验证：
- [x] 已读取 company-analysis.md（主 spec，当前 v0.3）
- [x] 已读取 report-frontmatter.md（frontmatter 字段）
- [x] 已读取 data-source-policy.md（数据来源规范 + 三必标）
- [x] 已读取 industry-metrics.md（行业指标包）
- [x] 已读取 cross-market-policy.md（跨市场规范；仅 markets ≥2 时需要）
- [x] 已读取 valuation-methods.md（估值方法规范）
- [x] 已读取 report-quality-checklist.md（自检清单 + Gate 类型）
```

凡未读取或不适用的项标注 `[N/A]` 并简述原因（如单市场标的跨市场政策不适用）。

### 3. 落盘前检查同标的报告

在 `research/stocks/<market>/` 下查找是否已存在同 ticker 的报告：
- 如有，**询问用户**：是更新现有报告（沿用文件名，更新 `last_material_update`）还是新建快照（用今日日期生成新文件）
- 不要默认覆盖

### 4. 命名规则（来自主 spec 第 2 节）

`research/stocks/<market>/<ticker>-<slug>-YYYYMMDD.md`
- `market`：`cn` / `hk` / `us`
- `ticker`：A 股代码 / 港股带 `-HK` / 美股代码
- `slug`：英文小写短名
- 例：`research/stocks/hk/00981-HK-smic-20260505.md`

A/H/ADR 同公司分别建文件，frontmatter `tickers` 字段交叉引用。

### 5. 撰写

按主 spec 第 4 节正文骨架逐节产出。重点：
- TL;DR ≤200 字、独立可读
- 每个关键数字带 `as_of` + 来源 + 口径（详见 data-source-policy.md）
- 估算值显式标注 `(估算)` / `(假设：xx)`
- L4/L5 来源不能用作硬数字主来源
- 第 7 章必须包含 thesis + 强化/削弱/证伪事件 + 重审日期
- `## Meta` 段必填

### 6. 自检（写完报告必做）

按 `assets/report-quality-checklist.md` 逐条检查，并按 Gate 类型处理：

- `hard_fail` 未通过：阻断报告产出，回头补数据、改结论或改写文本
- `requires_explanation` 未通过：可落盘，但必须在正文或 `## Meta` 段说明原因
- 跨市场报告额外检查 C1-C4

### 7. 更新索引

报告写完后**必须**更新 `research/README.md` 对应市场（cn/hk/us）的表格，加一行新报告。

### 8. 模板改进建议

如果撰写过程中发现模板/规范有不足：
- **不允许**直接修改 `research/templates/` 下的任何文件
- 必须在 `research/templates/_proposals/` 下按 `TEMPLATE.md` 格式新建一个 proposal 文件
- 同时在报告 `## Meta → 模板改进建议` 中简述并引用 proposal 文件路径

## 不要做的事

- ❌ 不要凭记忆撰写——每次都要重读 spec
- ❌ 不要把模板章节复制进本 SKILL.md——薄壳原则
- ❌ 不要直接改主 spec / references / assets——只走 proposal
- ❌ 不要默认覆盖已有报告——先问用户
- ❌ 不要给"买入/卖出/目标价"——评级用主 spec 第 6 节的"积极/中性/谨慎/回避"
- ❌ 不要把 web search 摘要当硬数字来源
