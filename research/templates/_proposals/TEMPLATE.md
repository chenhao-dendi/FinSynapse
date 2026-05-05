# 模板改进建议：<一句话主题>

> 提出日期：YYYY-MM-DD
> 提出人 / agent：<who>
> 状态：pending（pending / accepted / rejected / merged）
> 优先级：P0 / P1 / P2
> 目标版本：v0.X（建议合并到哪个版本）

## 1. 出现在哪份报告

- 路径：`research/stocks/<market>/<file>.md` 或 `research/industry/<topic>/<file>.md`
- 章节：第 X.Y 节

（试跑或日常使用中第一次发现问题的报告。如果是模板设计阶段就提的建议，写"无关联报告"。）

## 2. 建议改哪个文件 / 哪一节

- 文件：`research/templates/company-analysis.md` / `references/data-source-policy.md` / `references/industry-metrics.md` / `references/cross-market-policy.md` / `references/valuation-methods.md` / `assets/report-quality-checklist.md` / 其他
- 章节：第 X.Y 节
- 改动类型：新增 / 修改 / 删除 / 重构

## 3. 问题描述

<具体描述当前模板/规范的不足。最好引用具体写报告时遇到的卡点，而不是抽象建议。>

## 4. 建议改法

<具体怎么改：加哪段、改哪句、删哪节、调整顺序。如果改动较大，给出 markdown 草稿。>

## 5. 优先级与目标版本

### 优先级（P0 / P1 / P2）

| 等级 | 含义 | 典型场景 |
|------|------|---------|
| **P0** | 必须立即合并 | 影响数据可信度 / 影响结论结构 / 修复明显错误 / 多份报告被堵 |
| **P1** | 下一次 review 周期合并 | 补充缺失维度 / 改进体验 / 跨市场或行业适配 |
| **P2** | 攒批合并 | 行文优化 / 举例补充 / 边缘场景适配 |

**本提案优先级**：P0 / P1 / P2 + 理由

### 目标版本

- v0.X（建议合并到哪个 template_version）+ 理由

## 6. 兼容性评估

| 维度 | 影响 | 说明 |
|------|------|------|
| 已发布报告 | 是 / 否 | 如有：需要回填？标 legacy？还是不动？ |
| 主 spec 骨架 | 是 / 否 | 是否动 §1-§7 章节顺序或编号 |
| 其他 references 文件 | 是 / 否 | 列出受影响文件 |
| Quality checklist | 是 / 否 | 是否需要补 / 改 / 删 checklist 项 |
| 各 agent 薄壳（Claude SKILL / AGENTS.md） | 是 / 否 | 是否需要同步薄壳约束 |

## 7. 风险与权衡

<这次改动可能引入的副作用、未解决的问题、需要后续观察的点。>

## 8. 替代方案（可选）

<如果有 ≥2 种实现路径，简述其他方案与 tradeoff。否则可省略。>

## 9. 备注（可选）

<其他需要 reviewer 知道的信息：参考资料、关联 proposals、外部依赖等。>

---

## Review 区（reviewer 填写，提案者不动）

- review 日期：YYYY-MM-DD
- review 人：
- 决议：accepted / rejected / modified-then-accepted / deferred
- 决议理由：
- 实际落地位置：<列出最终改动的文件与章节>
- 状态变更：移到 `_archive/` 并在文件顶部状态行更新为 `merged YYYY-MM-DD → template_version X.Y` 或 `rejected YYYY-MM-DD: 原因`
