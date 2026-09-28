# Data Model, Provenance & Source-of-Truth Hierarchy

This document defines the data provenance rules, source-of-truth hierarchy, and canonical normalized schema for the `social-report-audit` skill.

---

## 1. Source-of-Truth Hierarchy

When evaluating conflicting data points or auditing past campaign materials, the skill adheres strictly to this four-tier priority hierarchy:

```
Tier 1: Original Raw Screenshots / Native Platform CSV/JSON Exports (Highest Authority)
   ↓
Tier 2: Explicit Raw Metrics Provided Directly by User
   ↓
Tier 3: Client Campaign Deck / Native Presentation Material
   ↓
Tier 4: Derived / Generated Audit Reports (Lowest Authority — Output, Never Input)
```

### Critical Rules:
1. **Generated reports are outputs, not ground truth.** A past report must never be used to override or correct raw screenshots or native exports.
2. **Discrepancy Preservation:** If a Tier 1 or Tier 2 source contradicts a Tier 3 or Tier 4 source, preserve both values in the audit, highlight the variance, and use Tier 1 as canonical.
3. **No Silent Normalization:** Never round or modify an exact visible number (e.g., if a screenshot clearly shows `1,225`, do not convert it to `~1,100` because another card displays a rounded abbreviation).

---

## 2. Canonical Normalized Metric Schema

Every extracted data point is normalized into the following conceptual record:

| Field Name | Type | Allowed Values / Examples | Description |
| :--- | :--- | :--- | :--- |
| `metric_name` | string | `views`, `reach`, `likes`, `comments`, `shares`, `saves`, `platform_interactions` | Canonical metric identifier. |
| `value` | float / int / null | `15020`, `1225`, `null` | Extracted numeric value. Null if unreadable or absent. |
| `precision` | string | `exact`, `approximate`, `unreadable`, `missing` | Indicates confidence in value fidelity. |
| `platform` | string | `instagram`, `facebook`, `meta_business_suite`, `cross_platform` | Originating network. |
| `content_format` | string | `reel`, `story`, `carousel`, `feed_post`, `unknown` | Asset publication format. |
| `creator` | string | e.g., `creator_a`, `anonymous` | Identifier or handle of the content creator. |
| `scope` | string | `organic`, `paid`, `unknown` | Clear boundary between creator and paid ad data. |
| `source_file` | string | `screenshot_01.png`, `user_input` | Provenance trace to source file or prompt. |
| `notes` | string | e.g., `"Approximate: display showed 'cca 11,5 tis.'"` | Contextual notes on reading conditions. |

---

## 3. OCR & Screenshot Reading Safety

When extracting data from UI screenshots:

1. **Read Exact Figures Where Available:**
   - If UI displays `1,225`, record `1225` with `precision: "exact"`.
   - If UI displays `1.1 tis.` or `1.1k`, record `1100` with `precision: "approximate"`.
2. **Handle Approximations Explicitly:**
   - Tokens such as `cca`, `~`, `tis.`, `k` signify approximate figures.
   - Any secondary metric derived using an approximate figure must also be declared approximate (e.g., `ER ≈ 3.80%`).
3. **Unreadable / Cropped Metrics:**
   - If an indicator is truncated (e.g., `--` on shares, or cropped edge), do **not** guess.
   - Set `value: null`, `precision: "unreadable"`, and flag in the report: `Metrika nečitelná / useknutá na screenshotu`.
4. **Deduplication Across Tabs & Sliders:**
   - Instagram Insights splits insights into *Přehled* (Overview), *Projevený zájem* (Interactions), and *Okruh uživatelů* (Audience).
   - Verify post identity before aggregating: match thumbnail, publication date, or duration to avoid counting the same post multiple times.
