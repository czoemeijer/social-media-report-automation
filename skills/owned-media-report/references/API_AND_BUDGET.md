# API and budget reference

The Skill reads authorized Facebook Pages, linked Instagram Professional accounts, and Meta Ad
Accounts. Instagram media and Insights are organic. Marketing API Insights are paid. The report
keeps those domains separate because their audience overlap is unknown.

The reporting workflow requests period-bounded Ads Insights first, then batch-reads metadata and
creatives only for campaign and ad IDs present in those Insights; ad set metadata is already carried
by period-scoped ad set Insights. `snapshot.json` is a
private, credential-free cache envelope keyed by provider, selected assets, API version, and exact
period. A completed historical same-period snapshot prevents duplicate API acquisition regardless
of the generic TTL; current/partial periods require freshness. `--refresh` bypasses reuse.
`analysis.json` is the compact Skill context. The validated `insights.json` records narrative claims
and their evidence references. `report.pdf` is the primary human artifact; the self-contained HTML
is its deterministic source and remains available for audit.

Budget inputs support CSV and TSV. Recognized concepts include publication date, validity, platform,
targeting, content name, task link, campaign/category, content ID or permalink, planned spend,
boost status, plan-recorded actual spend, notes, and explicit campaign/ad set/ad IDs. Header aliases
are normalized and can be extended by callers.

Matching priority is exact Instagram permalink, exact Facebook object ID, exact ad/campaign/ad set
ID, then another exact platform content identifier. Similar titles never create an authoritative
match. Results are `matched`, `unmatched`, `ambiguous`, or `needs_review`. Reconciliation uses one
chosen Insights level (ad by default), so parent and child spend are never summed together.

Paid action types remain distinct. The Ads `clicks` field is labeled all clicks; `link_click`,
`landing_page_view`, `post_engagement`, `post_reaction`, `video_view`, and save actions are exposed
separately when present. Missing action types remain unavailable. Campaign efficiency is ranked
only within awareness, engagement, traffic, sales, or other objective groups.
