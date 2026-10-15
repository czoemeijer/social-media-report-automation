# Project Agent Guidelines & Skills Protocol

<!-- codebase-memory-mcp:start -->
# Codebase Knowledge Graph (codebase-memory-mcp)

This project uses codebase-memory-mcp to maintain a knowledge graph of the codebase.
ALWAYS prefer MCP graph tools over grep/glob/file-search for code discovery.

## Priority Order
1. `search_graph` — find functions, classes, routes, variables by pattern
2. `trace_path` — trace who calls a function or what it calls
3. `get_code_snippet` — read specific function/class source code
4. `query_graph` — run Cypher queries for complex patterns
5. `get_architecture` — high-level project summary

## When to fall back to grep/glob
- Searching for string literals, error messages, config values
- Searching non-code files (Dockerfiles, shell scripts, configs)
- When MCP tools return insufficient results
<!-- codebase-memory-mcp:end -->

---

<!-- agent-skills-auto-discovery:start -->
# Agent Skills Auto-Discovery & Execution Protocol

When operating within this repository:

## 1. Skill Discovery Hierarchy
- **Workspace Local**: `./.agents/skills/<skill-name>/`
- **Global AI Environments**: `~/.gemini/config/skills/`, `~/.codex/skills/`, `~/.claude/skills/`, `~/.agents/skills/`
- **Local Upstream SSOT**: `~/.gemini/marketing-skills-upstream/` (128 marketing skills)
- **Local Documentation**: `./docs/marketing/`

## 2. Autonomous Skill Detection & Resolution
Before tackling any domain task (marketing strategy, copywriting, landing page CRO, SEO audits, paid ads, campaign automation):
1. **Verify Active Skills**: Check if the required specialized skill is available in your active context.
2. **Missing Skill Resolution**:
   - Search `~/.gemini/marketing-skills-upstream/marketingskills/skills/` (Corey Haines, 50 skills) and `~/.gemini/marketing-skills-upstream/openclaudia-skills/skills/` (OpenClaudia, 78 skills).
   - Link it into `./.agents/skills/<skill-name>` or run `bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh sync-global`.
   - In case of naming collisions, Corey Haines holds canonical names and OpenClaudia uses the `oc-` prefix.
   - Always read the mounted skill's `SKILL.md` reference material before producing deliverables.

## 3. Marketing Skills Documentation Index
Detailed technical guides and prompt libraries are stored in [`docs/marketing/`](./docs/marketing/):
- [`docs/marketing/agent-project-init-prompts-en.md`](./docs/marketing/agent-project-init-prompts-en.md): English project kickoff & skill mounting prompt library.
- [`docs/marketing/agent-project-init-prompts.md`](./docs/marketing/agent-project-init-prompts.md): Bilingual project initialization prompts.
- [`docs/marketing/project-skill-init-guide.md`](./docs/marketing/project-skill-init-guide.md): Step-by-step project onboarding and skill gap analysis guide.
- [`docs/marketing/marketing-skills-installation.md`](./docs/marketing/marketing-skills-installation.md): Global multi-environment architecture & installation record.
- [`docs/marketing/marketing-skills-inventory.md`](./docs/marketing/marketing-skills-inventory.md): Full inventory of all 128 curated skills.
- [`docs/marketing/marketing-skills-comparison.md`](./docs/marketing/marketing-skills-comparison.md): Overlapping skill trade-offs & namespace rules.
- [`docs/marketing/marketing-skills-maintenance.md`](./docs/marketing/marketing-skills-maintenance.md): Multi-environment maintenance & upstream sync guide.
- [`docs/marketing/marketing-skills-validation.md`](./docs/marketing/marketing-skills-validation.md): Health check & validation reports.
<!-- agent-skills-auto-discovery:end -->
