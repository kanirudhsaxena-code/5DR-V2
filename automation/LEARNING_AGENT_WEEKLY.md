# 5DR Learning Lab — Weekly Deep Cycle

Run once after the final trading session of each week.

1. Analyse accumulated learning observations by regime, D+1/D+3/D+5, engine, Event Shock state and execution dimension.
2. Use the V2.2.2 definitive recommendation ledger for trade-efficacy statistics. Every actionable recommendation is included from issuance; legacy `UNTRIGGERED` labels are treated as entry-verification exceptions, not as a normal exclusion bucket.
3. Separate directional-model performance from execution performance. Review standardized issuance entry, entry-band deviation, strike/expiry fit, MFE/MAE where verifiable, SL/T1/T2 placement, thesis/time exits and data-quality exceptions.
4. Search for repeated, falsifiable patterns; do not manufacture a lesson from small samples.
5. A hypothesis may enter challenger testing only when the frozen testing threshold is met or a deterministic calibration defect exists.
6. Create bounded challenger specifications with every change declared relative to production.
7. Run chronological/walk-forward backtest and out-of-sample comparisons against the same eligible production cases.
8. Maintain day-normalized statistics so multiple snapshots from one day do not inflate evidence.
9. Advance only qualifying challengers to forward shadow mode.
10. Apply the full promotion gate. If it passes, create a `PENDING_USER_APPROVAL` promotion proposal; do not implement it.
11. Produce one Weekly Learning Report containing:
   - What Worked
   - What Failed
   - New Patterns
   - Challenger Scoreboard
   - Recommendation Efficacy using the corrected definitive lifecycle
   - Production Modification Recommended = YES/NO
12. If NO, state that no production change is recommended and continue learning autonomously.
