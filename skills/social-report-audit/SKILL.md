---
name: social-report-audit
description: Extract social media metrics from screenshots or raw data, validate engagement numbers, audit inconsistencies, calculate derived engagement rates, and generate structured campaign reports. Use when asked to audit or create social media reports, process Instagram/Facebook Insights, or analyze campaign metrics.
---

# Social Media Report & Audit Skill (`social-report-audit`)

This skill audits, validates, normalizes, and reports social media campaign metrics from Instagram and Facebook. It accepts raw numbers, platform UI screenshots, or creator folders, audits discrepancies, computes deterministic engagement indicators, and outputs structured Markdown reports.

---

## 1. Activation Triggers

Activate this skill when the user:
- Requests an audit or report for social media performance (Instagram, Facebook).
- Supplies screenshots of platform insights (Instagram Insights, Meta Business Suite).
- Provides raw social metrics (Views, Reach, Likes, Comments, Shares, Saves, ER).
- Asks to compare influencer/creator campaign outputs or verify engagement calculations.

---

## 2. Source-of-Truth Hierarchy

When evaluating conflicting data points or auditing past campaign materials, follow this strict priority hierarchy:

1. **Tier 1: Original Screenshots / Native Platform CSV/JSON Exports (Highest Authority)**
2. **Tier 2: Explicit Raw Metrics Provided Directly by User**
3. **Tier 3: Client Presentation Decks / Native Campaign Summaries**
4. **Tier 4: Derived / Generated Audit Reports (Lowest Authority — Output, Never Input)**

*Rule:* Generated reports are outputs. Never use a past report to overwrite or "correct" raw screenshot evidence. If sources conflict, document the discrepancy and prefer Tier 1.

For detailed schema and provenance guidelines, consult [references/DATA_MODEL.md](references/DATA_MODEL.md).

---

## 3. Extraction & OCR Safety Rules

When extracting metrics from platform screenshots:

1. **Exact vs. Approximate Reading:**
   - If an exact number is displayed (e.g., `1,225`), record `1,225`. Never round to `~1,100`.
   - If a number uses abbreviation notation (e.g., `cca 11,5 tis.`, `1.1k`), mark the value as **approximate** (`~11,500`, `~1,100`).
2. **Unreadable / Cropped Figures:**
   - Do **not** guess missing, truncated, or blurred numbers. Mark them as `Unreadable / Not available`.
3. **Absence vs. Zero Distinction:**
   - The absence of a metric line on a screenshot is **not** equivalent to zero. If a platform card omits a metric (e.g. a Reel Profile Activity card showing only Follows, omitting External link taps), record the metric as `unavailable / not shown` (`null`), never as `0`. A value of `0` is valid only when explicitly displayed with a numeric zero (e.g. `Business address taps: 0`).
4. **Feed-Visible vs. Canonical Insights Shares:**
   - Feed-visible send/share (paper plane) and repost (arrows) metrics must be captured separately from canonical Insights Shares. When they conflict, present both values without overwriting or silently substituting one for the other.
5. **Tab & Post Deduplication:**
   - Distinguish multiple tabs of the same post (e.g., *Přehled*, *Projevený zájem*, *Okruh uživatelů*) from separate posts.
   - Merge complementary metrics belonging to the same post ID/timestamp without double-counting.
6. **Story Deduplication & Re-screenshot Safeguard:**
   - **Never equate the number of screenshots with the number of Stories.** An influencer often provides multiple screenshots of the same story:
     - *Scroll slices:* Consecutive screenshots at the same timestamp (e.g. `10:00`) showing upper, middle, or lower portions of the same Story Insights screen.
     - *Re-screenshots over time:* A later screenshot (e.g. next morning `09:00`) taken to capture comments, sticker interactions, or final viewer counts.
   - **Mandatory check:** Verify the top Story tray thumbnail. If two screenshots have the same thumbnail, visual layout, and topic selected, they are **the exact same story**. Never count a later re-screenshot as an additional story or a "repost".

---

## 4. Scope Classification: Organic vs. Paid Media vs. Mixed

Always classify each extracted data point into its appropriate domain:

