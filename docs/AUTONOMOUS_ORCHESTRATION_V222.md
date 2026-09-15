# 5DR V2.2.2 Autonomous Orchestration

## Pipeline
verified evidence -> contract validation -> lifecycle planner -> append-only event persistence -> due checkpoint capture -> efficacy eligibility -> Learning Lab observation

## Fail-closed rules
- No verified evidence: no lifecycle write.
- Contract mismatch: reject evidence.
- A lone snapshot may create a MARK but cannot prove terminal event ordering.
- Due checkpoint without verified market evidence remains DUE.
- Efficacy is eligible only for closed/scorable lifecycle paths with captured checkpoint evidence.
- NO_TRADE is assessed separately and never enters actionable hit-rate denominator.

## Governance firewall
This orchestration layer may account for outcomes. It MUST NOT change scoring weights, probability logic, gates, thresholds, recommendation semantics, historical forecasts, execution plans, or production Learning Lab configuration. Learning proposals remain approval-gated.

## Production activation gate
Scheduler and production Neon writes remain disabled until: CI passes; shadow orchestration passes against representative OPEN/CLOSED/NO_TRADE cases; database action translation is reviewed; evidence source is verified; explicit production activation approval is received.
