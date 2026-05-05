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
- review 通过 → 改主文件 → bump `template_version` → 在主 spec changelog 记录 → 删除已合并的 proposal（或归档到 `_archive/`）
- review 拒绝 → 在 proposal 末尾写"Rejected YYYY-MM-DD: 原因" → 留档不删，便于将来重新评估

## 优先级（自评）

- **高**：影响数据可信度、影响结论结构、修复明显错误
- **中**：补充缺失维度、改进体验
- **低**：行文优化、举例补充

## 当前未合并的 proposals

（目录刚建立，尚无 proposals）
