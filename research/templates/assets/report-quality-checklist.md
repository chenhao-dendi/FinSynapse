# 报告质量自检 Checklist (v0.2)

> 适用：所有遵循 `templates/company-analysis.md` 的研究报告。
> 用法：报告写完后，agent 必须逐项检查；未通过项按 Gate 类型处理，并在报告 `## Meta` 段中说明。
> 版本：0.2（补充 Gate 类型、语言约束、免责声明检查）

---

## Gate 类型

| Gate | 含义 | 处理方式 |
|------|------|----------|
| `hard_fail` | 无合理解释时禁止落盘 | 补数据、改结论或改写文本后再产出 |
| `requires_explanation` | 可落盘，但必须解释 | 在正文或 `## Meta` 写明原因、口径或数据缺口 |
| `not_applicable` | 确实不适用 | 标注 N/A，并在 `## Meta → 不适用章节` 说明 |

---

## A. 完成度

| 编号 | 检查项 | Gate | 适用 |
|------|--------|------|------|
| A1 | **frontmatter 完整**：`title / as_of / tickers / markets / industry / template_version / depth / source_level / confidence / not_investment_advice / sources` 全部填写，未填字段不能省略，应标注 `N/A` 并解释 | `hard_fail` | brief / standard |
| A2 | **TL;DR 独立可读**：≤200 字；只读 TL;DR 也能知道公司业务、当下叙事、多空核心、研究结论 | `hard_fail` | brief / standard |
| A3 | **关键数字有审计线索**：财务、估值、市场份额数字均带 `as_of` 与来源（规则见 `references/data-source-policy.md`） | `hard_fail` | brief / standard |
| A4 | **N/A 有解释**：所有标注 N/A 的章节，在 `## Meta → 不适用章节` 中说明原因 | `requires_explanation` | standard |
| A5 | **结论结构完整**：第 7 章包含 thesis（一句话）+ 强化事件（≥3 条）+ 削弱事件（≥3 条）+ 证伪事件（≥1 条）+ 重审日期 | `hard_fail` | standard |
| A6 | **§7.0 维度评级矩阵已填**：6 维（业务地位 / 财务健康 / 护城河 / 治理与资本配置 / 成长驱动 / 风险抵御）每行 ★1-★5 + 一句话理由（≤30 字）；矩阵综合判断应与 7.1 单一标签一致 | `hard_fail` | standard |

**A4 例外**：§4.2 管理层激励数据公开披露不充分时，标"未公开披露"即可，无需在 Meta 列为 N/A 章节（详见主 spec §5.5）。

---

## B. Sanity Checks

| 编号 | 检查项 | Gate | 适用 |
|------|--------|------|------|
| B1 | **财务关系合理**：通常应满足 **毛利率 ≥ 经营利润率 ≥ 净利率**。如不成立（一次性损益、特殊会计处理、负利润、金融行业等），必须在正文中解释 | `requires_explanation` | standard |
| B2 | **估值倍数异常有解释**：PE/PS/EV-EBITDA 与同业差异 >50% 时，必须在 6.1 解释（叙事溢价、盈利质量差异、周期错位或口径差异） | `requires_explanation` | standard |
| B3 | **多情景假设确实不同**：Bull / Base / Bear 不能只是数字微调，至少有增长率、毛利率、市占率、监管环境、客户结构等实质假设差异 | `requires_explanation` | standard |
| B4 | **估值不被单一假设支配**：若某一输入（如 WACC、终值倍数、增长率）小幅变动导致估值大幅摆动，必须在正文点出并附敏感性解释 | `requires_explanation` | standard |
| B5 | **Bull/Bear 不是同一句话的正反面**：例如不允许"Bull：AI 需求爆发 / Bear：AI 需求不爆发"。两边必须各自基于不同维度，且各 ≥3 条 | `hard_fail` | brief / standard |
| B6 | **无投资建议指令语言**：不得以建议或指令形式出现"买入 / 卖出 / 加仓 / 减仓 / 仓位 / 目标价 / 止盈 / 止损"等交易措辞；如为否定或引用，也应改写成研究语言 | `hard_fail` | brief / standard |
| B7 | **固定免责声明存在**：正文底部必须包含主 spec 规定的免责声明 footer，且 frontmatter `not_investment_advice: true` | `hard_fail` | brief / standard |

---

## C. 跨市场报告补充

仅在 `markets` 含 ≥2 市场，或报告显式分析 AH/ADR 双股时勾选。

| 编号 | 检查项 | Gate | 适用 |
|------|--------|------|------|
| C1 | **主从关系明确**：从报告 frontmatter `sources` 显式引用主报告路径 | `hard_fail` | cross-market |
| C2 | **§1-§4 引用 + 摘要表**：从报告未冗余复制主报告内容（详见 `references/cross-market-policy.md` §2） | `requires_explanation` | cross-market |
| C3 | **§5/§6/§7 真正差异化**：主报告与从报告在风险、估值、结论上有市场专属内容，不是 copy-paste | `hard_fail` | cross-market |
| C4 | **AH/ADR 折溢价数据合规**：折溢价数字带 `as_of` 与来源；若 >50% 折价已在文中解释 | `requires_explanation` | cross-market |

---

## D. Future Deep Checks（v0.3，暂不作为 v0.2 必过项）

- [ ] DCF 数学约束：终端增长率 < WACC。
- [ ] DCF 终端价值占 EV 的比例异常时有解释。
- [ ] 敏感性表中心格等于 base case。
- [ ] 同一标的 brief / standard / deep 之间关键数字一致。

---

## 用法说明

1. 报告产出后，agent 按本 checklist 逐项检查。
2. `hard_fail` 未通过时，不应落盘最终报告；应补数据、改写或调整结论。
3. `requires_explanation` 未通过时，可以落盘，但必须在正文或 `## Meta` 中写明原因。
4. `not_applicable` 项必须在 `## Meta → 不适用章节` 中说明。
5. 自检结果不需要写进报告正文，只用于 agent 自身把关。

---

## 报错示例（参考）

- ❌ A3 fail：表格里有"市场份额 6%"但没标 as_of 也没标来源 → 必须补，或挪到"定性描述"。
- ❌ B1 requires explanation：净利率 8% 但毛利率只有 6% → 检查是否口径混淆、是否有大额投资收益，正文必须解释。
- ❌ B5 hard fail：Bull "国产替代加速" / Bear "国产替代受阻" → 改成 Bull 多维度（产能/客户/技术）、Bear 多维度（地缘/价格战/财务负担）。
