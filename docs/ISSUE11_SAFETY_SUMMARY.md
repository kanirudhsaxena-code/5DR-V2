# Safety summary

- Read-only market access.
- No order API.
- No raw credentials/payloads in handoff.
- Fixed/allowlisted network destinations.
- Bounded retries/responses/diagnostics.
- Stale/missing/unavailable/conflicting critical evidence fails closed.
- Event-source failure never means no event.
- Framework files unchanged.
- Shadow release flags false.
- Console normalization remains downstream and mandatory.
