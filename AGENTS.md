# AGENTS.md

> 本文件被 Codex、opencode、Cursor 等支持 `AGENTS.md` 约定的 agent 读取。
> Claude Code 用户请同时参考 `.claude/skills/`。

## 项目简介

**FinSynapse** 是一个金融研究与日报项目，主要产出：
- 每日宏观日报（`research/`、`dist/` 输出）
- 个股 / 行业研究报告（`research/stocks/`、`research/industry/`）

## 当前 agent 工作流

### 公司分析报告（最常见的 agent 任务）

当用户要求"写一份 X 公司的分析报告"、"做 XX (ticker) 的深度研究"、"按公司分析模板写一下 XXX"、"/company-analysis" 时：

#### 1. 强制读取（每次执行必做，不允许使用记忆中的旧版本）

按顺序读取以下文件：

1. `research/templates/company-analysis.md` （主 spec，当前 v0.2）
2. `research/templates/report-frontmatter.md` （frontmatter 字段定义）
3. `research/templates/references/data-source-policy.md` （数据来源优先级 + 三必标审计线索）
4. `research/templates/references/industry-metrics.md` （行业 packs；按公司行业引用对应章节）
5. `research/templates/references/cross-market-policy.md` （仅当 `markets` 含 ≥2 市场时读，如 AH/ADR 双股）
6. `research/templates/references/valuation-methods.md` （估值方法规范）
7. `research/templates/assets/report-quality-checklist.md` （报告完成度与 sanity 自检）

#### 2. 命名规则（来自主 spec §2）

`research/stocks/<market>/<ticker>-<slug>-YYYYMMDD.md`

- `market`：`cn` / `hk` / `us`
- `ticker`：A 股代码（`688981`）/ 港股带 `-HK`（`00981-HK`）/ 美股代码（`NVDA`）
- `slug`：英文小写短名（`smic` / `nvidia`）
- 示例：`research/stocks/hk/00981-HK-smic-20260505.md`

A/H/ADR 同公司分别建文件，**遵循 cross-market-policy.md 主从报告规则**：流动性更好的市场为主报告，从报告 §1-§4 允许引用 + 摘要表。

#### 3. 落盘前检查同标的报告

在 `research/stocks/<market>/` 下查找是否已存在同 ticker 的报告：
- 如有，**询问用户**：是更新现有报告（沿用文件名，更新 `last_material_update`）还是新建快照（用今日日期生成新文件）
- 不要默认覆盖

#### 4. 撰写要点

按主 spec §4 正文骨架逐节产出。重点：

- TL;DR ≤200 字，独立可读
- **每个关键数字**带 `as_of` + 来源 + 口径（详见 data-source-policy.md "三必标"）
- L4/L5 来源（媒体/web search）**不能用作硬数字主来源**
- 估算值显式标注 `(估算)` / `(假设：xx)`
- 第 7 章必须包含：**§7.0 维度评级矩阵**（6 维 ★1-★5）+ thesis + 强化/削弱/证伪事件 + 重审日期
- `## Meta` 段必填（数据缺口 + 不适用章节为强制；模板改进建议为可选）

#### 5. 自检（写完报告必做）

按 `assets/report-quality-checklist.md` 逐条检查（A1-A6 + B1-B7）；跨市场报告额外检查 C1-C4。

按 checklist 的 Gate 类型处理：
- `hard_fail` 未通过：阻断报告产出，回头补数据、改结论或改写文本
- `requires_explanation` 未通过：可落盘，但必须在正文或 `## Meta` 段说明原因
- `not_applicable` 项：必须在 `## Meta → 不适用章节` 中说明

#### 6. 更新索引

报告写完后**必须**更新 `research/README.md` 对应市场（cn/hk/us）的表格，加一行新报告（含模板版本）。

#### 7. 模板改进建议（自迭代机制）

如果撰写过程中发现模板/规范有不足：

- **不允许**直接修改 `research/templates/` 下的任何文件
- 必须在 `research/templates/_proposals/` 下按 `TEMPLATE.md` 格式新建一个 proposal 文件，命名 `YYYYMMDD-<slug>.md`
- 同时在报告 `## Meta → 模板改进建议` 中简述并引用 proposal 文件路径

## 强制约束（薄壳原则，所有 agent 通用）

- ❌ 不要凭记忆撰写——每次都要重读 spec
- ❌ 不要把模板章节复制进 AGENTS.md / SKILL.md / 其他 agent 配置文件——薄壳原则，所有内容只在 `research/templates/` 维护
- ❌ 不要直接改主 spec / references / assets——只走 proposal
- ❌ 不要默认覆盖已有报告——先问用户
- ❌ 不要给"买入/卖出/目标价"——评级用主 spec §6 的"积极/中性/谨慎/回避"，配套 thesis + 强化/削弱/证伪事件
- ❌ 不要把 web search 摘要当硬数字来源
- ❌ 不要在报告里跨章节复制内容（如 Bull case 在 TL;DR 写一遍、§5.1 又写一遍）

## 项目其他常用入口

| 入口 | 说明 |
|------|------|
| `README.md` / `README.en.md` | 项目总体说明（中英文） |
| `docs/_local/` | 本地工作笔记、计划文档（不公开发布） |
| `research/README.md` | 研究报告索引 + 撰写规范 |
| `research/templates/` | 模板与规范的唯一真源 |
| `.claude/skills/` | Claude Code 专属 skill 配置 |
| `pyproject.toml` | Python 项目配置（uv 管理） |
| `scripts/` | 数据脚本与日报生成工具 |

## 通用代码与提交约定

- Python 项目（`uv` 管理依赖）；提交前确保通过 ruff / pytest
- Commit message 风格：`feat(<scope>): <短描述>` / `chore(<scope>): ...` / `refactor(<scope>): ...` / `fix(<scope>): ...`
- 涉及研究报告的 commit 走 `feat(research)` 或 `chore(brief)`
- 不要在未授权情况下 push 到远程
