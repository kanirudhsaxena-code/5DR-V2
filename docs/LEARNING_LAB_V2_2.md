# 5DR V2.2 — Continuous Learning & Challenger Governance

## Purpose

V2.2 adds an autonomous learning/research layer around the frozen 5DR production model. The learner can diagnose outcomes, generate hypotheses, create challenger models, backtest, run out-of-sample evaluation, shadow-test and reject weak challengers. It cannot modify production autonomously.

Production remains:

- model: `5DR_V2_1`
- output contract: `5DR_V2_1_2`
- core directional methodology: unchanged
- production promotion: explicit user approval only

## Closed-loop architecture

`Production 5DR -> Efficacy -> Learning observations -> Hypotheses -> Challengers -> Backtest/OOS -> Shadow -> Promotion proposal -> User approval -> separately versioned implementation`

Historical forecasts and learning artifacts are immutable. Learning is additive.

## Autonomous cadence

### Checkpoint-triggered
Whenever a D+1…D+5 checkpoint or recommendation terminal event becomes scorable:

1. reconcile outcome;
2. classify success/error/inconclusive;
3. attribute likely source without forcing causality;
4. append learning observations;
5. update evidence for existing hypotheses/challengers.

### Daily post-close

- reconcile all newly scorable data;
- create incremental observations;
- evaluate hypothesis support/opposition;
- update challenger experiments/shadow outcomes;
- auto-reject clearly inferior challengers;
- append a learning-cycle record.

### Weekly deep cycle

- analyse repeated patterns by regime/horizon/dimension;
- create falsifiable hypotheses;
- create bounded challengers when evidence allows;
- run chronological/walk-forward tests;
- update challenger scoreboard;
- create promotion proposal only if the full frozen gate passes;
- produce a Weekly Learning Report.

## Promotion gate

Promotion eligibility requires all applicable conditions:

- 40 day-normalized backtest/OOS target dates, or 30 for tightly scoped single-regime challenger;
- 15 forward shadow target dates, or 12 in intended regime for scoped challenger;
- >=5pp directional accuracy improvement OR >=8% relative Brier improvement;
- no D+1/D+3/D+5 deterioration >3pp and at least one improves >=5pp;
- if execution changes, hit rate deterioration <=3pp and average-R deterioration <=0.10R;
- relative maximum-drawdown deterioration <=10% where measurable;
- anti-leakage and data-quality checks pass;
- result not concentrated in a single day/event or inflated by repeated snapshots.

Passing the gate creates `PENDING_USER_APPROVAL`. It never changes production.

## Learning dimensions

- PRICE_STRUCTURE
- PVPO
- PARTICIPATION
- MACRO_CATALYSTS
- PROBABILITY_CALIBRATION
- MARKET_TRUST
- REGIME
- EXECUTION_EDGE
- STRIKE_EXPIRY
- ENTRY_STOP_TARGET
- EVENT_SHOCK
- CROSS_ENGINE_INTERACTION
- NO_TRADE

## Database additions

Migration `006_learning_lab_v2_2.sql` adds:

- `learning_lab_config`
- `learning_cycles`
- `learning_observations`
- `learning_hypotheses`
- `challenger_models`
- `learning_lifecycle_events`
- `challenger_predictions`
- `challenger_evaluations`
- `promotion_proposals`
- `promotion_decisions`
- `learning_reports`
- `v_learning_challenger_scoreboard`
- `v_learning_promotion_queue`
- `v_learning_lab_status`

Learning evidence/audit tables are append-only through database rules.

## Production firewall

The learner is prohibited from changing:

- `production_config`
- active model version
- production DES5 engine weights
- tradeability thresholds
- output contract
- canonical-window rules
- live execution rules
- historical production forecasts

A promotion proposal must show the exact proposed change, baseline vs challenger evidence, sample/regime/horizon breakdown, weaknesses, rollback plan and new model-version recommendation.

## User intervention

Routine learning intervention: **none**.

Only production-promotion decisions require the user:

- `APPROVE`
- `REJECT`
- `CONTINUE_TESTING`
