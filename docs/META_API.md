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
JSON/CSV/Markdown/HTML/PDF. A fresh
same-period snapshot is reused automatically; `--refresh` forces acquisition. Stale data is never
silently reused, except as an explicitly reported same-period fallback when Meta rate-limits the
refresh.

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

The command never prints the token and refuses to overwrite the target. For stable server-side
automation, consume a Business Manager System User Token with
`META_AUTH_MODE=system_user_token`; this project does not create System Users or bypass Meta
administration. App Review or advanced access can be required for third-party client assets. A
token described as non-expiring can still lose permissions or asset access.

When an app secret is configured, server calls include the official HMAC-SHA256
`appsecret_proof`. Token debug is capability-based and only runs when both app ID and secret are
available.

## Data contracts

- Instagram: profile, paginated media, common media Insights, and Reel watch-time values preserved
  in milliseconds.
- Ads: period-bounded Insights at account/campaign/ad set/ad levels are fetched first. Only IDs
  present in those results are batch-read for campaign objective, ad set, ad, and creative metadata.
  Raw `actions` and `cost_per_action_type` arrays are retained alongside stable maps.
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
backoff, `Retry-After` handling, cursor pagination, and structured errors. It retries safe GETs only
for transient transport, rate-limit, and server failures. Authentication, permission, and malformed
request errors are not retried blindly. Paging URLs and raw response bodies are not persisted.

Official Meta references used for the current contract:

- [Secure Graph API requests and appsecret_proof](https://developers.facebook.com/docs/graph-api/guides/secure-requests)
- [Long-lived access tokens](https://developers.facebook.com/documentation/facebook-login/guides/access-tokens/get-long-lived)
- [Instagram Insights](https://developers.facebook.com/documentation/instagram-platform/insights)
- [Marketing API Insights](https://developers.facebook.com/documentation/ads-commerce/marketing-api/insights)
