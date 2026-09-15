# EDGE Console handoff contract

The 5DR acquisition runner will hand the Console a bounded JSON envelope containing:

- `request_id`
- `status`: `AUTONOMOUS_EVIDENCE_READY` or `AUTONOMOUS_EVIDENCE_BLOCKED`
- `assessed_at`
- required system categories
- evidence items with category/status/source reference/retrieval timestamp/authority/fallback flag/bounded detail
- blocker lists for missing/unavailable/conflicting evidence
- `trading_enabled=false`
- `forecast_release_enabled=false` while shadow validation is active

The handoff must never contain an Upstox token, Cloudflare credential, raw provider response, arbitrary exception text or user screenshot bytes.

EDGE Console is responsible for persisting the envelope against the governed request and may only advance `adapter_stage` to `AUTONOMOUS_EVIDENCE_READY` after independently validating the envelope. Normalization remains a separate subsequent gate.
