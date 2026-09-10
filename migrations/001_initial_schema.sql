-- 5DR V2 schema v1 reference
-- Canonical production schema is already applied to Neon database five_dr.
-- This repository tracks the same object model: schema_meta, model_versions, runs, forecasts, component_scores, controls, daily_forecasts, execution_plans, evidence_items, forecast_evidence, pvpo_zones, evidence_delta, outcome_checkpoints, efficacy_results, change_log.

INSERT INTO schema_meta(schema_version) VALUES (1) ON CONFLICT (schema_version) DO NOTHING;
INSERT INTO model_versions(model_version,status,freeze_date,specification_ref) VALUES ('5DR_V2','FROZEN',DATE '2026-09-09','5DR_V2_CANONICAL_SIMPLIFIED_SPECIFICATION') ON CONFLICT (model_version) DO NOTHING;
