# 5DR acquisition state machine

`SCREENSHOTS_READY` is produced by EDGE Console only after both routine user evidence families are staged.

The autonomous runner then performs:

1. authenticated read-only Upstox acquisition;
2. Market Trust cross-market corroboration;
3. controlled event/shock source-registry verification;
4. execution-risk input provenance derivation;
5. freshness/conflict/completeness assessment.

Only a complete, verifiable envelope may become `AUTONOMOUS_EVIDENCE_READY`. Missing, stale, unavailable or conflicting critical evidence becomes `AUTONOMOUS_EVIDENCE_BLOCKED`.

`AUTONOMOUS_EVIDENCE_READY` still does not publish a forecast. EDGE Console must persist the envelope, normalize governed market inputs and reach `NORMALIZED_READY` before the existing 5DR execution packet can be released.

During shadow validation both `trading_enabled` and `forecast_release_enabled` remain false.
