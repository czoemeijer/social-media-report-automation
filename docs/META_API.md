# Meta owned-media API

The adapter targets Graph API `v26.0` and reads only assets authorized for the configured token. It
uses the Page-to-Instagram relationship instead of assuming a token can read unrelated creator
Insights. Third-party creator reporting remains screenshot/evidence-first.

## Configuration and discovery

Copy `.env.example` to ignored `.env.local`, add your own token, then run:

```bash
social-report meta discover --json
social-report meta doctor
```

For a normal complete report, use the Agent Skill. Its high-level command is also available to
operators:

```bash
python3 skills/owned-media-report/scripts/owned_media_report.py report \
  --from 2026-09-01 --to 2026-09-30 \
  --output-dir private/reports/2026-09 --language en
```

Omitting both date flags selects the previous completed calendar month. The output directory holds
the private `snapshot.json`, compact `analysis.json`, validated `insights.json`, and report
JSON/CSV/Markdown/HTML/PDF. A valid snapshot for a completed historical period is reused regardless
of the generic 36-hour TTL when it was captured after that period ended; `--refresh` is the
explicit override. Current or partial periods still obey the TTL. A valid same-period snapshot can
also be used as an explicitly reported fallback when Meta rate-limits a refresh. Concurrent local
requests for the same provider, asset selectors, period, and API version share one acquisition.

With one unambiguous compatible relationship, selectors can resolve automatically. Multiple Pages
or Ad Accounts require `META_PAGE_ID`, `META_AD_ACCOUNT_ID`, or matching CLI flags. The linked
Instagram Professional account normally comes from the selected Page; `META_IG_USER_ID` is an
explicit override and is validated against that relationship when possible.

## Authentication progression

Use a temporary Graph API Explorer User Token only for development. An early internal deployment
can exchange an eligible short-lived User Token for a long-lived token when `META_APP_ID` and
`META_APP_SECRET` are configured:

```bash
social-report meta exchange-user-token --save-to private/meta-user-token.secret
```

The command never prints the token, validates the exchanged candidate's app, validity, and required
scopes before an atomic save, and refuses to overwrite the target. Meta documents exchange from an
eligible short-lived User Token to a roughly 60-day long-lived User Token, but does not document a
perpetual unattended server-side User Token renewal flow. This project therefore does not schedule
renewal, automate browser login, or replace credentials in place. Its 14/7/3-day lifecycle warnings
are operator policy, not Meta guarantees. For stable server-side automation, consume a Business
Manager System User Token with
`META_AUTH_MODE=system_user_token`; this project does not create System Users or bypass Meta
administration. App Review or advanced access can be required for third-party client assets. A
token described as non-expiring can still lose permissions or asset access.

When an app secret is configured, server calls include the official HMAC-SHA256
`appsecret_proof`. Token debug is capability-based and only runs when both app ID and secret are
available.

## Data contracts

- Instagram: profile, paginated media, common media Insights, and Reel watch-time values preserved
  in milliseconds.
- Ads: period-bounded Insights at account/campaign/ad set/ad levels are fetched first. Only campaign
  and ad IDs present in those results are read for campaign objective plus ad/creative metadata.
  Ad set identity and metrics already come from ad set Insights, so no duplicate ad set metadata
  read is made. Raw `actions` and `cost_per_action_type` arrays are retained alongside stable maps.
- Matching: exact `source_instagram_media_id`, normalized Instagram permalink, then another exact
  documented identifier. Caption/date similarity is never authoritative.
- Budget: CSV/TSV, normalized configurable headers, Decimal money, explicit reconciliation states,
  and exactly one Ads Insights aggregation level per calculation.

Organic reach and paid reach are never added and presented as unique reach. Organic views and paid
impressions remain different metrics. Platform-reported `total_interactions` remains separate from
the local sum of likes, comments, saves, and shares.

