# 5DR Learning Lab — Weekly Deep Cycle

Run once after the final trading session of each week.

1. Analyse accumulated learning observations by regime, D+1/D+3/D+5, engine, Event Shock state and execution dimension.
2. Search for repeated, falsifiable patterns; do not manufacture a lesson from small samples.
3. A hypothesis may enter challenger testing only when the frozen testing threshold is met or a deterministic calibration defect exists.
4. Create bounded challenger specifications with every change declared relative to production.
5. Run chronological/walk-forward backtest and out-of-sample comparisons against the same eligible production cases.
6. Maintain day-normalized statistics so multiple snapshots from one day do not inflate evidence.
7. Advance only qualifying challengers to forward shadow mode.
8. Apply the full promotion gate. If it passes, create a `PENDING_USER_APPROVAL` promotion proposal; do not implement it.
9. Produce one Weekly Learning Report containing:
   - What Worked
   - What Failed
   - New Patterns
   - Challenger Scoreboard
   - Production Modification Recommended = YES/NO
10. If NO, state that no production change is recommended and continue learning autonomously.
