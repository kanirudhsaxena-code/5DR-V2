# 5DR V2.2.2 Screenshot + Web Evidence Bridge

## Purpose
This document fixes the production evidence boundary for the current 5DR build.

Current production evidence sources are only:
1. user-supplied screenshots/charts; and
2. deep, current, verifiable web research performed by the 5DR intelligence layer.

Upstox and other broker/data feeds are explicitly outside this activation and may be integrated later only through a separately reviewed change.

## Evidence packet contract
The intelligence layer must emit a normalized evidence packet before lifecycle planning. At minimum the packet records:
- forecast_id;
- evidence_source_type (`SCREENSHOT` or `WEB_RESEARCH`);
- source_ref;
- observed_at;
- captured_at;
- instrument;
- strike and expiry when option-contract evidence is asserted;
- observed premium when lifecycle premium evidence is asserted;
- verification status;
- freshness status;
- contract-match status;
- continuous_path boolean;
- evidence notes / provenance.

## Fail-closed rules
- Missing or unverifiable evidence never becomes inferred evidence.
- Screenshot timestamps are not invented.
- Web evidence must retain a source reference and observation/retrieval time.
- Option evidence must match instrument, strike and expiry before it can affect lifecycle state.
- A point-in-time screenshot or web quote defaults to `continuous_path=false`.
- Snapshot evidence may create a MARK but cannot manufacture ordering between target and stop events.
- Stale, mismatched or ambiguous evidence produces NO_WRITE.
- No evidence bridge may place broker orders or enable option writing.

## Lifecycle handoff
Validated contract evidence is converted to the existing `OptionEvidence` contract and passed to `plan_recommendation`. Due D+1..D+5 market evidence is passed to `plan_due_checkpoints`. Planned actions then pass through the approval-gated lifecycle executor.

The bridge does not change scoring weights, gates, thresholds, probabilities, recommendation semantics or historical forecasts.

## Persistence and audit
Each accepted evidence packet must preserve provenance sufficient to reconstruct why a lifecycle MARK/EVENT/CHECKPOINT was proposed. Recommendation events remain guarded/idempotent. Checkpoints remain DUE-to-CAPTURED only. Historical lineage is never rewritten.

## Continuous learning boundary
Captured lifecycle outcomes and D+1..D+5 checkpoints feed efficacy measurement and the Learning Lab. The Learning Lab may autonomously identify patterns, errors and candidate improvements, but no candidate changes production methodology without explicit approval.

## Operational model
Screenshot-driven intelligence runs when new screenshot evidence is supplied. Deep-web research can supplement and independently verify evidence. Lifecycle accounting may operate autonomously only on evidence packets that already satisfy this contract; infrastructure must not pretend to perform ChatGPT-style deep research where no research-capable intelligence service exists.

## Future Upstox integration
A future read-only Upstox acquisition layer may produce evidence packets under this same contract after separate validation and approval. It is not a dependency of V2.2.2 activation.