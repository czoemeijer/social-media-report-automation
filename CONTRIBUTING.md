# Contributing to Social Report Audit

Thank you for your interest in contributing to `social-report-audit`! This project provides deterministic mathematical auditing, provenance tracking, and report generation for social media analytics across AI agents and automated workflows.

---

## Code of Conduct & Core Principles

1. **Deterministic Accuracy Over Guesswork:** Calculation formulas are mathematical baselines. Never introduce fuzzy rounding or silent estimations into core metrics.
2. **One Core:** Business rules belong in `src/social_report`; Skill wrappers and Dify tools must not duplicate formulas.
3. **Strict Privacy & Anonymization:** Never commit proprietary client screenshots, real accounts, or confidential business data. All test cases, examples, and regression fixtures must use synthetic identifiers.
4. **Evidence-Based Compatibility:** A package build is not a live Dify import. Record the Dify,
   plugin SDK, model provider, and runtime evidence before claiming compatibility.

---

## Development Setup

1. **Clone repository:**
   ```bash
   git clone https://github.com/czoemeijer/social-media-report-automation.git
   cd social-media-report-automation
   ```

2. **Install and verify:**
   ```bash
   uv sync --extra dev
   uv run ruff check src tests scripts evals plugins skills
   uv run mypy
   uv run python -m unittest discover -s tests -v
   uv run python scripts/validate_dify_dsl.py
   uv run python scripts/package_plugin.py
   uv build
   ```

---

## Submitting Pull Requests

1. Fork the repo and create your feature branch: `git checkout -b feat/new-platform-support`.
2. Add regression tests for new logic or edge cases. Archive changes require malicious-input tests.
3. Verify that all existing regression cases continue to pass.
4. If changing the plugin, rebuild it and update the DSL dependency checksum.
5. Open a pull request against the `main` branch.
