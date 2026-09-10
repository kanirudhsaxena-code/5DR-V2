# 5DR V2

5DR V2 is the frozen NIFTY-only five-day forecasting, options-decision and efficacy framework.

## Canonical architecture
- **Google Drive** — canonical frozen specification and evidence archive
- **Neon PostgreSQL** — immutable forecasts, checkpoints, outcomes and efficacy
- **GitHub** — code, schema, migrations, tests and version history
- **ChatGPT** — operating workspace only

## Core directional engines
| Engine | Base Weight |
|---|---:|
| Price + Volume + Structure | 35% |
| PVPO / Derivatives | 30% |
| Market Participation | 15% |
| Macro + Catalysts | 20% |

Execution Edge is independent and affects tradeability only.

## Control engines
- Regime
- Market Trust
- Event Shock / Kill Switch
- Execution Edge

## Final decisions
- `BUY_CE`
- `BUY_PE`
- `BUY_CONVEXITY`
- `NO_TRADE`

## Standard output
Exactly two tables:
1. 5DR Outcome
2. 5DR Drill-down

## Security
Never commit real Neon credentials, API keys, tokens, screenshots/private evidence, user data, or `.env`.

Model version: **5DR_V2**  
Schema version: **1**  
Methodology status: **FROZEN**