- **Organic Creator Content:** Views, Organic Reach, Likes, Comments, Shares/reposts, Saves, Creator ER.
- **Paid Media / Boosted Posts:** Paid Impressions, Paid Reach, Link Clicks, Media Spend, CPM, CPC, CTR, Ad Engagement.
- **Mixed or Unknown Scope:** When Instagram Insights displays the notice *"Insights include data from your post/reel and any ads"* and no separate `Ad` tab breakdown is provided.

*Rules:*
- **Ads Disclaimer Rule:** If the screenshot states *"Insights include data from your post/reel and any ads"*, the metrics **must not** be automatically classified as organic. Without a separate Ad breakdown, classify the scope as `mixed_or_unknown` and explicitly state: *"Organic and paid contributions cannot be separated without a separate Ad breakdown."*
- **Never** use Paid Reach as the denominator for Organic Engagement Rate.
- **Never** mix Paid Ad Engagements into Organic Known Engagement Actions.
- If scope is unknown or mixed, clearly label it `Scope: mixed_or_unknown` and keep it separate.

---

## 5. Deterministic Calculation Rules

Whenever Python execution is available, use the bundled calculation script:
```bash
python3 skills/social-report-audit/scripts/calculate_metrics.py input.json
```

### Core Formulas:
1. **Known Engagement Actions:**
   $$\text{Known Engagement Actions} = \text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$$
2. **Calculated ER by Reach & Incomplete Component Rule:**
   $$\text{Calculated ER by Reach} = \frac{\text{Known Engagement Actions}}{\text{Reach}} \times 100$$
   *Strict Incomplete Rule:* If any of the four engagement components (Likes, Comments, Shares, Saves) is missing, unreadable, or `--`, the calculated ER **MUST NOT** be presented as complete. Present only the sum of known actions and a clearly labeled **minimum / lower bound** (e.g. `Calculated ER Lower Bound by Reach: ≥ 7.54% (Incomplete — Shares unavailable)`). Never present an incomplete calculation as the final true ER.
   *If Reach is approximate, flag the calculated ER as approximate (e.g., `≈ 3.80%`).*
3. **Save Rate:**
   $$\text{Save Rate} = \frac{\text{Saves}}{\text{Reach}} \times 100$$
4. **Comment-to-Like Ratio:**
   $$\text{Comment-to-Like Ratio} = \frac{\text{Comments}}{\text{Likes}} \times 100$$
   *If Likes = 0, output `N/A`.*

### Discrepancy Auditing (Known Actions vs. Platform Interactions):
If Meta reports a higher composite "Interactions" total than $\text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$:
- Report both figures distinctly.
- Categorize the difference as `Uncategorized Platform Interactions` (representing sticker taps, profile visits, or link clicks).
- Never silently force the composite total into the standard four-component engagement sum.

For exhaustive metric definitions and edge cases, see [references/METRICS.md](references/METRICS.md).

---

## 6. Reach Aggregation Warning

Reach is **non-additive across distinct posts, dates, and creators**.

When aggregating Reach across multiple content pieces:
- Label the aggregated metric strictly as: **"Sum of Content-Level Reach"**.
- Always include the mandatory disclosure:
  > *Note: This represents the sum of individual content reach values and contains audience overlap. It must not be interpreted as unique campaign reach.*

---

## 7. Report Structure & Tone Standards

Reports must maintain an empirical, professional tone without unsubstantiated superlatives or speculative causality. Distinguish between:
- **FACT:** Directly observed metrics from screenshots or platform exports.
- **DERIVED METRIC:** Deterministic calculation using defined formulas.
- **INTERPRETATION:** Cautious analytical deduction supported directly by numbers.
- **RECOMMENDATION:** Concrete, testable action item for client strategy.

### Strict Factuality & Causality Rules:
1. **No Unsubstantiated Explanations:**
   - Do NOT invent or assume technical or behavioral causes not proved by the input (e.g., do NOT claim that `Shares: --` is caused by API delays, caching, sync latency, or UI glitches unless source logs explicitly state so). State only what is observed: *"Screenshot in Insights shows Shares `--`, while feed shows X shares; cause of variance is undocumented in source data."*
2. **Factuality on Zero Values (Comments = 0):**
   - Never infer from `0 comments` that comments were disabled or that audience behavior was passive. State strictly the verified fact: *"Comments: 0"*.

For complete single-creator and multi-creator Markdown report templates, refer to [references/REPORT_FORMAT.md](references/REPORT_FORMAT.md).
