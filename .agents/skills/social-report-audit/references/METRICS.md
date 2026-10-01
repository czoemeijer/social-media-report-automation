# Metric Definitions & Calculation Rules

This document specifies the standard metrics, mathematical definitions, scope boundaries, and aggregation rules used by the `social-report-audit` skill.

---

## 1. Core Metrics Reference

| Metric Name | Scope | Definition / Interpretation | Organic / Paid | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Views / Plays** | Content | Number of times a video (Reel) or Story started playing or was viewed. | Organic, Paid, or Mixed | On Instagram, Reel plays can include replay views. |
| **Impressions** | Content | Total number of times content appeared on screen. | Organic, Paid, or Mixed | An individual user can account for multiple impressions. Impressions $\ge$ Reach. |
| **Reach** | Content / Account | Number of unique accounts that saw the content at least once. | Organic, Paid, or Mixed | Unique **only** within the reported window/asset. Summing post Reach does **not** equal unique audience. |
| **Likes / Reactions** | Content | Explicit positive tap/click actions (Heart on IG, Like/Love/Care/Haha on FB). | Organic / Mixed | Standard engagement action. |
| **Comments** | Content | User-submitted textual responses under a post or video. | Organic / Mixed | If Comments = 0, state only the fact. Do NOT infer disabled comments or passive consumption. |
| **Shares / Reposts (Insights)** | Content | Forwarding to Stories, direct sends to users, or public reposts reported by Insights. | Organic / Mixed | If `--`, record as unreadable/unavailable. Do NOT invent causes (e.g. API delays). |
| **Feed-Visible Shares & Reposts** | Content | Share / send and repost counts visible directly under post in feed UI. | Organic / Mixed | Kept distinct from canonical Insights Shares. Must not overwrite each other. |
| **Saves** | Content | Adding a post to personal bookmarks / saved collections. | Organic / Mixed | High indicator of utility, reference value, or purchase intent. |
| **Platform-Reported Interactions** | Platform | Composite interaction figure reported by Meta / platform UI. | Organic, Paid, or Mixed | Often includes profile taps, sticker interactions, and link clicks beyond likes/comments/shares/saves. |
| **Profile Activity (Taps / Visits / Follows)** | Profile | Actions on profile from asset. Absence on card is NOT zero — only record 0 when explicitly shown. | Organic, Paid, or Mixed | E.g., if external link taps is not shown on card, mark as unavailable/not shown. |
| **Link Clicks / Bio Clicks** | Content / Profile | Taps on sticker links, bio links, or outbound URLs. | Organic, Paid, or Mixed | Separate from in-feed engagements. |
| **Media Spend** | Campaign | Financial cost incurred for paid delivery. | Paid only | Never present in organic creator reporting. |
| **CPM** | Campaign | Cost per 1,000 impressions: $\frac{\text{Spend}}{\text{Impressions}} \times 1,000$. | Paid only | Paid efficiency metric. |
| **CPC** | Campaign | Cost per click: $\frac{\text{Spend}}{\text{Clicks}}$. | Paid only | Paid efficiency metric. |
| **CTR** | Content / Ad | Click-through rate: $\frac{\text{Clicks}}{\text{Impressions}} \times 100$. | Paid only | Ad responsiveness metric. |

---

## 2. Engagement Formulas

### A) Known Engagement Actions (Standard Deterministic Baseline)
To ensure auditability across creators and campaigns where platform reporting varies, the **known engagement actions** total is defined strictly as:

$$\text{Known Engagement Actions} = \text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$$

*Rule:* If any of these four values is missing, unreadable, or `--`, record the sum of visible components as known actions, but flag the engagement total as **incomplete**.

### B) Calculated ER by Reach & Incomplete Lower Bound Rule
Unless the client explicitly mandates an alternative denominator, the primary calculated engagement rate is:

$$\text{Calculated ER by Reach} = \frac{\text{Known Engagement Actions}}{\text{Reach}} \times 100$$

