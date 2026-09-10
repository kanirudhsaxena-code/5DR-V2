# 5DR V2.1 Forecast Governance

## Canonical window

For NIFTY trading day T, the canonical window opens at **15:20 IST on the immediately preceding NIFTY trading day** and closes at **09:14:59 IST on T**.

- Valid runs inside the window are `CANONICAL_CANDIDATE`.
- The latest valid candidate becomes `DAILY_CANONICAL` when the window closes.
- Runs from 09:15 through 15:19:59 are `INTRADAY_SNAPSHOT` and cannot replace that day's canonical forecast.
- At 15:20 the next trading day's canonical window opens.
- Weekends and exchange holidays are skipped using the NIFTY trading calendar.

## Candidate validity

The latest **valid** candidate wins. A later invalid run does not supersede an earlier valid candidate.

From 15:20 until market close, current-session charts/PVPO should be used where available. After close and before the next open, the most recent prior-session closing charts/PVPO may be carried forward because no newer exchange state exists. Overnight macro, global markets, crude, INR, rates, events and geopolitics must be refreshed.

Evidence modes:
- `LIVE_MARKET`
- `MARKET_CLOSED_CARRY_FORWARD`
- `PREOPEN_REFRESH`
- `MIXED`

## Anti-leakage

No NIFTY price action from 09:15 onward on trading day T may be used to select T's canonical forecast.

## Immutable lineage

Every forecast remains immutable. Governance and canonical selection are stored separately.

Lineage records:
- predecessor forecast
- target trading date
- DES5 delta
- Market Trust delta
- Bull/Range/Bear probability deltas
- recommendation/direction change
- Evidence Delta summary

## Efficacy hierarchy

1. Canonical Accuracy
2. Snapshot Accuracy
3. Day-Normalized Snapshot Accuracy
4. Revision Value
5. Overnight Revision Value
6. Early Recognition
7. Forecast Stability
8. Trade Efficacy

Revision Value is primarily `prior Brier - later Brier`; positive means the revision improved probability quality.

Forecast Stability Score is `max(0, 100 - 25 × directional flips)` and is diagnostic only.

## D+ checkpoint indexing

- For `DAILY_CANONICAL` assigned to trading day T, D+1 = trading day T.
- For `INTRADAY_SNAPSHOT` after 09:15 on T, D+1 = the next full NIFTY trading session.
- D+2 through D+5 skip weekends and exchange holidays.

## Backward compatibility

V2.1 does not change Price/Structure, PVPO, Participation, Macro/Catalyst scoring, DES5, Market Trust, probability logic, Event Shock/Kill Switch, Execution Edge, Single Tradeability Gate, or the standard two-table output.

The 10 Sep 2026 12:07 first production V2 forecast remains immutable and is classified as `INTRADAY_SNAPSHOT`.

Future forecasts use model version `5DR_V2_1`.
