# 5DR V2.2.2 Autonomous Lifecycle & Checkpoint Worker

## Scope
Execution-layer accounting only. This worker MUST NOT alter 5DR scoring, probabilities, gates, forecast methodology, historical forecasts, execution plans, or Learning Lab promotion governance.

## Contract
1. Read `v_recommendation_lifecycle_v222` and process actionable OPEN recommendations.
2. Use only timestamped, contract-matching, verifiable option evidence.
3. Append recommendation events; never rewrite historical events.
4. Preserve event ordering. If evidence cannot establish T1-vs-SL ordering, do not infer an outcome.
5. Complete due D+1 through D+5/FINAL checkpoints only from verified market evidence.
6. Populate efficacy only after its checkpoint evidence is scorable.
7. Treat NO_TRADE separately from actionable recommendation hit-rate.
8. Be idempotent: reruns must not duplicate lifecycle events or checkpoint outcomes.
9. Actual user P/L is outside this worker unless a separately verified user-fill record exists.
10. Learning Lab may consume results but cannot promote production changes without the existing approval firewall.

## Automation target
Run on trading sessions after fresh evidence ingestion and once after close for checkpoint reconciliation. Fail closed when evidence is unavailable, stale, mismatched by strike/expiry, or path ordering is ambiguous.

## Activation gate
Shadow-test first. Production scheduling is enabled only after tests, database write-path review, evidence adapter verification, and explicit production approval.
