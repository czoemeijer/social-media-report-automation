# Architecture

## Source boundaries

There are two intentional evidence paths. Third-party creator data enters through screenshots or
ZIPs because an operator's Meta token normally cannot read a creator's private Insights. Authorized
owned assets enter through `src/social_report/sources/meta`. Both converge on the canonical
deterministic core and exports; Skills and Dify remain adapters, never competing business-logic
implementations.

The Meta adapter is read-only and split into auth/client, discovery, Instagram, Ads, Insights
normalization, exact identity matching, and canonical mapping. A future TikTok source should reuse
the same source-to-canonical boundary without changing current creator evidence semantics.

## Boundaries

`src/social_report` is the only maintained source of business rules. Agent Skill scripts import it.
The Dify plugin build stages that package into `.difypkg`; it does not maintain a second code copy.

The owned-media Agent Skill is the primary product surface. Its `report` entry point resolves one
completed reporting period, reuses or acquires one credential-free private snapshot, builds one
compact `analysis.json`, validates evidence-bound narrative, and renders JSON/CSV/Markdown/HTML/PDF
from that same snapshot. Dify is the
secondary guided WebApp surface. The CLI remains a low-level operator interface and calls the same
workflow rather than maintaining parallel report logic.

For Meta Ads, the source adapter requests bounded Insights before metadata. Campaign, ad set, and
ad identifiers found in the selected period are then batch-read directly; normal reporting never
enumerates the full historical account inventory. Snapshot identity includes provider, selected
assets, API version, and exact period. Freshness is explicit, `--refresh` is opt-in, and a stale
same-period snapshot is accepted only as a reported fallback after a rate-limit failure.

Dify performs AI work:

1. global low-detail campaign reconstruction;
2. per-asset structured vision extraction;
3. a second pass only when validation returns `needs_review`;
4. narrative report writing from audited JSON, without screenshot access.

The plugin performs deterministic work:

1. upload validation and source manifests;
2. safe ZIP reading and directory evidence preservation;
3. per-asset file selection;
4. extraction validation and normalization;
5. scope-aware metrics, Story consistency, discrepancies, and review status;
6. JSON, CSV, and deterministic Markdown export.

## Intentional exclusions

- No standalone FastAPI backend: Dify Plugin Runtime can execute the required Python tools.
- No Redis, PostgreSQL, worker, or project container: a report needs no project-owned durable state.
- No Streamlit: duplicate UI and simulated metrics were removed.
- No mandatory n8n: external event automation is optional and points into Dify.
- No mandatory OCR: it remains an optional future adapter only if measured evaluation justifies it.
- No browser chart runtime or CDN: owned-media HTML uses deterministic inline CSS and SVG.

## Evidence hierarchy

Visual platform UI, account handles, thumbnails, and dates outrank directory and filename hints.
Paths remain useful contextual evidence and are preserved in ZIP manifests. Contradictions produce
warnings; unknown values remain unknown.
