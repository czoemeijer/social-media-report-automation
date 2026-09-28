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
3. **Tab & Post Deduplication:**
   - Distinguish multiple tabs of the same post (e.g., *Přehled*, *Projevený zájem*, *Okruh uživatelů*) from separate posts.
   - Merge complementary metrics belonging to the same post ID/timestamp without double-counting.

---

## 4. Scope Classification: Organic vs. Paid Media

Always classify each extracted data point into its appropriate domain:

- **Organic Creator Content:** Views, Organic Reach, Likes, Comments, Shares/reposts, Saves, Creator ER.
- **Paid Media / Boosted Posts:** Paid Impressions, Paid Reach, Link Clicks, Media Spend, CPM, CPC, CTR, Ad Engagement.

*Rules:*
- **Never** use Paid Reach as the denominator for Organic Engagement Rate.
- **Never** mix Paid Ad Engagements into Organic Known Engagement Actions.
- If scope is unknown or mixed, clearly label it `Scope: Unknown / Mixed` and keep it separate.

---

## 5. Deterministic Calculation Rules

Whenever Python execution is available, use the bundled calculation script:
```bash
python3 skills/social-report-audit/scripts/calculate_metrics.py input.json
```

### Core Formulas:
1. **Known Engagement Actions:**
   $$\text{Known Engagement Actions} = \text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$$
2. **Calculated ER by Reach:**
   $$\text{Calculated ER by Reach} = \frac{\text{Known Engagement Actions}}{\text{Reach}} \times 100$$
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

Reports must maintain an empirical, professional tone without unsubstantiated superlatives. Distinguish between:
- **FACT:** Directly observed metrics from screenshots or platform exports.
- **DERIVED METRIC:** Deterministic calculation using defined formulas.
- **INTERPRETATION:** Cautious analytical deduction supported by numbers.
- **RECOMMENDATION:** Concrete, testable action item for client strategy.

For complete single-creator and multi-creator Markdown report templates, refer to [references/REPORT_FORMAT.md](references/REPORT_FORMAT.md).
