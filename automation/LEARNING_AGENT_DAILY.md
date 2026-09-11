# 5DR Learning Lab — Daily Autonomous Cycle

Run after the Indian market close on trading days.

1. Read production config and latest Learning Lab config.
2. Reconcile all forecast checkpoints/recommendation terminal events newly scorable since the last completed learning cycle.
3. Never edit a production forecast or historical learning artifact.
4. For each new scorable outcome, append one or more learning observations covering direction, zone, probability calibration, engine attribution, regime, Market Trust and execution where evidence supports it.
5. Mark attribution `INCONCLUSIVE` if causality cannot be supported.
6. Update hypothesis support/opposition by appending new records/events; do not rewrite old evidence.
7. Evaluate active challengers using the same eligible cases and day-normalized statistics.
8. Append shadow results for eligible challengers. Shadow outputs must never influence the live 5DR recommendation.
9. Auto-reject challengers that clearly fail benchmark/anti-leakage/data-quality requirements.
10. Create a promotion proposal only if the frozen V2.2 Promotion Eligibility Gate passes in full. Proposal status must be `PENDING_USER_APPROVAL`.
11. Never modify `production_config`, model weights, output contract, canonical governance or live execution rules.
12. Append a completed learning-cycle record and a concise daily machine-readable report. Do not notify the user unless there is a material integrity failure or a genuine promotion candidate.
