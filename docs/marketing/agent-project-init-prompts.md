# AI Agent 项目初始化与技能自动检测补全提示词库 (Agent Skill Init Prompts)

本文件包含供新旧用户在启动任何项目时，直接发送给 AI Agent（Antigravity / OpenAI Codex / Claude Code）的标准化提示词，确保 Agent 具备自动感知环境、诊断缺失技能、一键补全与健康检查的能力。

---

## 提示词 1：【全能启动版】项目立项与技能装配全流程提示词（推荐）

> **使用场景**：在 Antigravity / Codex / Claude 中新建或打开一个项目目录时，将以下提示词完整复制发送给 Agent。

```markdown
你现在作为「AI 技能架构师与项目初始化专家 (Agent Skills Specialist)」。
我正在当前工作区启动一个新项目/新阶段任务。在正式编写项目业务代码或方案之前，请先对当前环境的 Agent 技能（Skills）进行全面的「环境审计、需求对齐、缺失补齐与健康校验」。

【当前项目目标】:
（请在此简要说明，例如：制定 2027 客户营销方案 / 社媒数据自动化分析 / 新产品 GTM 发布 / SEO 独立站增长 等）

【你的执行步骤】:
1. 环境与技能探测 (Environment Scan):
   - 检测当前运行环境 (Antigravity / Codex / Claude Code)。
   - 扫描全局技能目录 (~/.gemini/config/skills, ~/.codex/skills, ~/.claude/skills, ~/.agents/skills, ~/.cc-switch/skills) 及当前项目本地目录 (.agents/skills/)。
   - 列出当前已就绪的技能数量及名称。

2. 需求分析与缺失诊断 (Skill Gap Analysis):
   - 根据我上述的项目目标，评估完成该项目所需的专业技能套件 (涵盖市场分析、定位、文案、SEO、广告、流程设计等)。
   - 对比本地上游技能库 (~/.gemini/marketing-skills-upstream/ 中 128 个营销技能，含 Corey Haines 50 项 + OpenClaudia 78 项)。
   - 输出清晰的技能对比表格：
     * [已就绪技能] (Ready)
     * [本项目核心急需但缺失/未链接技能] (Missing - Critical)
     * [推荐可选增强技能] (Recommended - Optional)

3. 自动安装与软链接挂载 (Auto-Install & Link):
   - 如缺失全局技能，请运行管理脚本同步：
     bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh sync-global
   - 如本项目需要专属隔离技能，请在当前项目 .agents/skills/ 目录下创建指向 ~/.gemini/marketing-skills-upstream/ 对应技能的软链接。
   - 遵守命名冲突规范：Corey Haines 保留标准名，OpenClaudia 重名技能使用 `oc-` 前缀。

4. 完整性健康检查 (Health Validation):
   - 运行校验命令，确保所有技能目录及其 SKILL.md 均有效可读：
     bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh validate
   - 确认无断链 (Broken Symlink) 和无元数据缺失。

5. 交付物与启动建议 (Kickoff Handover):
   - 输出一份简明的「项目技能就绪矩阵报告」。
   - 明确告知我已经全部就绪，并直接推荐本项目的第一步具体行动指令。
```

---

## 提示词 2：【轻量即查即补版】单项功能/缺失技能诊断与快速挂载

> **使用场景**：项目进行中，发现缺少某项能力（例如“做竞品分析缺技能”、“写落地页文案缺参考规范”）时使用。

```markdown
请帮我检查并补全当前项目所需的专项技能。

【我需要的技能领域/功能】:
（例如：客户画像构建 icp-builder / 竞品调研 competitor-analysis / 落地页优化 cro 等）

【执行指令】:
1. 检查全局环境 (~/.gemini/config/skills, ~/.codex/skills) 及项目工作区 (.agents/skills) 是否已存在对应技能。
2. 若未挂载，请在上游技能库 ~/.gemini/marketing-skills-upstream/ (Corey Haines 与 OpenClaudia) 中检索匹配的技能目录。
3. 自动执行软链接挂载并校验 SKILL.md 存在且格式正确。
4. 确认挂载成功后，简要总结该技能的核心功能与触发指令，并立即按照该技能的最佳实践继续处理我的业务需求。
```

---

## 提示词 3：【永久常驻规则】项目级自动感知协议 (写入 AGENTS.md / GEMINI.md)

> **使用场景**：直接放入任何项目的根目录 `AGENTS.md` 或 `GEMINI.md`，使进入该项目的所有 Agent 永久具备自动补全意识，无需每次反复提示。

```markdown
<!-- marketing-skills-auto-discovery:start -->
# Agent Skills Auto-Discovery & Integration Protocol

When working in this repository:
1. **Skill Discovery Hierarchy**:
   - Workspace Local: `./.agents/skills/<skill-name>/`
   - Global Environments: `~/.gemini/config/skills/`, `~/.codex/skills/`, `~/.agents/skills/`
   - Local Upstream SSOT: `~/.gemini/marketing-skills-upstream/`

2. **Missing Skill Resolution**:
   - If a requested task requires specialized marketing, SEO, copy, or launch skills that are not active in your current context:
   - Check `~/.gemini/marketing-skills-upstream/marketingskills/skills/` (Corey Haines) and `~/.gemini/marketing-skills-upstream/openclaudia-skills/skills/` (OpenClaudia).
   - If found, automatically link it to the project `.agents/skills/<name>` or execute:
     `bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh sync-global`
   - If there is a naming collision, use canonical name for Corey Haines and `oc-` prefix for OpenClaudia.
   - Read the newly linked `SKILL.md` before executing the user's task.
<!-- marketing-skills-auto-discovery:end -->
```
