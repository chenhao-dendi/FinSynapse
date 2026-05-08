# 模板改进建议：§7 催化剂事件增加分类体系

> 提出日期：2026-05-08
> 提出人 / agent：opencode-DeepSeek（参考 anthropics/financial-services catalyst-calendar）
> 状态：merged 2026-05-08 → v0.3
> 优先级：P1
> 目标版本：v0.3

## 1. 出现在哪份报告

无关联报告——模板设计层面改进。灵感来自 anthropics/financial-services 仓库 `equity-research/skills/catalyst-calendar/SKILL.md` 第 2-3 节。

## 2. 建议改哪个文件 / 哪一节

- 文件：`research/templates/company-analysis.md`
- 章节：§7.3-7.5（强化/削弱/证伪事件）的格式说明
- 改动类型：新增（增加推荐列，不替换现有格式）

## 3. 问题描述

当前 §7.3-7.5 的强化/削弱/证伪事件是纯列表，没有分类。实践中不同类别的事件（财报 vs 产品发布 vs 监管决定）有不同的时间节奏和可观测性。

参考 catalyst-calendar 的四分类体系：

| 分类 | 说明 |
|------|------|
| **Earnings & Financial** | 财报、股东会、投资者日、指引变更 |
| **Corporate Events** | 产品发布、审批、M&A、管理层变动 |
| **Industry Events** | 行业会议、监管决定、竞品动态 |
| **Macro Events** | FOMC、CPI、地缘政治（跨市场报告适用） |

在事件列表中增加 `Type` 列有助读者快速识别事件性质和时间节点。

## 4. 建议改法

在 §5.3（第 7 章结论事件 bad/good 示例）中，将 Good 示例从纯列表升级为带 Type 列的表格：

```markdown
**Good**（具体、可观察、有触发条件，推荐加 Type 分类）：

| # | 事件 | Type | 触发条件 |
|---|------|------|---------|
| H1 | Q3 毛利率 ≥25% | Earnings | 连续 3 个季度向上 |
| H2 | N+1（5nm 等效）流片公开 | Corporate | 公司或客户公开披露 |
| H3 | 大基金 III 期对 SMIC 出资额公布 | Industry | 基金公告 |
| W1 | 美国新制裁覆盖 28nm 设备 | Industry | BIS 公告或法案 |
| W2 | 华为/寒武纪订单大幅下修 | Earnings | 客户财报/供应链数据 |
| W3 | Capex 维持 $70 亿+ 但毛利率不再向上 | Corporate | 公司季报 |
| F1 | 因合规被撤销前道设备进口许可 | Industry | 政府公告 |

Type 可选值：`Earnings` / `Corporate` / `Industry` / `Macro`（跨市场可加 `Macro`）
H = 强化 (Heightening)，W = 削弱 (Weakening)，F = 证伪 (Falsifying)
```

同时在 §7.3-7.5 的骨架中增加可选 `Type` 列指示：

```markdown
7.3 **强化事件**（什么发生会让 thesis 更成立）：≥3 条；推荐含 Type（Earnings/Corporate/Industry/Macro）
7.4 **削弱事件**（什么发生会让 thesis 受损）：≥3 条；推荐含 Type
7.5 **证伪事件**（什么发生会推翻 thesis）：≥1 条；推荐含 Type
```

**向后兼容**：Type 列为推荐而非强制。不带 Type 的纯列表仍然有效。

## 5. 优先级与目标版本

**本提案优先级**：P1

理由：增加可追踪性和事件节奏感知，但非硬缺陷。现存 §5.3 已对"具体可观察"有要求，Type 是锦上添花。与其他 §7 增强一并合入 v0.3。

### 目标版本

v0.3

## 6. 兼容性评估

| 维度 | 影响 | 说明 |
|------|------|------|
| 已发布报告 | 否 | 不要求回填 |
| 主 spec 骨架 | 否 | §7.3-7.5 编号不变，只增加推荐格式 |
| 其他 references 文件 | 否 | 不涉及 |
| Quality checklist | 否 | 暂不增加 Type 列检查项（P2 可补一条 `requires_explanation`："若事件 ≥5 条未分 Type，建议补充分类"） |
| 各 agent 薄壳 | 否 | 薄壳只引用主 spec |

## 7. 风险与权衡

- 四分类是否穷举——对小众事件类别（如法律诉讼）可能需要 fallback（归入 Corporate 或 Industry）。如有明显遗漏可在 v0.4 补 Other 类。
- Type 列可能过度 engineering——对只有 3-5 个事件的 report 可能显得冗余。用"推荐"而非"强制"解决。

## 8. 替代方案

A. 只用编号前缀 H/W/F，不加 Type——更简洁但失去分类信息。
B. 强制要求 Type——对简单 case 过于繁琐。
C. 不写进主 spec，只在 references 下加一个 catalyst-format.md——可发现性差。

选择当前方案：主 spec 推荐 + 向下兼容纯列表。

## 9. 备注

参考来源：https://github.com/anthropics/financial-services/blob/main/plugins/vertical-plugins/equity-research/skills/catalyst-calendar/SKILL.md
