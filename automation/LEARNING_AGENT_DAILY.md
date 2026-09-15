# 5DR Learning Lab — Daily Autonomous Cycle

Run after the Indian market close on trading days.

1. Read production config and latest Learning Lab config.
2. Reconcile all forecast checkpoints and recommendation outcomes newly scorable since the last completed learning cycle.
3. Apply the V2.2.2 definitive recommendation lifecycle: every actionable `BUY_CE`, `BUY_PE` or `BUY_CONVEXITY` call belongs to the efficacy ledger from issuance. Do not exclude a definitive call merely because a preferred entry-band path cannot later be proved.
4. Use the verified issuance premium as the standardized model-entry reference when available. Treat entry-band compliance/deviation as an execution-quality diagnostic. If no verified entry reference can be established, use `ENTRY_NOT_VERIFIABLE` / `NOT_SCORABLE` rather than fabricating a fill, win or loss.
5. Reconcile open calls through append-only `MARK`, `T1_HIT`, `T2_HIT`, `SL_HIT`, `THESIS_EXIT` or `TIME_EXIT` events. Legacy immutable `UNTRIGGERED` labels are read diagnostically as entry-verification exceptions and are not a normal current lifecycle state.
6. Never edit a production forecast, execution plan, prior recommendation event, assessment snapshot or historical learning artifact.
7. For each new scorable outcome, append one or more learning observations covering direction, zone, probability calibration, engine attribution, regime, Market Trust and execution where evidence supports it. Explicitly distinguish forecast error from execution/entry/strike/expiry error.
8. Mark attribution `INCONCLUSIVE` if causality cannot be supported.
9. Update hypothesis support/opposition by appending new records/events; do not rewrite old evidence.
10. Evaluate active challengers using the same eligible cases and day-normalized statistics.
11. Append shadow results for eligible challengers. Shadow outputs must never influence the live 5DR recommendation.
12. Auto-reject challengers that clearly fail benchmark/anti-leakage/data-quality requirements.
13. Create a promotion proposal only if the frozen V2.2 Promotion Eligibility Gate passes in full. Proposal status must be `PENDING_USER_APPROVAL`.
14. Never modify `production_config`, model weights, output contract, canonical governance or live forecasting/execution rules.
15. Append a completed learning-cycle record and a concise daily machine-readable report. Do not notify the user unless there is a material integrity failure or a genuine promotion candidate.
