# 5DR V2.2.2

5DR is the NIFTY-only five-day forecasting, options-decision, efficacy and governed-learning framework.

## Current production contract

- Production model: `5DR_V2_1`
- Output contract: `5DR_V2_1_2`
- Core directional methodology: unchanged / frozen
- Governance: canonical-window + immutable lineage
- Standard user output: exactly two tables, with Assessment & Efficacy first
- Learning Lab: V2.2 architecture, production-promotion approval gated
- Drive evidence ingestion: V2.2.1 protocol
- Recommendation lifecycle: V2.2.2 definitive-call efficacy amendment

## V2.2.2 change

Every released `BUY_CE`, `BUY_PE` or `BUY_CONVEXITY` decision belongs to the recommendation efficacy ledger from issuance.

- `UNTRIGGERED` is no longer a normal current lifecycle state.
- A verified issuance premium is the standardized model-entry reference when available.
- Preferred entry bands remain execution-quality benchmarks rather than a loophole for excluding definitive calls.
- If no verified entry reference exists, use `ENTRY_NOT_VERIFIABLE` / `NOT_SCORABLE` rather than inventing a fill.
- Open recommendations are reconciled at every later 5DR run and close through T1/T2/SL/thesis/time exit events.
- Historical forecasts, execution plans, events and previously released assessment snapshots remain immutable; reconstruction is append-only.
- Standardized model P/L is not user-account P/L.

This amendment changes recommendation lifecycle/accounting only. DES5, the four directional engines, regime weights, probability mapping, Market Trust, Event Shock/Kill Switch, Execution Edge, the Single Tradeability Gate, Drive ingestion, Learning Lab challenger thresholds and the production firewall are unchanged.

See `docs/RECOMMENDATION_LIFECYCLE_V2_2_2.md` and `migrations/007_definitive_recommendation_lifecycle_v2_2_2.sql`.
