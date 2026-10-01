# Contributing to Social Report Audit

Thank you for your interest in contributing to `social-report-audit`! This project provides deterministic mathematical auditing, provenance tracking, and report generation for social media analytics across AI agents and automated workflows.

---

## Code of Conduct & Core Principles

1. **Deterministic Accuracy Over Guesswork:** Calculation formulas are mathematical baselines. Never introduce fuzzy rounding or silent estimations into core metrics.
2. **Zero External Runtime Dependencies:** The calculation script (`calculate_metrics.py`) must remain pure standard library Python (Python 3.9+) to ensure instantaneous portability in sandboxed agent environments.
3. **Strict Privacy & Anonymization:** Never commit proprietary client screenshots, real accounts, or confidential business data. All test cases, examples, and regression fixtures must use synthetic identifiers.

---

## Development Setup

1. **Clone repository:**
   ```bash
   git clone https://github.com/czoemeijer/social-media-report-automation.git
   cd social-media-report-automation
   ```

2. **Run test suite:**
   ```bash
   python3 -m unittest discover tests -v
   ```

3. **Verify dual sync:**
   Because this skill is used in both standard agent environments (`skills/`) and Antigravity workspace roots (`.agents/skills/`), ensure any changes to `SKILL.md`, `references/`, or `scripts/` are mirrored in both directories.

---

## Submitting Pull Requests

1. Fork the repo and create your feature branch: `git checkout -b feat/new-platform-support`.
2. Add regression test cases in `tests/test_regression_cases.py` for any new logic or edge cases.
3. Verify that all existing regression cases continue to pass.
4. Open a pull request against the `main` branch.
