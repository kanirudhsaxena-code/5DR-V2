# 5DR autonomous source registry

Initial event/shock registry:

| Source | Type | Priority | Role |
| --- | --- | ---: | --- |
| RBI | Official/regulatory | 1 | Monetary-policy, liquidity and regulatory-event verification |
| SEBI | Official/regulatory | 1 | Securities-market regulatory-event verification |
| NSE | Exchange | 2 | Exchange notices / market-event fallback |

Rules:
- HTTPS allowlist only; caller-provided arbitrary URLs are rejected.
- Redirects are rejected by the fetch boundary.
- Response body is bounded and hashed; evidence stores a source reference + SHA-256, not the page body.
- Failed sources remain failures. They are never translated into `no event`.
- Fallback use is explicit and makes EVENT_SHOCK evidence `DEGRADED`.
- All-source failure makes EVENT_SHOCK `UNAVAILABLE` and blocks autonomous evidence readiness.

This registry is an acquisition/governance component, not a 5DR scoring change.
