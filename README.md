# 5DR V2.1

5DR is the NIFTY-only five-day forecasting, options-decision and efficacy framework.

## Current production version

- Model: `5DR_V2_1`
- Database schema: `3`
- Core scoring: unchanged from V2
- Governance: canonical-window + immutable snapshot lineage

## Canonical window

For trading day T:
- opens 15:20 IST on the preceding NIFTY trading day
- closes 09:14:59 IST on T
- latest valid candidate becomes the Daily Canonical
- 09:15–15:19:59 runs are intraday snapshots

## Core directional engines

| Engine | Base Weight |
|---|---:|
| Price + Volume + Structure | 35% |
| PVPO / Derivatives | 30% |
| Market Participation | 15% |
| Macro + Catalysts | 20% |

Execution Edge remains independent and affects tradeability only.

## Persistence

- Google Drive: canonical specification/evidence archive
- Neon PostgreSQL: immutable forecasts, governance, outcomes and efficacy
- GitHub: code/schema/migrations/tests
- ChatGPT: operating workspace

See `docs/FORECAST_GOVERNANCE_V2_1.md`.
