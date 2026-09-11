# 5DR V2.2 — Learning Lab Branch

5DR is the NIFTY-only five-day forecasting, options-decision, efficacy and continuous-learning framework.

## Production remains unchanged

- Production model: `5DR_V2_1`
- Production output contract: `5DR_V2_1_2`
- Current production database schema: `5` until migration 006 is explicitly approved and applied
- Core directional methodology: unchanged from V2/V2.1
- Governance: canonical-window + immutable lineage
- Standard user output: exactly two tables, with Assessment & Efficacy first

## V2.2 Learning Lab

This branch adds autonomous learning and challenger governance without autonomous production implementation.

Learning flow:

`Forecast → Efficacy → Diagnosis → Hypothesis → Challenger → Backtest/OOS → Shadow → Promotion Proposal → User Approval → Separate Versioned Implementation`

The learner may autonomously diagnose outcomes, create hypotheses/challengers, test them, shadow-test them and reject weak challengers. It may **not** modify production configuration, weights, thresholds, historical forecasts, canonical rules or live execution logic.

A challenger that passes the frozen promotion gate can only create a `PENDING_USER_APPROVAL` proposal. Production implementation requires explicit user approval.

## V2.1.2 assessment baseline retained

Every standard `5DR` run continues to use:

1. `TABLE 1 — 5DR ASSESSMENT & EFFICACY`
2. `TABLE 2 — CURRENT 5DR RUN`

Historical forecasts remain immutable.

See:

- `docs/ASSESSMENT_EFFICACY_V2_1_2.md`
- `docs/LEARNING_LAB_V2_2.md`
- `docs/PROMOTION_GATE_V2_2.md`
- `migrations/006_learning_lab_v2_2.sql`
