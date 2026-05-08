# 模板改进建议（Proposals）

本目录用于收集对 `templates/company-analysis.md` 及其 references / assets 的改进建议。

## 提交流程

1. **谁可以提**：任何 agent（Claude / Gemini / Codex / opencode）或人工
2. **怎么提**：按 `TEMPLATE.md` 复制一份新文件，命名 `YYYYMMDD-<slug>.md`（如 `20260520-add-esg-section.md`）
3. **不能做什么**：
   - ❌ 不能直接修改主 spec / references / assets
   - ❌ 不能在已有的 proposal 文件上覆盖（同主题如已有 proposal，请在原文件下追加 "Update YYYY-MM-DD" 段，而非新建）

## 合并节奏

- **每 5 份新报告** 或 **每月** 至少一次，由人工 review proposals
- review 通过 → 改主文件 → bump `template_version` → 在主 spec changelog 记录 → **移动**到 `_archive/` 并在文件顶部状态行写 `merged YYYY-MM-DD → template_version X.Y`
- review 拒绝 → 移动到 `_archive/` 并在文件顶部写 `rejected YYYY-MM-DD: 原因` → 留档不删，便于将来重新评估
- review 推后 → 留在 `_proposals/` 根目录，状态保持 `pending`

## 优先级（自评）

- **高**：影响数据可信度、影响结论结构、修复明显错误
- **中**：补充缺失维度、改进体验
- **低**：行文优化、举例补充

## 当前未合并的 proposals

| 文件 | 优先级 | 主题 | 来源 |
|------|:------:|------|------|
| [20260505-fill-consumer-pack.md](20260505-fill-consumer-pack.md) | P1 | industry-metrics.md 消费 pack 填实内容 | Pop Mart 试跑 |
| [20260505-add-ip-subpack.md](20260505-add-ip-subpack.md) | P1 | 消费 pack 下新增 IP/版权类子包 | Pop Mart 试跑 |
| [20260505-monthly-ops-cadence.md](20260505-monthly-ops-cadence.md) | P2 | 消费/零售类的月度运营数据节奏补充 | Pop Mart 试跑 |

## 已归档（_archive/）

| 文件 | 状态 | 主题 |
|------|------|------|
| [20260505-add-rating-matrix.md](_archive/20260505-add-rating-matrix.md) | merged → v0.2 | §7.0 6 维评级矩阵 |
| [20260505-ah-shared-content-policy.md](_archive/20260505-ah-shared-content-policy.md) | merged → v0.2 | AH/ADR 主从报告共享引用模式 |
| [20260505-cross-market-metrics-pack.md](_archive/20260505-cross-market-metrics-pack.md) | merged → cross-market-policy.md | 跨市场补充指标 |
| [20260505-add-cross-market-appendix.md](_archive/20260505-add-cross-market-appendix.md) | merged → v0.2 主模板 | 可选附录 A 跨市场对照 |
| [20260508-catalyst-classification.md](_archive/20260508-catalyst-classification.md) | merged → v0.3 | §7 事件 Type 四分类（Earnings/Corporate/Industry/Macro） |
| [20260508-quality-checklist-enhance.md](_archive/20260508-quality-checklist-enhance.md) | merged → v0.3 | checklist 新增 B8/B9（跨章节一致 + 引用可点击） |
| [20260508-thesis-falsifiability.md](_archive/20260508-thesis-falsifiability.md) | merged → v0.3 | §7 thesis 可证伪性要求 |
| [20260508-thesis-scorecard.md](_archive/20260508-thesis-scorecard.md) | merged → v0.3 | §7 thesis pillar scorecard 推荐格式 |
