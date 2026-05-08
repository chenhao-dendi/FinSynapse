# 模板改进建议：report-quality-checklist 补充跨章节一致性 + hyperlink 检查

> 提出日期：2026-05-08
> 提出人 / agent：opencode-DeepSeek（参考 anthropics/financial-services initiating-coverage Task 5 Final Verification + earnings-analysis §Critical Requirements）
> 状态：merged 2026-05-08 → v0.3
> 优先级：P1
> 目标版本：v0.3

## 1. 出现在哪份报告

无关联报告——checklist 设计层面改进。灵感来自两个来源：

1. `initiating-coverage/SKILL.md` Task 5 Final Verification：`Numbers match financial model exactly`
2. `earnings-analysis/SKILL.md` §Critical Requirements：完整的 citation hyperlinks 要求

## 2. 建议改哪个文件 / 哪一节

- 文件：`research/templates/assets/report-quality-checklist.md`
- 章节：B 部分（Sanity Checks），新增 B8-B9
- 改动类型：新增

## 3. 问题描述

当前 checklist 的 Sanity Checks（B1-B7）缺少两项检查：

**缺失 1：跨章节数字一致性**

报告可能在 §2（财务体检）写了一个营收数字，在 §5（增长驱动）又引用了一个不一致的数字（来源不同、口径不同、年份不同）。当前没有显式检查要求"同一指标在不同章节引用时必须一致"。

参考 initiating-coverage Final Verification：
> Numbers match financial model exactly

FinSynapse 不做 Excel 模型，但跨章节数字一致是同样的原则。

**缺失 2：引用可点击**

Markdown 报告中引用来源时，有时只是文字提及"据 XX 公告"，没有提供超链接。这降低了可审计性。

参考 earnings-analysis：
> ALL URLs are CLICKABLE HYPERLINKS (not plain text)

## 4. 建议改法

在 B 部分末尾新增 B8、B9：

```markdown
| B8 | **跨章节数字一致**：同一指标（如营收、毛利率、市值）在 §2/§5/§6/§7 等不同章节出现时，数值必须一致。如为不同口径（如 LTM vs FY、含/不含一次性项），必须显式标注口径差异 | `hard_fail` | standard |
```

或改为 `requires_explanation` 更宽松：

```markdown
| B8 | **跨章节数字一致**：同一指标（如营收、毛利率、市值）在多处引用时数值一致。如因口径差异（LTM vs FY、含/不含一次性项目）导致数值不同，必须在每处显式标注口径 | `requires_explanation` | standard |
| B9 | **引用可点击**：数据来源（财报/公告/公告链接）在 Markdown 正文中应提供可点击的链接（`[text](url)` 格式）。无法提供链接的来源（如付费终端数据）应注明平台名称和访问日期 | `requires_explanation` | standard |
```

同时在 D 部分（Future Deep Checks）加一条面向 v0.3 的建模一致性检查：

```markdown
- [ ] 跨章节关键数字一致（brief/standard/deep 同一标的的一致）
```

## 5. 优先级与目标版本

**本提案优先级**：P1

理由：B8 属于基本质量要求（硬 fail 可能过于严格，`requires_explanation` 更合理）；B9 提升审计能力。不阻塞现有报告产出。

### 目标版本

v0.3

## 6. 兼容性评估

| 维度 | 影响 | 说明 |
|------|------|------|
| 已发布报告 | 否 | 不要求回填 |
| 主 spec 骨架 | 否 | checklist 改动不影响主 spec 正文 |
| 其他 references 文件 | 否 | 不涉及 |
| Quality checklist | 是 | 新增 B8、B9 |
| 各 agent 薄壳 | 否 | 薄壳只引用 checklist 路径 |

## 7. 风险与权衡

- B8 设为 `hard_fail` 可能对跨章节频繁引用同一指标的复杂报告过于严苛——建议 `requires_explanation`（不给过但要求解释）。
- B9（引用可点击）对 Markdown 报告天然友好（`[text](url)` 是基本语法），对小部分没有公开 URL 的数据源（如 Wind 终端、Bloomberg 终端）只需标注平台名 + 日期即可通过。

## 8. 替代方案

A. 不新增检查项，只依赖现有 A3（关键数字有审计线索）——A3 侧重单点来源，不覆盖跨章节一致性。
B. 只加 B8，不加 B9——B8 是核心，B9 是体验优化。

选择当前方案：两项目标小、改动小、利大于弊。

## 9. 备注

参考来源：
- https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/equity-research/skills/initiating-coverage/SKILL.md (Final Verification: "Numbers match financial model exactly")
- https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/equity-research/skills/earnings-analysis/SKILL.md (Citation hyperlinks requirement)
