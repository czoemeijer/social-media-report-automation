# Social Media Report & Audit Skill (`social-report-audit`)

<div align="center">

[![CI](https://github.com/czoemeijer/social-media-report-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/czoemeijer/social-media-report-automation/actions/workflows/ci.yml)
[![Agent Skills Compatible](https://img.shields.io/badge/Agent_Skills-1.0-blue.svg)](https://skills.sh)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org)
[![Dependencies: Zero](https://img.shields.io/badge/Dependencies-Zero-success.svg)](skills/social-report-audit/scripts/calculate_metrics.py)
[![Tests: 18 Passed](https://img.shields.io/badge/Tests-18%20Passed-brightgreen.svg)](tests/)

**An open-source Agent Skill and deterministic calculation engine that audits social media campaign screenshots (Instagram & Facebook Insights), prevents LLM arithmetic hallucinations, detects platform discrepancies, and produces executive-ready audit reports.**

[Quickstart](#quickstart) •
[Core Audit Rules](#the-four-golden-audit-rules) •
[Drag & Drop UI](#drag--drop-ui-for-non-technical-users) •
[SOP Workflow](docs/SOP.md) •
[Contributing](CONTRIBUTING.md)

</div>

---

## The Problem: Why LLM Math Fails in Campaign Reporting

Social media reporting across influencer agencies, brands, and creators regularly suffers from four major flaws when processed by generative AI:

1. **Arithmetic Hallucination & Unit Misinterpretations:** LLMs routinely confuse rounded UI tokens (e.g. converting `1.1k` to `1,100` when exact records show `1,225`, or mis-summing four engagement actions like the classic 2,071 vs 2,107 bug).
2. **Conflating Platform Interactions with Direct Reactions:** Blindly trusting Meta's composite "Interactions" card (which contains profile visits, sticker taps, and bio link clicks) and reporting it as post reactions (Likes + Comments + Shares + Saves).
3. **Flawed Reach Aggregation:** Arithmetically adding post Reach across different creators or dates and falsely presenting it as "Unique Campaign Reach".
4. **Organic vs. Paid Media Blurring:** Silently blending paid ad delivery into organic creator benchmarks when Meta displays its combined ads notice.

## What This Skill Solves

`social-report-audit` couples multimodal visual extraction with a **zero-dependency, deterministic Python engine** (`calculate_metrics.py`). It enforces mathematical rigor, strict provenance tracking, and factual accountability.

---

## System Architecture

```mermaid
flowchart TD
    subgraph INTAKE ["1. Intake & Perception"]
        A["Screenshots / Images\n(IG / FB Insights)"] --> B["Multimodal Vision Agent\n(Claude 3.5 / Gemini / GPT-4o)"]
        B --> C["Data Extraction\n(Exact numbers vs Approximate tokens)"]
    end

    subgraph ENGINE ["2. Deterministic Audit Engine (Zero Dependencies)"]
        C --> D["calculate_metrics.py"]
        D --> E["Discrepancy Audit\n(Known Actions vs Platform Total)"]
        D --> F["Scope Validation\n(Organic vs Mixed Ads vs Paid)"]
        D --> G["Engagement Lower Bound Check\n(Missing '--' Protection)"]
    end

    subgraph OUTPUT ["3. Verified Deliverables"]
        E & F & G --> H["Structured Markdown Report\n(Fact vs Derived vs Hypothesis)"]
        E & F & G --> I["Normalized JSON / Analytics Output"]
        E & F & G --> J["Drag & Drop Web App / Streamlit UI"]
    end
```

---

## The Four Golden Audit Rules

| Rule | Principle | Enforcement Mechanism |
| :--- | :--- | :--- |
| **1. Incomplete Engagement Protection** | If any component of $\text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$ is missing or `--`, **complete ER MUST NOT be reported.** | Script sets `calculated_er_by_reach = None` and outputs an auditable **Minimum Lower Bound** (`er_lower_bound_by_reach`). |
| **2. Ads Disclaimer Scope Classification** | If Insights states *"Insights include data from your post/reel and any ads"* without a separate Ad tab breakdown: | Scope is strictly classified as `mixed_or_unknown` with mandatory notice that organic and paid contributions cannot be separated. |
| **3. Absence is NOT Zero** | If a platform card omits a metric (e.g. Profile Activity card showing Follows but not External Link Taps): | Metric remains `null / unavailable`, never coerced to `0`. Zero requires explicit UI evidence (`Business address taps: 0`). |
| **4. Feed vs. Insights Separation** | Feed-visible share/send (paper plane) and repost (arrows) counts: | Preserved in separate fields (`feed_shares`, `feed_reposts`) without overwriting canonical Insights shares. |

For detailed mathematical formulas and schemas, consult:
- [Metric Reference Guide](skills/social-report-audit/references/METRICS.md)
- [Data Model & Source-of-Truth Hierarchy](skills/social-report-audit/references/DATA_MODEL.md)
- [Standard Report Templates](skills/social-report-audit/references/REPORT_FORMAT.md)
- [Standard Operating Procedure (SOP)](docs/SOP.md)

---

## Quickstart

### 1. Install as an Agent Skill (Recommended)

Install globally or into your workspace using the standard `skills` CLI:

```bash
# Install globally for all supported agents (Antigravity, Claude Code, Cursor, Codex)
npx -y skills add czoemeijer/social-media-report-automation --skill social-report-audit -g -y

# Or install locally in current project:
npx -y skills add czoemeijer/social-media-report-automation --skill social-report-audit -y
```

### 2. Manual CLI Execution

The calculation engine is self-contained with **zero third-party dependencies** (requires Python 3.9+ standard library only):

```bash
# Run against a normalized JSON file
python3 skills/social-report-audit/scripts/calculate_metrics.py examples/sample-input.json

# Or pipe JSON via stdin
cat examples/sample-input.json | python3 skills/social-report-audit/scripts/calculate_metrics.py --stdin
```

See [examples/sample-report.md](examples/sample-report.md) for a sample generated output.

---

## Drag & Drop UI for Non-Technical Users

For account managers, coordinators, or teammates who prefer a visual drag-and-drop workflow:

```bash
# 1. Install optional lightweight UI dependencies
pip install streamlit pillow

# 2. Launch the studio
streamlit run clients/streamlit_app.py
```

* **Drag & Drop Upload:** Drop multiple screenshot files into the browser.
* **Instant KPI Cards:** Shows Views, Non-Unique Summed Reach, Known Actions, and Weighted ER Lower Bound.
* **One-Click Export:** Download client-ready Markdown audit reports.

For enterprise teams deploying on **Dify**, review the [Client & UI Solutions Architecture Guide](docs/CLIENT_SOLUTIONS.md).

---

## Privacy & Security Model

This project is built for zero data leakage when working with confidential brand assets:

1. **Strict Git Exclusions:** `.gitignore` blocks screenshots (`*.png`, `*.jpg`, `*.jpeg`), media files, archives, secrets, and private reports.
2. **Synthetic Public Fixtures:** All repository tests and examples use strictly synthetic data.
3. **Local Deterministic Execution:** The core calculation script performs no external telemetry or tracking.

---

## Testing & Verification

Run the comprehensive unit and regression test suite:

```bash
python3 -m unittest discover tests -v
```

All 18 unit and regression tests pass deterministically across:
* **Regression Case 1 (FB Reel):** $398 + 28 + 2 + 9 = 437 \rightarrow 437 / 11,500 \approx 3.80\%$ (approximate flag preserved).
* **Regression Case 2 (IG Reel):** $1,225 + 64 + 3 + 39 = 1,331 \rightarrow 1,331 / 17,664 \approx 7.53\%$ (prevents rounding to 1,100).
* **Regression Case 3 (IG Reel):** $130 + 6 + 3 + 111 = 250 \rightarrow 250 / 7,563 \approx 3.31\%$ (recipe save rate verified).
* **Regression Case 4 (IG Reel):** $123 + 2 + 2 + 49 = 176 \rightarrow 176 / 6,402 \approx 2.75\%$.
* **Regression Case 5 (Interaction Bug Fix):** Asserts $1,753 + 100 + 10 + 208 = 2,071$ (never 2,107 without uncategorized actions cataloged).
* **Post-Audit Cases (6–18):** Incomplete ER lower bound enforcement, ads disclaimer scope isolation, absence vs. zero preservation, and feed-visible share conflict resolution.

---

## Project Structure

```
social-media-report-automation/
├── README.md                                  # Project overview and instructions
├── LICENSE                                    # MIT License
├── CONTRIBUTING.md                            # Contribution guidelines
├── CHANGELOG.md                               # Version release notes
├── package.json                               # Package and skills CLI metadata
├── .gitignore                                 # Protection against data leakage
├── .github/
│   ├── workflows/ci.yml                       # GitHub Actions CI (Linux/macOS, Python 3.9-3.12)
│   ├── ISSUE_TEMPLATE/                        # Bug report and feature request templates
│   └── PULL_REQUEST_TEMPLATE.md               # Standardized PR checklist
├── skills/
│   └── social-report-audit/
│       ├── SKILL.md                           # Main agent instruction definition
│       ├── references/
│       │   ├── METRICS.md                     # Formulas, scopes, and aggregation rules
│       │   ├── DATA_MODEL.md                  # Provenance hierarchy and schema
│       │   └── REPORT_FORMAT.md               # Markdown report templates
│       └── scripts/
│           └── calculate_metrics.py           # Python deterministic calculation engine
├── docs/
│   ├── SOP.md                                 # Standard Operating Procedure for audit teams
│   └── CLIENT_SOLUTIONS.md                    # Dify & Streamlit UI architectural guide
├── clients/
│   └── streamlit_app.py                       # Drag-and-drop web/desktop client
├── examples/
│   ├── README.md                              # Guide to synthetic test cases
│   ├── sample-raw-input.md                    # Raw simulation input
│   ├── sample-input.json                      # Normalized test fixture
│   └── sample-report.md                       # Sample Markdown output
└── tests/
    ├── test_regression_cases.py               # 15 regression test cases
    └── test_calculate_metrics.py              # 3 CLI and edge-case unit tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).
