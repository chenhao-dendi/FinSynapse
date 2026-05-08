# CLAUDE.md

> 本文件被 Claude Code 读取。
> Codex / opencode / Cursor 请读 [AGENTS.md](AGENTS.md)。

## 项目简介

**FinSynapse** 是一个金融研究与日报项目，详见 [AGENTS.md](AGENTS.md)。

## Claude Code 专属说明

### Skills

本仓库的 Claude Code skills 位于 `.claude/skills/`，目前包含：

| Skill | 触发 | 说明 |
|-------|------|------|
| `company-analysis` | 写个股分析报告时自动触发 | 遵循 `research/templates/company-analysis.md`（当前 v0.3）撰写报告 |

> opencode 用户也可以通过 `skill` 工具加载 `.claude/skills/company-analysis/SKILL.md`（已在该 agent 的 available skills 中注册）。

### 核心工作流

Claude Code 执行公司分析任务时，按 `.claude/skills/company-analysis/SKILL.md` 走 8 步流程（强制读取 → 前置验证 → 检查已有报告 → 命名 → 撰写 → 自检 → 更新索引 → 模板改进建议）。所有步骤在 AGENTS.md 中有高层概述，在 SKILL.md 中有详细操作说明。

### 强制约束（薄壳原则）

- ❌ 不要凭记忆撰写——每次都要重读 `research/templates/` 下的 spec
- ❌ 不要复制模板章节进本文件或 SKILL.md
- ❌ 不要直接改 `research/templates/`——走 `_proposals/` 流程
- ❌ 不要给"买入/卖出/目标价"

## 通用信息

所有 agent 通用的项目约定、代码规范、提交风格等，见 [AGENTS.md](AGENTS.md)。本文件只维护 Claude Code 专属内容。
