# 5DR V2 Database Schema

Canonical production database: Neon PostgreSQL database `five_dr`.

Schema v1 contains: schema_meta, model_versions, runs, forecasts, component_scores, controls, daily_forecasts, execution_plans, evidence_items, forecast_evidence, pvpo_zones, evidence_delta, outcome_checkpoints, efficacy_results, change_log.

Issued forecasts and issuance-time scoring/control records are immutable.
