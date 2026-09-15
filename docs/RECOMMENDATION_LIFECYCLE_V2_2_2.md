# 5DR V2.2.2 — Definitive Recommendation Lifecycle

## Scope

This is an efficacy/accounting/lifecycle amendment only. It does **not** change the four directional engines, DES5, regime weights, probability mapping, Market Trust, Event Shock/Kill Switch, Execution Edge, Single Tradeability Gate, Drive evidence ingestion, Learning Lab challenger thresholds, or the production-promotion firewall.

## Definitive recommendation rule

Every released `BUY_CE`, `BUY_PE` or `BUY_CONVEXITY` decision creates a tracked recommendation at issuance. `NO_TRADE` remains a separate avoidance decision.

The original strike, expiry, observed premium when available, entry guidance, stop/invalidation, T1 and T2 are immutable issuance-time fields. Later runs assess or close the recommendation; they never rewrite the original plan.

## Standardized model entry

1. If a verified option premium is stored at issuance, that premium is the standardized model-entry reference for efficacy accounting.
2. The preferred entry band remains an execution-quality benchmark, not a gate determining whether the recommendation exists.
3. If the issuance premium is outside the preferred band, record the deviation and continue tracking the recommendation.
4. If no verified issuance premium exists, use the first later verifiable executable quote when available. Until then, classify the recommendation `ENTRY_NOT_VERIFIABLE` / `NOT_SCORABLE`.
5. `UNTRIGGERED` is not a normal V2.2.2 lifecycle state. Legacy immutable `UNTRIGGERED` labels are normalized diagnostically as entry-verification exceptions when current cumulative efficacy is reconstructed.

A standardized model entry is **not** a claim about the user's actual fill.

## Lifecycle

Normal lifecycle:

`OPEN/ACTIVE -> T1_HIT | T2_HIT | SL_HIT | THESIS_EXIT | TIME_EXIT -> CLOSED`

- T1 before SL = primary `WIN`.
- SL before T1 = primary `LOSS`.
- T2 is an additional achievement/terminal standardized outcome where the frozen evaluation policy uses it.
- Every new 5DR run reconciles all open recommendations before issuing the current run's recommendation.
- A later `NO_TRADE`, new strike/expiry, or direction change never erases an earlier call.
- If a later run explicitly invalidates the prior thesis, append `THESIS_EXIT` using the verified contemporaneous premium when available.
- Multiple recommendations for the same option contract remain distinct by forecast/recommendation ID and issuance timestamp.

## Immutability and reconstruction

Historical reconstruction is append-only. Existing forecasts, execution plans, recommendation events and released assessment snapshots are not updated or deleted.

When historical evidence proves that T1/T2/SL had been crossed by a later observation, the event may be recorded at the first verified observation timestamp. Do not invent an earlier exact touch time or event ordering when the price path is not observed.

## Learning Lab

The Learning Lab consumes the corrected terminal outcomes and execution-quality diagnostics. Entry-band deviations may become learning evidence instead of causing definitive calls to disappear from the efficacy population.

`ENTRY_NOT_VERIFIABLE` / `NOT_SCORABLE` remains a data-quality exception and never becomes a fabricated win/loss.

This amendment does not change autonomous-learning permissions or permit autonomous production implementation.