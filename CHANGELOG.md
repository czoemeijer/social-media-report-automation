# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - Unreleased

### Added
- Project-owned Dify plugin with safe intake, ZIP normalization, per-asset file selection,
  extraction validation, deterministic audit, and JSON/CSV/Markdown export tools.
- Dify workflow DSL for global reconstruction, grouped vision extraction, confidence-gated review,
  deterministic auditing, and narrative reporting.
- Canonical `src/social_report` package and generated JSON Schema artifacts.
- Scope buckets, signed interaction discrepancies, Story temporal safeguards, and lightweight
  perceptual duplicate support.
- Synthetic evaluation fixture generator and deterministic scoring harness.
- Privacy, deployment, architecture, and security documentation.

### Changed
- Agent Skill scripts are thin wrappers over the shared core.
- Missing scope now defaults to `unknown`, never `organic`.
- Paid, organic, mixed-or-unknown, and unknown metrics are aggregated separately.

### Removed
- Streamlit and its simulated metric path as a maintained product surface.

## [1.2.0] - 2026-10-02

### Added
- **`story-series-extract` Skill:** Added specialized agent skill for straightforward extraction of Instagram/Facebook Story sequences and campaign creator summaries without complex arithmetic assumptions.
- **Story Series Calculation Engine:** Added `skills/story-series-extract/scripts/extract_story_series.py` supporting series views breakdown, starting reach isolation, drop-off rate, and interactive poll/quiz extraction.
- **Reference Templates & Synthetic Examples:** Added `examples/sample-story-series-input.json`, `examples/sample-story-series-report.md`, and `references/TEMPLATE.md`.
- **Story Series Unit Tests:** Added `tests/test_story_series_extract.py`, bringing test suite to 20 deterministic tests.
- **Anti-Duplicate & Re-Screenshot Protocol:** Codified rules preventing overcounting of Stories due to vertical scroll slices or later timestamped re-screenshots (Story tray thumbnail matching, phone status bar timestamps, and snapshot time consistency).

### Changed
- **Workspace Organization:** Cleaned root workspace, isolated raw local screenshots with strict case-insensitive gitignore media rules (`*.PNG`, `*.png`, etc.).
- **Global & Workspace Sync:** Synchronized `story-series-extract` to `.agents/skills/` and global `~/.gemini/config/skills/`.

## [1.1.0] - 2026-10-01

### Added
- **Incomplete Engagement Action Lower Bound:** When any of the 4 engagement components (Likes, Comments, Shares, Saves) is missing or unreadable (`--`), calculated ER by Reach is explicitly set to `None` and reported strictly as an incomplete lower bound (`er_lower_bound_by_reach`).
- **Mixed or Unknown Scope:** Automatic classification of `scope: mixed_or_unknown` when Instagram Insights displays the notice *"Insights include data from your post/reel and any ads"* without a separate Ad breakdown.
- **Feed-Visible Distribution Tracking:** Separate fields (`feed_shares`, `feed_reposts`) to track public feed interaction counts independently from canonical Insights shares without overwriting.
- **Absence vs. Zero Safeguard:** Codified rule that unlisted metrics on platform cards remain `null/unavailable` rather than being coerced to zero.
- **GitHub Actions CI:** Cross-platform continuous integration testing across Python 3.9–3.12 on Linux and macOS.
- **Community Standards:** Added `CONTRIBUTING.md`, Issue Templates, PR Template, and comprehensive SOP.
- **Client Architecture Guide & Streamlit App:** Added drag-and-drop web/desktop UI solution guide and standalone `ui/streamlit_app.py`.

### Changed
- Sanitized all regression test suites to use purely anonymized synthetic test fixtures.
- Enhanced `.gitignore` with strict security filters for environment variables, secrets, and temp reports.

## [1.0.0] - 2026-09-28

### Added
- Initial release of `social-report-audit` agent skill.
- Core deterministic calculation engine (`calculate_metrics.py`).
- Source-of-truth hierarchy, canonical data model, and standardized Markdown report templates.
- Regression test suite with 13 baseline unit and integration tests.
