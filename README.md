# 5DR V2.1.2

5DR is the NIFTY-only five-day forecasting, options-decision and efficacy framework.

## Current production contract

- Model: `5DR_V2_1`
- Output contract: `5DR_V2_1_2`
- Target database schema: `5`
- Core directional methodology: unchanged from V2/V2.1
- Governance: canonical-window + immutable lineage
- Standard user output: exactly two tables, with Assessment & Efficacy first

## V2.1.2 change

Every standard `5DR` run now opens with a cumulative assessment dashboard covering:

- D+1 through D+5 directional accuracy
- zone hit rate and zone error
- directional margin in NIFTY points
- all recommendation statuses
- recommendation hit rate, standardized model P/L, open MTM and average R
- explicit `NOT DUE` / `NOT SCORABLE` treatment

The current forecast/recommendation appears second. Historical forecasts remain immutable.

See `docs/ASSESSMENT_EFFICACY_V2_1_2.md`.
