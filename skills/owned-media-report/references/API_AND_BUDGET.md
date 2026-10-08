# API and budget reference

The Skill reads authorized Facebook Pages, linked Instagram Professional accounts, and Meta Ad
Accounts. Instagram media and Insights are organic. Marketing API Insights are paid. The report
keeps those domains separate because their audience overlap is unknown.

Budget inputs support CSV and TSV. Recognized concepts include publication date, validity, platform,
targeting, content name, task link, campaign/category, content ID or permalink, planned spend,
boost status, plan-recorded actual spend, notes, and explicit campaign/ad set/ad IDs. Header aliases
are normalized and can be extended by callers.

Matching priority is exact Instagram permalink, exact Facebook object ID, exact ad/campaign/ad set
ID, then another exact platform content identifier. Similar titles never create an authoritative
match. Results are `matched`, `unmatched`, `ambiguous`, or `needs_review`. Reconciliation uses one
chosen Insights level (ad by default), so parent and child spend are never summed together.