The deterministic analysis keeps the Ads `clicks` field separate from `link_click`,
`landing_page_view`, `post_engagement`, `post_reaction`, `video_view`, and save action types. Missing
actions remain unavailable rather than becoming zero. Campaign rankings occur only inside the same
objective group; sales efficiency requires an actual purchase/conversion action.

When an Ad Creative points to an Instagram media object outside the selected owned account, the
adapter may retain that exact object as `reference_only`. This proves content identity for the paid
creative but leaves organic Insights unavailable; it never treats object readability as permission
to claim another creator's private analytics.

Facebook Page identity and the Page-to-Instagram relationship are supported. Facebook organic Post
Insights and Instagram Story ingestion are optional capabilities and are not claimed by this
release; active/historical Story limitations do not change the screenshot-first Story Skill.

## Reliability and security

The standard-library HTTP client sets connect/read timeouts, a User-Agent, bounded exponential
backoff, cursor pagination, and structured errors. Errors are classified as `TRANSPORT`,
`SERVER_TRANSIENT`, `RATE_LIMIT`, `AUTH`, `PERMISSION`, `INVALID_REQUEST`, or `OTHER`. Only transport
and transient server failures are retried. A rate-limit response stops immediately, preserves
sanitized `Retry-After`/estimated-regain guidance, and lets the workflow use a valid same-period
snapshot rather than increasing regain time. Authentication, permission, and malformed requests
are not retried blindly. Paging URLs and raw response bodies are not persisted.

Usage is observed opportunistically from `X-App-Usage`, `X-Ad-Account-Usage`, and
`X-Business-Use-Case-Usage` on responses already being made. No quota polling request exists;
business/account IDs and undocumented fields are discarded. The project health policy is:
`UNKNOWN` without telemetry, `HEALTHY` below 70%, `ELEVATED` at 70%, `HIGH` at 85%, `CRITICAL` at
95%, and `BLOCKED` after an actual rate-limit response. These thresholds are local operating policy,
not Meta-defined service levels. `doctor` reports the sanitized summary accumulated by its normal
checks.

Graph batch and multi-ID requests reduce HTTP round trips, not Meta quota consumption: each
subrequest still counts. The collector keeps the code-100 multi-ID compatibility fallback, bounds
reads to report-period IDs, and does not poll quota endpoints.

| Concern | Meta documents | Project behavior |
| --- | --- | --- |
| Long-lived User Token | Eligible exchange; commonly about 60 days; expired tokens require login again | Manual exchange, candidate validation, atomic new-file save; no automatic renewal |
| Usage telemetry | Usage response headers and regain estimates | Parse existing responses only; sanitize IDs; apply explicit local thresholds |
| Throttling | Stop calls and wait/reduce load | No rate-limit retry loop; structured wait guidance and snapshot fallback |
| Batch requests | Up to 50 operations; each operation counts | Use only for transport efficiency, never claim quota savings |
| Historical Insights | Narrow, non-overlapping date ranges are preferred | Completed-period snapshot is immutable-by-policy unless `--refresh` |

Official Meta references used for the current contract:

- [Secure Graph API requests and appsecret_proof](https://developers.facebook.com/docs/graph-api/guides/secure-requests)
- [Long-lived access tokens](https://developers.facebook.com/documentation/facebook-login/guides/access-tokens/get-long-lived)
- [Debug Token](https://developers.facebook.com/docs/graph-api/reference/debug_token/)
- [Graph API rate limiting and usage headers](https://developers.facebook.com/docs/graph-api/overview/rate-limiting/)
- [Graph API error handling](https://developers.facebook.com/docs/graph-api/guides/error-handling/)
- [Graph API batch requests](https://developers.facebook.com/docs/graph-api/batch-requests)
- [Instagram Insights](https://developers.facebook.com/documentation/instagram-platform/insights)
- [Marketing API Insights](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights)
- [Marketing API Insights best practices](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights/best-practices)
