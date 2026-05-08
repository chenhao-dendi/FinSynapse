# 模板改进建议：§7 thesis 增加可证伪性要求

> 提出日期：2026-05-08
> 提出人 / agent：opencode-DeepSeek（参考 anthropics/financial-services thesis-tracker）
> 状态：merged 2026-05-08 → v0.3
> 优先级：P1
> 目标版本：v0.3

## 1. 出现在哪份报告

无关联报告——属于模板设计层面改进。灵感来自 anthropics/financial-services 仓库 `equity-research/skills/thesis-tracker/SKILL.md` 第 1 节：

> "A thesis should be falsifiable — if nothing could disprove it, it's not a thesis"

## 2. 建议改哪个文件 / 哪一节

- 文件：`research/templates/company-analysis.md`
- 章节：新增 §5.4.1（在 §5.4 维度评级矩阵 与 §5.5 管理层激励 之间）
- 改动类型：新增

## 3. 问题描述

当前 §7 要求写 thesis（一句话）+ 强化/削弱/证伪事件，但没有明确要求 thesis 本身**必须可证伪**。实际跑报告时可能出现"万能 thesis"——比如"AI 长期趋势利好公司"这种无法被任何具体事件推翻的表述。

参考 thesis-tracker：可证伪性是 thesis 的底层要求——如果 nothing could disprove it，则不是 thesis，而是信仰陈述。这个原则一句话就能讲清楚，不需要改结构。

## 4. 建议改法

在 `company-analysis.md` §5.4（维度评级矩阵示例）之后，新增一个小节：

```markdown
### 5.4.1 Thesis 可证伪性（v0.3）

§7.2 的 thesis 必须**可证伪**：如果没有任何可观察事件能让你改变观点，这个 thesis 就不成立。

**Bad**（不可证伪）：
> 中国半导体长期前景看好。

**Good**（可证伪）：
> SMIC 的 28nm 产能定价权在未来 12 个月将持续增强（证伪事件：行业 28nm 报价连续 2 个季度环比下跌 ≥5%）。

原则：每个 thesis 必须有至少 1 个具体的、可观察的证伪事件（见 §7.5）。证伪事件不是"黑天鹅"，而是**合理可能出现且可以观测**的具体条件。
```

同时在 §7.2 的骨架说明中加一行提示：

```markdown
7.2 **当前 Thesis（一句话）**：研究上看好/谨慎的最核心理由。**必须可证伪**（见 §5.4.1）
```

## 5. 优先级与目标版本

**本提案优先级**：P1

理由：不是硬缺陷（现有 B5 已覆盖"Bull/Bear 不是同一句话的正反面"），但提升 thesis 质量有直接帮助。可与其他 §7 相关 proposals 一并合入 v0.3。

### 目标版本

v0.3 —— 与 thesis-scorecard、catalyst-classification 等 §7 增强 proposals 一并合入。

## 6. 兼容性评估

| 维度 | 影响 | 说明 |
|------|------|------|
| 已发布报告 | 否 | 不要求旧报告回填 |
| 主 spec 骨架 | 否 | 不改变 §1-§7 章节编号，只新增说明小节 |
| 其他 references 文件 | 否 | 不涉及 |
| Quality checklist | 否 | 可后续（P2）加一条 `requires_explanation` 检查项，当前不强求 |
| 各 agent 薄壳（Claude SKILL / AGENTS.md） | 否 | AGENTS.md 的"撰写要点"无需改动，薄壳只引用主 spec |

## 7. 风险与权衡

- 对 soft thesis（如 ESG 趋势、品牌力等难以量化的论点）可能略严苛——但这类也可以找到可观测代理变量（如品牌排名、ESG 评级变动），不算真正的阻挡。
- 增加 writing 思考负担，但方向正确不增加长度。

## 8. 替代方案

A. 不单独加小节，直接在 §7.2 旁注"必须可证伪"——更轻量，但可发现性差。
B. 不加任何文本约束，仅依赖 checklist——容易遗漏。

选择方案 A+（新增小节的清晰度 + §7.2 骨架行内提示的双重覆盖）。

## 9. 备注

参考来源：https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/equity-research/skills/thesis-tracker/SKILL.md
