# 调研索引

## 撰写规范

- **个股报告**：统一使用 [`templates/company-analysis.md`](templates/company-analysis.md)（v0.3）
  - frontmatter：[`templates/report-frontmatter.md`](templates/report-frontmatter.md)
  - 数据规范：[`templates/references/data-source-policy.md`](templates/references/data-source-policy.md)
  - 行业指标：[`templates/references/industry-metrics.md`](templates/references/industry-metrics.md)
  - 跨市场（AH/ADR）：[`templates/references/cross-market-policy.md`](templates/references/cross-market-policy.md)
  - 写完自检：[`templates/assets/report-quality-checklist.md`](templates/assets/report-quality-checklist.md)
  - 改进建议：[`templates/_proposals/`](templates/_proposals/)
- **个股文件命名**：`stocks/<market>/<ticker>-<slug>-YYYYMMDD.md`（详见主 spec 第 2 节）
  - 示例：`stocks/hk/00981-HK-smic-20260505.md`
- **行业研究** / **其他主题报告**：暂沿用 `[主题]-YYYYMMDD.md`
- **旧报告**：不强制迁移到新模板，只约束新报告

## 行业调研

### 半导体

| 文件 | 日期 | 简介 |
|------|------|------|
| [中国AI芯片自主化全景图-20260504.md](industry/semiconductor/中国AI芯片自主化全景图-20260504.md) | 2026-05-04 | 国产 AI 芯片公司总览（华为海思/寒武纪/海光等），含估值、财务、代工供应链分析 |
| [半导体行业周期性分析-20260504.md](industry/semiconductor/半导体行业周期性分析-20260504.md) | 2026-05-04 | 半导体行业周期框架、供需驱动与投资时钟分析 |
| [芯片制造核心概念解读-20260504.md](industry/semiconductor/芯片制造核心概念解读-20260504.md) | 2026-05-04 | 芯片制造入门：晶圆、光刻胶、DUV/EUV、刻蚀机等核心概念科普 |

### AI 产业链

| 文件 | 日期 | 简介 |
|------|------|------|
| [DeepSeek-V4-产业链分析-20260503.md](industry/ai/DeepSeek-V4-产业链分析-20260503.md) | 2026-05-03 | DeepSeek V4 芯片供应链、云部署、关联上市公司估值分析 |

---

## 个股调研

### A 股

| 文件 | 日期 | 标的 | 模板版本 |
|------|------|------|:-------:|
| [688981-smic-20260505.md](stocks/cn/688981-smic-20260505.md) | 2026-05-05 | 688981（中芯国际） | v0.1 |
| [中芯国际SMIC深度分析-20260504.md](stocks/cn/中芯国际SMIC深度分析-20260504.md) | 2026-05-04 | 688981 | legacy |

### 港股

| 文件 | 日期 | 标的 | 模板版本 |
|------|------|------|:-------:|
| [9992-HK-popmart-20260505.md](stocks/hk/9992-HK-popmart-20260505.md) | 2026-05-05 | 9992.HK（泡泡玛特） | v0.2 |
| [00981-HK-smic-20260505.md](stocks/hk/00981-HK-smic-20260505.md) | 2026-05-05 | 00981.HK（中芯国际） | v0.1 |
| [中芯国际港股优劣势综合分析-20260504.md](stocks/hk/中芯国际港股优劣势综合分析-20260504.md) | 2026-05-04 | 00981.HK | legacy |

### 美股

待添加。

### 韩国

| 文件 | 日期 | 标的 | 模板版本 |
|------|------|------|:-------:|
| [000660-sk-hynix-20260509.md](stocks/kr/000660-sk-hynix-20260509.md) | 2026-05-09 | 000660.KS（SK 海力士） | v0.3 |
| [005930-samsung-electronics-20260509.md](stocks/kr/005930-samsung-electronics-20260509.md) | 2026-05-09 | 005930.KS（三星电子） | v0.3 |
