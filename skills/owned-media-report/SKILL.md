---
name: owned-media-report
description: Collect and reconcile authorized Instagram organic and Meta Ads performance through the canonical social_report core.
---

# Owned Media Report

Use this Skill for first-party business assets that have authorized Meta API access. Keep the
existing `social-report-audit` and `story-series-extract` Skills for third-party creator evidence;
an operator token does not grant private creator Insights unless that creator independently
authorized the application.

## Workflow

1. Run `scripts/owned_media_report.py doctor` and stop on a core `FAIL`.
2. Run `scripts/owned_media_report.py discover --json`. If multiple compatible assets are shown,
   require explicit `META_PAGE_ID` and/or `META_AD_ACCOUNT_ID`; never choose the first result.
3. Pull a bounded reporting period with `pull --from YYYY-MM-DD --to YYYY-MM-DD`.
4. Optionally pass `--budget path/to/plan.csv` or `.tsv` for deterministic plan-versus-actual
   reconciliation.
5. Export JSON for auditability, CSV for analysis, or Markdown for a concise handoff.

The wrapper contains no API or metric logic. It invokes `social_report.cli`, which uses the shared
canonical source adapter, matching rules, budget reconciler, and exporters.

## Guardrails

- Read credentials only from the process environment or ignored `.env.local`.
- Never paste, print, store in reports, or commit access tokens, app secrets, or paging URLs.
- Treat organic reach and paid reach as separate, non-additive domains.
- Treat `total_interactions` as platform-reported and separate from calculated action components.
- Accept only exact platform identifiers or normalized permalinks as authoritative matches.
- Do not publish content, mutate campaigns, or request `ads_management` for reporting.
- Mark absent and unsupported metrics unavailable; never turn absence into zero.

See [API and budget reference](references/API_AND_BUDGET.md).
