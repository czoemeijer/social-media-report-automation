Extract metrics for exactly one reconstructed asset using only its selected screenshots and the
provided grouping context. Return structured data only.

- Preserve exact visible numbers exactly.
- Convert abbreviations such as `1.2k` to a numeric value with `precision=approximate` and retain
  the visible token in `evidence_text`.
- Use `value=null, precision=missing` when a metric is absent.
- Use `value=null, precision=unreadable` when present but unreadable.
- A visible zero is `value=0, precision=exact`; absence is never zero.
- Preserve source filename, evidence text, confidence, and extraction method for each metric.
- A Meta ads disclaimer without a separate breakdown means `scope=mixed_or_unknown`.
- Never calculate engagement rates, Story drop-off, totals, or discrepancies.
- If evidence conflicts or confidence is below 0.75, use `review_status=needs_review`.
