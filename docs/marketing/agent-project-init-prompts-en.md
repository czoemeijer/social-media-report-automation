# AI Agent Project Initialization & Skill Auto-Detection Prompts (English Edition)

Standardized, machine-readable English prompt library designed for AI Agents across Google Antigravity, OpenAI Codex, and Claude Code. Enables autonomous environment scanning, requirement alignment, skill gap diagnosis, one-click symlink mounting, and health validation.

---

## Prompt 1: Comprehensive Project Kickoff & Skill Suite Assembly (Recommended)

> **When to use**: Copy and paste this prompt when initiating a new project folder or launching a major project phase in Antigravity, Codex, or Claude Code.

```markdown
You are acting as an elite **AI Agent Systems Architect & Skills Integration Specialist**.
I am kicking off a new project / major milestone in this workspace. Before authoring any production code, strategy documents, or workflows, perform a comprehensive **Environment Audit, Requirement Alignment, Skill Gap Detection, Auto-Mounting, and Health Validation**.

### Project Objective & Scope:
[Insert your project goals here, e.g.:
- Develop an end-to-end 2027 Multi-Channel Marketing Strategy for a B2B SaaS client
- Build an automated Dify workflow integrating Meta/YouTube/LinkedIn analytics reporting
- Execute a high-converting Product Hunt launch campaign with landing page optimization and drip email sequences
- Scale programmatic SEO and content repurposing pipeline]

### Required Operational Protocol:

#### Phase 1: Environment & Active Skill Discovery
1. Identify the active runtime environment (Google Antigravity, OpenAI Codex, or Claude Code).
2. Inspect all global and local skill discovery roots:
   - Global Antigravity / Gemini: `~/.gemini/config/skills/`
   - Global OpenAI Codex: `~/.codex/skills/`
   - Global Claude Code: `~/.claude/skills/`
   - Global Universal Agents: `~/.agents/skills/`
   - CC-Switch Central Registry: `~/.cc-switch/skills/`
   - Workspace Local Directory: `./.agents/skills/`
3. Inventory and report the total count and list of active skills currently accessible to you.

#### Phase 2: Requirement Alignment & Skill Gap Diagnosis
1. Analyze the project objectives specified above and derive the required domain skill stack (e.g., positioning, copywriting, CRO, SEO audit, paid ads, analytics, launch strategy).
2. Benchmark against the local upstream SSOT (`~/.gemini/marketing-skills-upstream/` containing 128 curated marketing skills: 50 from Corey Haines and 78 from OpenClaudia).
3. Produce a structured gap diagnosis matrix:
   - **[Ready]**: Skills already active in the current environment.
   - **[Critical Missing]**: Essential skills required for the core deliverables that are currently unlinked.
   - **[Recommended Optional]**: Complementary skills that provide supplementary enhancement.

#### Phase 3: Automated Installation & Symlink Provisioning
1. If global skills are missing across environments, synchronize all global targets by executing:
   `bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh sync-global`
2. If workspace-isolated skills are needed for this repository, create targeted symbolic links in `./.agents/skills/` pointing to the respective upstream path in `~/.gemini/marketing-skills-upstream/`:
   `ln -snf ~/.gemini/marketing-skills-upstream/<repo>/skills/<skill-name> ./.agents/skills/<skill-name>`
3. Enforce the canonical conflict resolution policy:
   - Corey Haines skills retain standard canonical names (e.g., `copywriting`, `product-marketing`, `content-strategy`).
   - Conflicting OpenClaudia skills use the namespace prefix `oc-` (e.g., `oc-copywriting`, `oc-product-marketing`).

#### Phase 4: Health Check & Metadata Validation
1. Validate all symbolic links and ensure each mounted skill contains a valid, well-formed `SKILL.md`:
   `bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh validate`
2. Ensure zero broken symlinks or missing YAML frontmatter descriptions.

#### Phase 5: Readiness Matrix & Kickoff Execution
1. Output an executive **Project Skill Readiness Matrix** summarizing the operational toolchain.
2. Provide immediate next steps and recommend the exact prompt/subagent command to launch Phase 1 of the actual project work.
```

---

## Prompt 2: Quick On-Demand Skill Audit & Mounting

> **When to use**: Use mid-project whenever you encounter a specific task requiring an unmounted capability (e.g., competitor profiling, CRO audit, email sequences).

```markdown
Please inspect, verify, and mount the required specialized skill(s) for the current task.

### Target Functional Area / Skill Required:
[Specify target capability, e.g.:
- Ideal Customer Profile builder: `icp-builder`
- Competitor strategy breakdown: `competitor-analysis`
- Conversion rate optimization audit: `cro` or `page-cro`
- Drip email automation sequences: `email-sequence`
- Viral thread & social copy: `thread-writer` / `social-content`]

### Execution Protocol:
1. Check whether the target skill is already linked in your active environment (`~/.gemini/config/skills/`, `~/.codex/skills/`, or `./.agents/skills/`).
2. If unlinked or missing, search `~/.gemini/marketing-skills-upstream/marketingskills/skills/` and `~/.gemini/marketing-skills-upstream/openclaudia-skills/skills/`.
3. Provision the symbolic link to mount the skill, resolve any name conflicts, and verify that `SKILL.md` is readable.
4. Briefly summarize the skill's trigger guidelines and immediately proceed to execute my task using that skill's documented best practices.
```

---

## Prompt 3: Project-Level Auto-Discovery Protocol (Embed in AGENTS.md / GEMINI.md)

> **When to use**: Add to the root `AGENTS.md` or `GEMINI.md` of any project repository. Gives all visiting agents autonomous skill-awareness without manual re-prompting.

```markdown
<!-- agent-skills-auto-discovery:start -->
# Agent Skills Auto-Discovery & Execution Protocol

When operating within this repository:

1. **Skill Discovery Hierarchy**:
   - **Workspace Local**: `./.agents/skills/<skill-name>/`
   - **Global AI Environments**: `~/.gemini/config/skills/`, `~/.codex/skills/`, `~/.claude/skills/`, `~/.agents/skills/`
   - **Local Upstream SSOT**: `~/.gemini/marketing-skills-upstream/` (128 marketing skills)

2. **Autonomous Skill Detection & Resolution**:
   - Before tackling any domain task (marketing strategy, copywriting, landing page CRO, SEO audits, paid ads, campaign automation), check if the appropriate specialized skill is available.
   - If a required skill is missing from your active context:
     a. Search `~/.gemini/marketing-skills-upstream/marketingskills/skills/` (Corey Haines) and `~/.gemini/marketing-skills-upstream/openclaudia-skills/skills/` (OpenClaudia).
     b. Link it into `./.agents/skills/<skill-name>` or run `bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh sync-global`.
     c. In case of naming collisions, Corey Haines holds canonical names and OpenClaudia uses the `oc-` prefix.
   - Always read the mounted skill's `SKILL.md` reference material before producing deliverables.
<!-- agent-skills-auto-discovery:end -->
```
