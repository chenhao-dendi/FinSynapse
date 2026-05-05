# 行业指标扩展包

> 适用：所有遵循 `templates/company-analysis.md` 的研究报告。报告 frontmatter 的 `industry` 字段决定引用哪个 pack。
> 版本：0.1（仅占位；半导体 pack 内容在 v0.2 填充，其余 pack 按需求出现时再补）

通用模板（`company-analysis.md`）覆盖**任何公司都适用的财务/治理/估值维度**。但银行的 NIM、SaaS 的 ARR、半导体的产能利用率，无法用通用维度替代。本文件按行业列出**额外应在 1.4 / 2.x 章节补充的指标清单**。

---

## 行业 packs 索引

| `industry` 字段值 | 状态 | 链接 |
|------------------|------|------|
| `semiconductor`  | 🚧 v0.2 填充 | [#半导体](#半导体-semiconductor) |
| `saas`           | 📝 占位      | [#saas](#saas) |
| `bank`           | 📝 占位      | [#银行](#银行-bank) |
| `consumer`       | 📝 占位      | [#消费](#消费-consumer) |
| `resource`       | 📝 占位      | [#资源](#资源-resource) |
| `other`          | —            | 不强制行业指标，agent 按公司业务自行判断需补哪些维度 |

---

## 半导体 (semiconductor)

> 状态：v0.2 待填充。下面是预留大纲。

### 业务画像补充（1.4 行业地位与市场份额 后）
- 商业模式分类：晶圆代工 (Foundry) / IDM / Fabless / 设备 / 材料 / 设计服务
- 制程节点分布与对应营收占比
- 客户集中度（Top 5 / Top 10）
- 工艺类型（逻辑/存储/模拟/功率/特殊工艺）

### 财务体检补充（2.x 之后）
- 月产能（8 寸等效，wafer/月）
- 产能利用率（%）
- 资本开支强度（Capex / 营收）
- 折旧规模与资本周期阶段
- 良率（如披露）
- ASP 趋势（如披露）

### 风险特别提示（5.3 监管/地缘/合规 补充）
- 出口管制（美国实体清单、EAR/ITAR）
- 关键设备/材料供应（EUV/DUV、光刻胶、晶圆基底）
- 客户/产品端制裁风险

### Sanity Checks 补充
- 产能利用率与营收增速方向是否一致
- Capex 强度与同业对比（>50% 的极端值需解释）

---

## SaaS

> 状态：占位。

预计补充：ARR、NRR、Gross Retention、CAC、LTV、Magic Number、Rule of 40、Payback Period、Customer Concentration。

---

## 银行 (bank)

> 状态：占位。

预计补充：NIM、生息资产规模、不良贷款率、关注类贷款率、拨备覆盖率、拨贷比、资本充足率、核心一级资本充足率、ROA、ROE、成本收入比。

---

## 消费 (consumer)

> 状态：占位。

预计补充：同店销售增长、门店数量与净开店、库存周转天数、应收账款周转、坪效/人效、渠道结构（直营/经销/线上）、品牌矩阵、复购率/NPS（如披露）。

---

## 资源 (resource)

> 状态：占位。

预计补充：储量与可采年限、品位、单位生产成本、商品价格敏感度、Capex/产能、矿权/勘探权、套保策略、运输与物流瓶颈。

---

## 怎么用

1. 报告 frontmatter 填 `industry: semiconductor`
2. 在主模板 1.4 / 2.5 末尾的"行业指标补充"位置，照搬本 pack 的指标清单
3. 标注 N/A 仍走 Meta 解释规则
4. 发现本 pack 缺指标 → 提交 proposal 到 `_proposals/`，不要直接改本文件
