# 5DR V2.1.2 — Assessment-First Efficacy & Performance Control

## Scope

V2.1.2 changes assessment, efficacy accounting, persistence and output order only. DES5, the four directional engines, regime weights, Market Trust, the probability engine, Event Shock and the Single Tradeability Gate are unchanged.

Active model remains `5DR_V2_1`. New output contract is `5DR_V2_1_2`.

## Standard output

A standard `5DR` response contains exactly two tables:

1. `TABLE 1 — 5DR ASSESSMENT & EFFICACY` — always first.
2. `TABLE 2 — CURRENT 5DR RUN`.

Table 1 reconciles cumulative forecast and recommendation performance. Table 2 contains the current forecast, all D+1 through D+5 paths, Forecast Assessment, Recommendation Assessment, trade plan and engine diagnostics.

## Forecast scoring

For BULLISH, a directional hit occurs when checkpoint close is above the forecast reference spot. Margin = actual close minus reference spot.

For BEARISH, a directional hit occurs when checkpoint close is below the forecast reference spot. Margin = reference spot minus actual close.

For RANGE, directional hit equals zone hit. Margin is positive distance to the nearest zone edge when inside the zone and negative nearest-boundary distance when outside.

Zone hit means the actual close lies inside the stored expected zone, inclusive. Zone error is zero inside the zone, otherwise the distance to the nearest boundary.

D+1 through D+5 are scored independently. `NOT DUE` and `NOT SCORABLE` never enter denominators. Every displayed rate includes numerator and denominator.

## Forecast efficacy bundle

For each D+1 through D+5 show:

- scorable count
- directional accuracy
- zone hit rate
- average directional margin, NIFTY points
- average zone error, NIFTY points

No invented composite efficacy score is introduced in V2.1.2.

## Recommendation lifecycle

Every recommendation is tracked separately by forecast ID, including successive runs that recommend the same contract.

Actionable states are `UNTRIGGERED`, `OPEN`, `T1_HIT`, `T2_HIT`, `SL_HIT`, `TIME_EXIT`, and `NOT_SCORABLE`. `NO_TRADE` is tracked separately for avoidance efficacy.

Model entry is the observed issuance premium when it lies inside the frozen entry band, otherwise the first verifiable later premium inside the band. If entry cannot be determined, it is never guessed.

Primary recommendation hit rate uses T1-before-SL as WIN and SL-before-T1 as LOSS after entry. T2 is tracked as an additional target achievement but does not alter the primary hit-rate denominator.

Primary standardized model P/L uses one equal notional unit per recommendation and resolves at the first primary terminal event: T1, SL or TIME_EXIT. Open recommendations show MTM separately.

User P/L is never inferred.

## Recommendation efficacy bundle

Show total recommendations, actionable calls, resolved wins/losses, open, untriggered, not-scorable, hit rate, average R, realized standardized model P/L and open standardized MTM. The ledger lists every historical/current recommendation on every standard 5DR run.

## Persistence

- Forecast checkpoint evaluations are append-only outcome records separate from immutable forecasts.
- Recommendation state changes are append-only events.
- Each released 5DR run persists an immutable assessment snapshot showing exactly what Table 1 contained at that run timestamp.

Corrections, where objectively required, are appended as new evaluation records that supersede prior evaluation records; the original rows are not edited.

## Release gate

A new `5DR_V2_1` release under `5DR_V2_1_2` is blocked unless:

- Forecast Assessment is nonblank;
- Recommendation Assessment is nonblank;
- all D+1 through D+5 assessment slots are present;
- every known recommendation is represented in the ledger;
- `NOT DUE` / `NOT SCORABLE` are explicit where applicable;
- an assessment snapshot has been persisted.

Historical V2.1.1 outputs remain valid under their original contract.
