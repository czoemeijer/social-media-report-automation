# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-10-01

### Added
- **Incomplete Engagement Action Lower Bound:** When any of the 4 engagement components (Likes, Comments, Shares, Saves) is missing or unreadable (`--`), calculated ER by Reach is explicitly set to `None` and reported strictly as an incomplete lower bound (`er_lower_bound_by_reach`).
- **Mixed or Unknown Scope:** Automatic classification of `scope: mixed_or_unknown` when Instagram Insights displays the notice *"Insights include data from your post/reel and any ads"* without a separate Ad breakdown.
- **Feed-Visible Distribution Tracking:** Separate fields (`feed_shares`, `feed_reposts`) to track public feed interaction counts independently from canonical Insights shares without overwriting.
- **Absence vs. Zero Safeguard:** Codified rule that unlisted metrics on platform cards remain `null/unavailable` rather than being coerced to zero.
- **GitHub Actions CI:** Cross-platform continuous integration testing across Python 3.9–3.12 on Linux and macOS.
- **Community Standards:** Added `CONTRIBUTING.md`, Issue Templates, PR Template, and comprehensive SOP.
- **Client Architecture Guide & Streamlit App:** Added drag-and-drop web/desktop UI solution guide and standalone `clients/streamlit_app.py`.

### Changed
- Sanitized all regression test suites to use purely anonymized synthetic test fixtures.
- Enhanced `.gitignore` with strict security filters for environment variables, secrets, and temp reports.

## [1.0.0] - 2026-09-28

### Added
- Initial release of `social-report-audit` agent skill.
- Core deterministic calculation engine (`calculate_metrics.py`).
- Source-of-truth hierarchy, canonical data model, and standardized Markdown report templates.
- Regression test suite with 13 baseline unit and integration tests.