*Strict Incomplete Rule:*
- If any component of $\text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$ is missing, unreadable, or `--`, the resulting percentage **MUST NOT** be presented as a complete Calculated ER.
- Instead, it must be reported strictly as a **Known Actions Lower Bound / Minimum ER** (e.g., `Calculated ER Lower Bound: ≥ 7.54% (Incomplete — Shares unavailable)`).
- Never report an incomplete calculation as the final true ER.

*General Rules:*
1. Always label complete results as **"Calculated ER by Reach"** to prevent confusion with alternative formulas (e.g., ER by Impressions, ER by Followers).
2. If Reach is marked as approximate (e.g., `cca 11 500` or `~11.5k`), the resulting ER must also be flagged as **approximate** (e.g., `≈ 3.80%`).
3. If Reach is zero or missing, the result is `N/A (Reach unavailable)` — never divide by zero.

### C) Secondary Ratios
- **Save Rate (Saves / Reach):**
  $$\text{Save Rate} = \frac{\text{Saves}}{\text{Reach}} \times 100$$
  *Significance:* Evaluates long-term utility (recipes, tutorials, product guides).
- **Comment-to-Like Ratio (Comments / Likes):**
  $$\text{Comment / Like Ratio} = \frac{\text{Comments}}{\text{Likes}} \times 100$$
  *Significance:* Measures conversational depth vs. passive consumption. If Likes = 0, output `N/A`. Note: A value of 0% indicates only zero comments observed; do not speculate about turned off comments.

---

## 3. Discrepancy Auditing

### A) Known Actions vs. Platform-Reported Interactions
Platforms frequently display a generic **"Interakce" / "Interactions"** card that exceeds the sum of Likes + Comments + Shares + Saves.
Never silently force platform-reported interactions into the known engagement sum. Always decompose:
1. **Known Engagement Actions:** $\text{Likes} + \text{Comments} + \text{Shares} + \text{Saves}$
2. **Platform-Reported Total:** Extracted directly from platform UI.
3. **Discrepancy / Other Actions:** Difference representing profile taps, sticker taps, story replies, or link clicks:
   $$\text{Uncategorized Actions} = \text{Platform-Reported Total} - \text{Known Engagement Actions}$$

### B) Feed-Visible Shares & Reposts vs. Insights Shares
- If a post's public feed view shows share counts (paper plane) or repost counts (arrows), but Insights shows `--` or a divergent figure, **never overwrite one with the other**.
- Keep canonical Insights shares and feed-visible distribution metrics in separate fields.
- Report both figures in the audit and state that the reason for variance is undocumented in the source data.

### C) Absence vs. Zero Rule
- A metric omitted from a card (e.g., Reel Profile activity showing Follows but not External link taps) must be recorded as `unavailable / not shown` (`null`), never as `0`.
- A value of `0` requires explicit display on the card (e.g. `Business address taps: 0`).

---

## 4. Scope Classification: Organic vs. Paid Media vs. Mixed

Organic creator metrics, mixed outputs, and paid ad performance represent fundamentally different data domains:

| Domain | Valid Denominators | Valid Interaction Types | Invalid Cross-Domain Operations |
| :--- | :--- | :--- | :--- |
| **Organic Creator** | Organic Reach, Views | Likes, Comments, Shares, Saves | ❌ Never divide organic actions by paid Reach.<br>❌ Never add paid impressions to organic views without explicit distinction. |
| **Mixed / Unknown** | Mixed Reach, Mixed Views | Observed Actions | ⚠️ Mandatory disclosure: Organic and paid contribution cannot be separated without separate Ad breakdown. |
| **Paid Media / Boosted** | Paid Impressions, Paid Reach | Link clicks, 3s video views, ad engagements | ❌ Never equate paid ad "Engagements" with organic Likes+Comments+Shares+Saves.<br>❌ Never mix ad spend into organic benchmarks. |

### Ads Disclaimer Rule:
If Instagram Insights displays the disclaimer:
> *„Insights include data from your post/reel and any ads“*
and no separate `Ad` tab screenshot / breakdown is available:
1. Classify the scope strictly as **`mixed_or_unknown`**.
2. Include the mandatory statement: *"Organic and paid contributions cannot be separated without a separate Ad breakdown."*
3. Do not assume or classify the data as purely organic.

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
