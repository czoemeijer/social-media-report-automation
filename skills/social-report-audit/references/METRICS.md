# Metric Definitions & Calculation Rules

This document specifies the standard metrics, mathematical definitions, scope boundaries, and aggregation rules used by the `social-report-audit` skill.

---

## 1. Core Metrics Reference

| Metric Name | Scope | Definition / Interpretation | Organic / Paid | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Views / Plays** | Content | Number of times a video (Reel) or Story started playing or was viewed. | Organic or Paid | On Instagram, Reel plays can include replay views. |
| **Impressions** | Content | Total number of times content appeared on screen. | Organic or Paid | An individual user can account for multiple impressions. Impressions $\ge$ Reach. |
| **Reach** | Content / Account | Number of unique accounts that saw the content at least once. | Organic or Paid | Unique **only** within the reported window/asset. Summing post Reach does **not** equal unique audience. |
| **Likes / Reactions** | Content | Explicit positive tap/click actions (Heart on IG, Like/Love/Care/Haha on FB). | Organic | Standard engagement action. |
| **Comments** | Content | User-submitted textual responses under a post or video. | Organic | Excludes private DMs unless explicitly scoped. |
| **Shares / Reposts** | Content | Forwarding to Stories, direct sends to users, or public reposts. | Organic | Strong signal of content recommendation value. |
| **Saves** | Content | Adding a post to personal bookmarks / saved collections. | Organic | High indicator of utility, reference value, or purchase intent. |
| **Platform-Reported Interactions** | Platform | Composite interaction figure reported by Meta / platform UI. | Organic or Paid | Often includes profile taps, sticker interactions, and link clicks beyond likes/comments/shares/saves. |
| **Link Clicks / Bio Clicks** | Content / Profile | Taps on sticker links, bio links, or outbound URLs. | Organic or Paid | Separate from in-feed engagements. |
| **Media Spend** | Campaign | Financial cost incurred for paid delivery. | Paid only | Never present in organic creator reporting. |
| **CPM** | Campaign | Cost per 1,000 impressions: $\frac{\text{Spend}}{\text{Impressions}} \times 1,000$. | Paid only | Paid efficiency metric. |
| **CPC** | Campaign | Cost per click: $\frac{\text{Spend}}{\text{Clicks}}$. | Paid only | Paid efficiency metric. |
| **CTR** | Content / Ad | Click-through rate: $\frac{\text{Clicks}}{\text{Impressions}} \times 100$. | Paid only | Ad responsiveness metric. |

---

## 2. Engagement Formulas

### A) Known Engagement Actions (Standard Deterministic Baseline)
To ensure auditability across creators and campaigns where platform reporting varies, the **known engagement actions** total is defined strictly as:

$$\text{Known Engagement Actions} = \text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$$

*Rule:* If any of these four values is missing or unreadable, the calculation must explicitly note the omission rather than substituting zero without disclosure.

### B) Calculated ER by Reach (Standard Baseline Formula)
Unless the client explicitly mandates an alternative denominator, the primary calculated engagement rate is:

$$\text{Calculated ER by Reach} = \frac{\text{Known Engagement Actions}}{\text{Reach}} \times 100$$

*Rules:*
1. Always label this metric as **"Calculated ER by Reach"** to prevent confusion with alternative formulas (e.g., ER by Impressions, ER by Followers).
2. If Reach is marked as approximate (e.g., `cca 11 500` or `~11.5k`), the resulting ER must also be flagged as **approximate** (e.g., `≈ 3.80%`).
3. If Reach is zero or missing, the result is `N/A (Reach unavailable)` — never divide by zero.

### C) Secondary Ratios
- **Save Rate (Saves / Reach):**
  $$\text{Save Rate} = \frac{\text{Saves}}{\text{Reach}} \times 100$$
  *Significance:* Evaluates long-term utility (recipes, tutorials, product guides).
- **Comment-to-Like Ratio (Comments / Likes):**
  $$\text{Comment / Like Ratio} = \frac{\text{Comments}}{\text{Likes}} \times 100$$
  *Significance:* Measures conversational depth vs. passive consumption. If Likes = 0, output `N/A`.

---

## 3. Discrepancy Auditing: Known Actions vs. Platform-Reported Interactions

Platforms (especially Meta Business Suite and Instagram Insights) frequently display a generic **"Interakce" / "Interactions"** card that exceeds the sum of Likes + Comments + Shares + Saves.

### Audit Rule:
Never silently force platform-reported interactions into the known engagement sum. Always decompose:
1. **Known Engagement Actions:** $\text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$
2. **Platform-Reported Total:** Extracted directly from platform UI.
3. **Discrepancy / Other Actions:** Difference representing profile taps, sticker taps, story replies, or link clicks:
   $$\text{Uncategorized Actions} = \text{Platform-Reported Total} - \text{Known Engagement Actions}$$

*Example:* If a post shows 176 known actions on the Reel, and 36 interactions from Stories, report:
- Reel Known Engagement Actions: `176`
- Additional Story Platform Interactions: `36`
- Combined Platform-Reported Interactions: `212` (with explicit breakdown)
- **Do not** report a flat "Likes + Comments + Shares + Saves = 212" when the actual sum of those four fields is 176.

---

## 4. Strict Separation: Organic vs. Paid Media

Organic creator metrics and paid ad performance represent fundamentally different data domains. They must **never** be merged into unified formulas:

| Domain | Valid Denominators | Valid Interaction Types | Invalid Cross-Domain Operations |
| :--- | :--- | :--- | :--- |
| **Organic Creator** | Organic Reach, Views | Likes, Comments, Shares, Saves | ❌ Never divide organic actions by paid Reach.<br>❌ Never add paid impressions to organic views without explicit distinction. |
| **Paid Media / Boosted** | Paid Impressions, Paid Reach | Link clicks, 3s video views, ad engagements | ❌ Never equate paid ad "Engagements" with organic Likes+Comments+Shares+Saves.<br>❌ Never mix ad spend into organic benchmarks. |

### Classification Rule:
If the source data does not specify whether a metric is organic or paid:
1. Mark the scope as `Scope: Unknown / Unverified`.
2. Do not combine it with confirmed organic or paid metrics.

---

## 5. Reach Aggregation & Audience Overlap

**Reach is non-additive across distinct content pieces, dates, and creators.**

- **Content-Level Reach:** Unique users who saw a single post.
- **Summed Content Reach:** The mathematical sum of Reach values across multiple posts (e.g., Post 1 Reach + Post 2 Reach).
- **Campaign Unique Reach:** De-duplicated reach across an entire campaign. This can **only** be reported if Meta Ads Manager or an official analytics export provides it directly.

### Mandatory Aggregation Label:
When reporting the sum of Reach values across multiple assets:
1. Label the row: **"Sum of Content-Level Reach"** (or *„Součet dosahů jednotlivých výstupů“*).
2. Attach the required caveat:
   > *Note: This represents the sum of individual content reach values and includes audience overlap. It must not be interpreted as unique campaign reach.*
