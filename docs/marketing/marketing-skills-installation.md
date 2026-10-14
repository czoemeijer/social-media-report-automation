# Marketing Skills Global Installation & Architecture Guide

## 1. Global Multi-Environment Architecture

```
~/.gemini/
├── marketing-skills-upstream/          # Git Upstream SSOT (128 marketing skills)
│   ├── marketingskills/                # Corey Haines (50 skills)
│   ├── openclaudia-skills/             # OpenClaudia (78 skills)
│   ├── docs/                           # Central Documentation
│   └── marketing-skills-manage.sh      # Unified Multi-Environment Management Script
│
├── config/skills/                      # Google Antigravity / Gemini (128 symlinks)
~/.codex/skills/                        # OpenAI Codex Global Skills (128 symlinks)
~/.claude/skills/                       # Claude Code Global Skills (128 symlinks)
~/.agents/skills/                       # Universal Agents Standard Skills (128 symlinks)
~/.cc-switch/skills/                    # CC-Switch Central Skill Storage (128 symlinks)
~/.cc-switch/cc-switch.db               # CC-Switch SQLite Registry (enabled_gemini/codex/claude=1)
```

## 2. Installation Record

| Field | Corey Haines Library | OpenClaudia Library | Total / Unified |
| :--- | :--- | :--- | :--- |
| **Repository** | `coreyhaines31/marketingskills` | `OpenClaudia/openclaudia-skills` | 2 Repositories |
| **License** | MIT | MIT | Open Source |
| **Total Skills** | 50 | 78 | **128 Skills** |
| **Activated Status** | 50 (Canonical) | 78 (71 Unique + 7 Prefixed) | **128 / 128 (100% Activated)** |
| **Platforms Covered** | Antigravity, Codex, Claude Code, Agents, CC-Switch | Antigravity, Codex, Claude Code, Agents, CC-Switch | **5 Environments Synced** |

## 3. Conflict Resolution Strategy

| Canonical (Corey Haines) | Prefixed (OpenClaudia) | Recommendation |
| :--- | :--- | :--- |
| `content-strategy` | `oc-content-strategy` | Corey Haines for deep frameworks, OpenClaudia for rapid drafting |
| `copy-editing` | `oc-copy-editing` | Corey Haines removes AI slop patterns |
| `copywriting` | `oc-copywriting` | Corey Haines for page-level conversions |
| `marketing-ideas` | `oc-marketing-ideas` | OpenClaudia for channel ideas, Corey Haines for loops |
| `product-marketing` | `oc-product-marketing` | Corey Haines for strategic positioning & GTM |
| `programmatic-seo` | `oc-programmatic-seo` | Both provide complementary template workflows |
| `seo-audit` | `oc-seo-audit` | OpenClaudia focuses on technical SEO, CH on content |

## 4. Maintenance Commands

```bash
# Check status across all 5 environments
bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh active

# Validate symlink and SKILL.md health
bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh validate

# Pull latest commits and re-sync all environments
bash ~/.gemini/marketing-skills-upstream/marketing-skills-manage.sh update
```
