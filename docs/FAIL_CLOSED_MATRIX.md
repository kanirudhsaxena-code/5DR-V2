# Acquisition fail-closed matrix

| Condition | Required result |
| --- | --- |
| Upstox token missing/rejected | BLOCKED; no forecast release |
| Upstox network/schema failure | BLOCKED unless an explicitly governed equivalent source exists |
| Market observation stale | BLOCKED |
| Cross-market corroboration absent | BLOCKED |
| Event primary source fails, approved fallback succeeds | DEGRADED with fallback recorded |
| All approved event sources fail | EVENT_SHOCK UNAVAILABLE; BLOCKED; never infer `no event` |
| Conflicting verified observations | BLOCKED pending reconciliation |
| Execution input provenance missing | BLOCKED |
| Complete verified evidence | Eligible for AUTONOMOUS_EVIDENCE_READY only; still requires Console normalization |

No condition in this matrix authorizes trading or bypasses the existing 5DR framework gates.
