---
name: owned-media-report
description: Generate, explain, and refresh a complete authorized Instagram organic and Meta Ads report from one reusable snapshot.
---

# Owned Media Report

Use this Skill when a user asks in natural language for an owned-media report, a previous-month
report, an organic-versus-paid explanation, or a refresh of an existing report. The normal user
should not have to compose low-level CLI calls. Keep `social-report-audit` and
`story-series-extract` for third-party creator evidence; an operator token does not grant private
creator Insights unless that creator independently authorized the application.

## Workflow

For a request such as “Generate the September owned-media report and analyze what matters,” operate
autonomously:

1. Resolve the requested period. Use exact dates when supplied. For "last month" or an unspecified
   monthly report, use the previous completed calendar month; never silently use a partial current
   month.
2. Look for a matching snapshot in the report directory or at a supplied snapshot path before
   checking authentication. A complete historical snapshot can be rendered offline even when it is
   stale; disclose its capture time and do not imply that it was refreshed.
3. Determine whether fresh API access is available only if no usable snapshot exists or the user
   explicitly requests a refresh. A completed historical period remains reusable regardless of the
   generic TTL; current or partial periods do not. Fetch once when truly necessary; a local
   single-flight lock coalesces concurrent requests for the same acquisition, and every exporter
   must use the same resulting snapshot.
4. Generate compact deterministic `analysis.json`. Read that file, not the large snapshot, and
   create evidence-backed insights whose references resolve to analysis fields.
5. Render Markdown, HTML, PDF, CSV, JSON, and the narrative from the same snapshot. Inspect the PDF
   for clipping, overlap, blank pages, and legibility.
6. Return the PDF path first with concise findings and a clear freshness statement.

The user does not need to know the diagnostic commands. The single high-level operator entry point
used behind this workflow is:

   ```bash
   python3 skills/owned-media-report/scripts/owned_media_report.py report \
     --from YYYY-MM-DD --to YYYY-MM-DD \
     --output-dir private/reports/YYYY-MM --language en
   ```

   Omit both date flags to select the previous completed month. Add `--refresh` only when the user
   asks for fresh data. Add `--budget path/to/plan.csv` or `.tsv` when a plan is supplied.
7. The command checks configuration/assets only when acquisition is necessary, reuses a fresh
   same-period `snapshot.json`, performs one live acquisition when needed, computes deterministic
   analytics, validates evidence references in `insights.json`, and writes `snapshot.json`,
   `analysis.json`, `insights.json`, `report.json`, `report.csv`, `report.md`, `report.html`, and
   `report.pdf`.
8. Read compact `analysis.json`, not the large raw snapshot, to explain the result. Keep claims tied
   to named analysis fields, distinguish observations from causes, avoid external benchmarks unless
   the user supplied them, and call out unavailable metrics explicitly.
9. Inspect the rendered PDF for clipping, overlap, blank pages, and legibility. Give the user the PDF
   path first; HTML and Markdown are audit/fallback artifacts.
10. If asset selection is ambiguous, use `doctor` and `discover --json`, then require explicit
   `META_PAGE_ID` / `META_AD_ACCOUNT_ID`; never choose the first result.

The high-level wrapper invokes the canonical `social_report` workflow. The core owns collection,
snapshot validation, matching, analytics, budget reconciliation, and rendering. Low-level `pull`
commands, `doctor`, `discover`, cache details, and renderer selection remain developer/operator
internals, not the normal Skill workflow.

## Guardrails

- Read credentials only from the process environment or ignored `.env.local`.
- Keep output under an ignored private directory. Never paste, print, store in reports, or commit
  access tokens, app secrets, paging URLs, snapshots, account IDs, campaign names, or captions.
- Reuse a valid completed-period snapshot unless `--refresh` is explicit. For current/partial
  periods, require a fresh snapshot unless explicitly offline. A valid same-period stale snapshot
  may be used as a clearly reported rate-limit fallback; never describe it as freshly acquired.
- Read quota telemetry only from response headers already returned by required calls. Never poll for
  quota. Stop on `RATE_LIMIT`; do not retry-storm, and report snapshot fallback or wait guidance.
- Treat token exchange as a manual operator action. Validate the candidate before saving to a new
  path; never invent unattended renewal, automate login, overwrite an active token, or expose it.
- Treat organic reach and paid reach as separate, non-additive domains.
- Treat `total_interactions` as platform-reported and separate from calculated action components.
- Accept only exact platform identifiers or normalized permalinks as authoritative matches.
- Compare campaigns only within objective groups. Do not infer conversions from clicks, landing
  views, or engagement actions.
- Treat correlations and period differences as observations, not causal effects. Do not invent
  industry benchmarks or recommend budget changes without evidence and an explicit decision basis.
- Do not publish content, mutate campaigns, or request `ads_management` for reporting.
- Mark absent and unsupported metrics unavailable; never turn absence into zero.

See [API and budget reference](references/API_AND_BUDGET.md).
