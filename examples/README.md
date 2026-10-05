# Examples & Synthetic Reproducibility

This folder provides a complete, privacy-safe, reproducible end-to-end example of the `social-report-audit` workflow.

---

## Files in this Directory

- **`sample-raw-input.md`**: Realistic raw notes and screenshot metric transcriptions (approximate values, missing values, platform discrepancies).
- **`sample-input.json`**: The canonical normalized JSON representation conforming to [references/DATA_MODEL.md](../skills/social-report-audit/references/DATA_MODEL.md).
- **`sample-report.md`**: The final auditable Markdown report produced from this data conforming to [references/REPORT_FORMAT.md](../skills/social-report-audit/references/REPORT_FORMAT.md).
- **`sample-story-series-input.json`**: Sample input data for the `story-series-extract` skill (Instagram Story sequences).
- **`sample-story-series-report.md`**: Standardized output report for Story series performance and poll results.

---

## How to Reproduce Calculations

You can run the deterministic calculation script directly against the sample input:

```bash
# From the repository root:
python3 skills/social-report-audit/scripts/calculate_metrics.py examples/sample-input.json
```

This output demonstrates:
1. Handling of approximate Reach (`cca 12,000` -> `ER ≈ 5.41%`).
2. Missing metrics disclosure (Modern Baker has unreadable shares -> marked null and explicitly noted).
3. Separation of platform-reported interactions (Story sticker taps) from known engagement actions.
4. Non-additive Reach warning across multiple creators.
