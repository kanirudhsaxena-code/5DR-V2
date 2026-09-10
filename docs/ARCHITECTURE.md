# 5DR V2 Technical Architecture

## Independence
5DR is NIFTY-only and completely independent of EDGE.

## Canonical systems
1. Google Drive — methodology specification and evidence archive.
2. Neon PostgreSQL — system of record for released forecasts and efficacy.
3. GitHub — technical implementation and version history.
4. ChatGPT — run interface and analytical workspace.

## Runtime evidence
5DR uses only fresh deep-web research, user-provided charts, and user-provided option-chain/OI/premium screenshots. No continuous live-market feed is required.

## Persistence rules
- Every released forecast is immutable.
- A later rolling run creates a new forecast and never overwrites an older one.
- D+1 through D+5 are stored separately.
- Outcomes are stored separately from issuance-time evidence.
- Efficacy is derived from immutable forecast/outcome pairs.
- Model version is attached to every forecast.

## Visible output
A standard 5DR run contains exactly two tables: 5DR Outcome and 5DR Drill-down.
