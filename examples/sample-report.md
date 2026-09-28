# Performance Audit Report: Summer Recipes Campaign (Synthetic Demo)

This report demonstrates the standardized audit output produced by `social-report-audit` using synthetic creator campaign data.

---

## 1. Campaign Summary (All Creators)

| Metric | Aggregated Value | Aggregation Scope & Notes |
| :--- | :--- | :--- |
| **Views (Total Video Plays)** | **34,800** | Sum of Reel plays and Story views |
| **Sum of Content-Level Reach** | **22,720** | **Non-unique sum of post reach (contains audience overlap)** |
| **Likes / Reactions** | **836** | Direct positive reactions |
| **Comments** | **55** | Direct post comments and story replies |
| **Shares / Reposts** | **8 (+1 unreadable)** | 8 verified shares; 1 post had unreadable shares in UI |
| **Saves (Bookmarks)** | **237** | Recipe bookmarks across Reels |
| **Weighted Calculated ER by Reach** | **5.00%** | Weighted baseline: $1,136\text{ known actions} / 22,720\text{ reach} \times 100$ |

> **Audience Overlap Disclosure:** The reach figure (22,720) represents the arithmetic sum of individual post reach values. Because individuals may have viewed multiple assets across creators, this figure must not be interpreted as unique campaign reach.

### Supplemental Metrics & Interaction Audit
- **Total Known Engagement Actions:** 1,136 (Likes + Comments + Shares + Saves)
- **Total Platform-Reported Interactions:** 1,184 (includes 48 story link/sticker taps)
- **Overall Save Rate:** 1.04%
- **Overall Comment-to-Like Ratio:** 6.58%

---

## 2. Creator Performance Breakdown

### A) Culinary Studio (`@culinary_studio_demo`)
*Outputs: 1× Instagram Reel + 1× Instagram Story.*

| Metric | Reel (Recipe) | Story (Link) | Total Creator | Audit Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Views** | 18,450 | 2,150 | **20,600** | Stable view-through velocity |
| **Reach** | ~12,000 | 1,820 | **~13,820** | Reel reach reported as approximate (`cca 12k`) |
| **Likes** | 512 | 14 | **526** | Direct reactions |
| **Comments** | 34 | 2 | **36** | 34 post comments, 2 story replies |
| **Shares** | 8 | 0 | **8** | Reel reposts |
| **Saves** | 95 | – | **95** | High recipe bookmarking |
| **Calculated ER by Reach** | **≈ 5.41%** | **0.88%** | **≈ 4.81%** | Flagged approximate due to approximate Reel reach |

**Interaction Composition:**
- Known Engagement Actions: 649 (Reel) + 16 (Story) = 665
- Platform-Reported Interactions: 649 (Reel) + 64 (Story) = 713
- Uncategorized Platform Actions: 48 (Story sticker taps on product link)

---

### B) Modern Baker (`@modern_baker_demo`)
*Outputs: 1× Instagram Reel.*

| Metric | Reel (Dessert Tutorial) | Audit Notes |
| :--- | :--- | :--- |
| **Views** | 14,200 | Organic video plays |
| **Reach** | 8,900 | Exact account reach |
| **Likes** | 310 | Positive reactions |
| **Comments** | 19 | Post discussions |
| **Shares** | *Unreadable / Cropped* | UI displayed `--`; recorded as null without guessing |
| **Saves** | 142 | Exceptional save rate (**1.60%**) |
| **Calculated ER by Reach** | **5.29%** | Based on known visible components (310 + 19 + 142 = 471) |

**Audit Observation:**
- Save Rate (1.60%) is more than double the campaign average (0.79%), indicating high reference value for baking instructions despite lower comment volume.

---

## 3. Objective Findings & Strategic Recommendations

1. **High Save Rates Correlate with Specific Ingredient Formats:** Modern Baker achieved 142 saves from 8,900 reach (1.60%), outperforming the wider campaign in reference value. Content featuring numbered steps and clear measurements drove bookmarking.
2. **Story Formats Drive Outbound Actions Over Feed Engagement:** The Story from Culinary Studio generated 48 link clicks from 1,820 accounts (2.64% click rate), confirming Stories are best suited for outbound traffic rather than comment generation.
3. **Ensure Full Capture of Metrics in Post Deliverables:** Modern Baker's screenshot truncated the shares metric. Future creator agreements should specify full-screen or native dashboard exports to eliminate unreadable data points.
