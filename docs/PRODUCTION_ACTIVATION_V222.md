# 5DR V2.2.2 Production Activation Gate

## Current state
The lifecycle worker, strict evidence adapter, idempotent persistence planner, and autonomous lifecycle orchestrator are merged and validated. This document defines the remaining production activation boundary; it does not activate production writes or scheduling.

## Preconditions
Production activation MUST remain blocked unless all are true:
1. CI on the activation PR is green.
2. Lifecycle orchestration shadow validation has passed.
3. Recommendation-event persistence is append-only and idempotent.
4. Checkpoint capture is idempotent (`DUE` -> `CAPTURED` only).
5. Evidence is timestamped, verified, and contract-matched to instrument, strike, and expiry.
6. Ambiguous snapshot evidence cannot close a lifecycle path.
7. CLOSED and NO_TRADE recommendations cannot be processed as actionable OPEN paths.
8. Efficacy requires a CLOSED scorable lifecycle plus captured checkpoint evidence.
9. Learning Lab may observe outcomes but may not change production methodology without approval.
10. An explicit production activation approval is recorded after review of the final executor/scheduler implementation.

## Production executor contract
The production executor must:
- read canonical OPEN actionable rows from `v_recommendation_lifecycle_v222`;
- ingest only verified evidence through `OptionEvidence`;
- call `plan_recommendation` and `plan_due_checkpoints` before any write;
- translate `EVENT` actions through the guarded recommendation-event insert;
- translate `CHECKPOINT` actions through the idempotent checkpoint capture statement;
- treat `MARK` as non-terminal evidence;
- treat `NO_WRITE` as a hard fail-closed decision;
- re-read lifecycle state after persistence and never manufacture event ordering;
- emit an auditable run summary containing counts, source references, failures, and no-write reasons;
- never place a broker order or enable option writing.

## Scheduler contract
The scheduler must be a separate, explicit production switch. Initial activation should use conservative cadence after fresh evidence ingestion and after market close. Concurrency must prevent overlapping lifecycle runs. A failed or stale evidence acquisition must result in no lifecycle write.

## Rollback / kill switch
Disabling the scheduler must stop future autonomous runs without deleting or rewriting historical recommendation events. Historical lineage remains immutable. Any production defect must fail closed and be corrected through a reviewed PR.

## Not activated by this document
- no production Neon write credential is consumed;
- no scheduled workflow is enabled;
- no autonomous lifecycle event is written to production;
- no model weights, probabilities, gates, thresholds, recommendation semantics, or historical forecasts are changed.
