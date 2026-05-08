# 模板改进建议：§7 thesis 增加 scorecard 表格格式

> 提出日期：2026-05-08
> 提出人 / agent：opencode-DeepSeek（参考 anthropics/financial-services thesis-tracker）
> 状态：merged 2026-05-08 → v0.3
> 优先级：P1
> 目标版本：v0.3

## 1. 出现在哪份报告

无关联报告——模板设计层面改进。灵感来自 anthropics/financial-services 仓库 `equity-research/skills/thesis-tracker/SKILL.md` 第 3 节（Thesis Scorecard）。

## 2. 建议改哪个文件 / 哪一节

- 文件：`research/templates/company-analysis.md`
- 章节：§7.2（当前 Thesis）
- 改动类型：新增（增加推荐格式，不替换现有格式）

## 3. 问题描述

当前 §7.2 只要求一句话 thesis，但没有提供追踪结构。实践中一个好的 thesis 通常包含多个支柱（pillar），每个支柱有独立的预期和验证方式。

参考 thesis-tracker 的 scorecard 格式：

```
| Pillar | Original Expectation | Current Status | Trend |
|--------|---------------------|----------------|-------|
| Revenue growth >20% | On track | Q3 was 22% | Stable |
| Margin expansion | Behind | Margins flat YoY | Concerning |
```

这种格式的优点：
1. 把 thesis 从一句话拆成可追踪的多根支柱
2. 每根支柱有"预期 vs 实际"的对照
3. Trend 列让读者一眼看到哪些在改善、哪些在恶化
4. 与 §7.3-7.5（强化/削弱/证伪事件）自然衔接

## 4. 建议改法

在 §7.2 骨架中，将单行改为**推荐格式 + 保留纯文本兼容**：

```markdown
7.2 **当前 Thesis**（推荐 scorecard 格式；也可纯文本一句话）
```

新增 §5.4.2（Thesis Scorecard 格式说明）：

```markdown
### 5.4.2 Thesis Scorecard 格式（v0.3，推荐使用）

当 thesis 含多个独立支柱时，推荐用 scorecard 表格替代纯文本一句话。

| Pillar | Original Expectation | Current Status | Trend |
|--------|---------------------|----------------|-------|
| 支柱 1（如"毛利率 ≥25%"） | 预期是什么 | 当前实际值/状态 | 改善/稳定/恶化/新 |
| 支柱 2 | ... | ... | ... |
| 支柱 3 | ... | ... | ... |

**填写规则**：
- **Pillar**：具体、可验证的陈述，不同于 Bull/Bear 论点的宏观叙事
- **Original Expectation**：首次覆盖时的预期值或上次重审时的基准
- **Current Status**：最新可观测数据，必须带 `as_of` + 来源
- **Trend**：改善 / 稳定 / 恶化 / 新（新出现的支柱）

≥2 个 pillar 时推荐使用此格式；单 pillar 或确实无法拆分的 thesis 仍可用纯文本一句话。
```

**向后兼容**：纯文本一句话 thesis 仍然有效，scorecard 是推荐而非强制。

## 5. 优先级与目标版本

**本提案优先级**：P1

理由：非硬缺陷，但显著提升 thesis 可追踪性和报告复用价值（下次更新时可直接对比）。与其他 §7 增强一并合入 v0.3。

### 目标版本

v0.3

## 6. 兼容性评估

| 维度 | 影响 | 说明 |
|------|------|------|
| 已发布报告 | 否 | 不要求回填 |
| 主 spec 骨架 | 否 | §7.2 编号不变，只增加推荐格式说明 |
| 其他 references 文件 | 否 | 不涉及 |
| Quality checklist | 是 | 建议加一条 `requires_explanation`：如使用纯文本 thesis，在 Meta 中简短说明为何未使用 scorecard（单 pillar 等情况） |
| 各 agent 薄壳 | 否 | 薄壳只引用主 spec |

## 7. 风险与权衡

- 可能增加报告撰写负担——单 pillar thesis 强行拆成多行会显得空洞。用"推荐而非强制"解决。
- scorecard 需要 ongoing 追踪才能体现价值——一次性的 initiation 报告价值有限。这正是 §7.6（重审日期）的配套价值：下次更新时 scorecard 提供直接的 diff 基础。

## 8. 替代方案

A. 强制使用 scorecard——过于僵化。
B. 只在 references 中放格式说明，不写进主 spec——可发现性差。
C. 保持现状，让 agent 自行发挥——失去规范化优势。

选择当前方案：主 spec 推荐 + 向下兼容纯文本。

## 9. 备注

参考来源：https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/equity-research/skills/thesis-tracker/SKILL.md
