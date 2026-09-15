# 5DR Autonomous Acquisition — Shadow Contract

This layer is execution infrastructure only. It MUST NOT change 5DR V2.1 scoring, thresholds, probabilities, gates, learning governance, or historical checkpoints.

## Routine ownership

User-owned evidence remains limited to NIFTY price/technical screenshots and options/OI screenshots while Upstox does not fully replace those visual inputs.

System-owned evidence families are MARKET_TRUST, EVENT_SHOCK, and EXECUTION_RISK.

## Provider discipline

- Upstox access is authenticated, read-only and NIFTY constrained.
- Provider responses are validated before evidence is emitted.
- Evidence references preserve source path and response digest, not credentials or raw payloads.
- EVENT_SHOCK uses an allowlisted source registry. Source failure is never treated as proof that no event exists.
- DEGRADED evidence is explicit. UNAVAILABLE/PENDING critical evidence blocks readiness.
- Stale evidence blocks readiness.
- Conflicting verified observations block readiness until reconciled.

## Release discipline

The acquisition envelope always sets `trading_enabled=false` and `forecast_release_enabled=false` during shadow validation. A successful acquisition probe does not itself authorize a forecast. Console publication remains behind autonomous-evidence, normalization and governed engine gates.
