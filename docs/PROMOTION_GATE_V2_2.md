# 5DR V2.2 — Promotion Gate

The Learning Lab is autonomous in learning and experimentation, not in production implementation.

## States

1. Observation
2. Hypothesis
3. Challenger
4. Backtest
5. Out-of-sample
6. Shadow
7. Promotion candidate
8. `PENDING_USER_APPROVAL`
9. User decision: `APPROVE`, `REJECT`, or `CONTINUE_TESTING`
10. Separate versioned implementation only after `APPROVE`

## Hard safeguards

- immutable historical production forecasts;
- chronological/walk-forward validation;
- day-normalized statistics;
- forward shadow testing;
- minimum sample gates;
- multi-metric comparison;
- no autonomous relaxation of promotion thresholds;
- no autonomous production change.

## Gate thresholds

See `src/learning_lab.py` and `learning_lab_config` in migration 006. The code and database thresholds are intentionally aligned.
