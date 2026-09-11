-- 5DR V2.2 — Continuous Learning & Challenger Governance
-- Additive learning/research layer. Production forecasting methodology remains frozen.
-- Active production model remains 5DR_V2_1 and output contract remains 5DR_V2_1_2.

CREATE TABLE IF NOT EXISTS public.learning_lab_config (
  config_version TEXT PRIMARY KEY,
  architecture_version TEXT NOT NULL CHECK (architecture_version = '5DR_V2_2'),
  production_model_version TEXT NOT NULL REFERENCES public.model_versions(model_version),
  production_output_contract_version TEXT NOT NULL,
  autonomous_learning_allowed BOOLEAN NOT NULL DEFAULT TRUE CHECK (autonomous_learning_allowed),
  autonomous_production_mutation_allowed BOOLEAN NOT NULL DEFAULT FALSE CHECK (NOT autonomous_production_mutation_allowed),
  promotion_requires_user_approval BOOLEAN NOT NULL DEFAULT TRUE CHECK (promotion_requires_user_approval),
  hypothesis_min_supporting_observations INTEGER NOT NULL CHECK (hypothesis_min_supporting_observations >= 1),
  hypothesis_min_support_ratio NUMERIC NOT NULL CHECK (hypothesis_min_support_ratio > 0 AND hypothesis_min_support_ratio <= 1),
  promotion_min_backtest_target_dates INTEGER NOT NULL CHECK (promotion_min_backtest_target_dates >= 1),
  promotion_min_scoped_backtest_target_dates INTEGER NOT NULL CHECK (promotion_min_scoped_backtest_target_dates >= 1),
  promotion_min_shadow_target_dates INTEGER NOT NULL CHECK (promotion_min_shadow_target_dates >= 1),
  promotion_min_scoped_shadow_target_dates INTEGER NOT NULL CHECK (promotion_min_scoped_shadow_target_dates >= 1),
  promotion_min_directional_improvement_pp NUMERIC NOT NULL CHECK (promotion_min_directional_improvement_pp >= 0),
  promotion_min_brier_relative_improvement NUMERIC NOT NULL CHECK (promotion_min_brier_relative_improvement >= 0),
  promotion_max_primary_horizon_deterioration_pp NUMERIC NOT NULL CHECK (promotion_max_primary_horizon_deterioration_pp >= 0),
  promotion_max_hit_rate_deterioration_pp NUMERIC NOT NULL CHECK (promotion_max_hit_rate_deterioration_pp >= 0),
  promotion_max_avg_r_deterioration NUMERIC NOT NULL CHECK (promotion_max_avg_r_deterioration >= 0),
  promotion_max_drawdown_relative_deterioration NUMERIC NOT NULL CHECK (promotion_max_drawdown_relative_deterioration >= 0),
  config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO public.learning_lab_config (
  config_version,
  architecture_version,
  production_model_version,
  production_output_contract_version,
  hypothesis_min_supporting_observations,
  hypothesis_min_support_ratio,
  promotion_min_backtest_target_dates,
  promotion_min_scoped_backtest_target_dates,
  promotion_min_shadow_target_dates,
  promotion_min_scoped_shadow_target_dates,
  promotion_min_directional_improvement_pp,
  promotion_min_brier_relative_improvement,
  promotion_max_primary_horizon_deterioration_pp,
  promotion_max_hit_rate_deterioration_pp,
  promotion_max_avg_r_deterioration,
  promotion_max_drawdown_relative_deterioration,
  config_json
)
SELECT
  '5DR_V2_2_LAB_1',
  '5DR_V2_2',
  '5DR_V2_1',
  '5DR_V2_1_2',
  12,
  0.65,
  40,
  30,
  15,
  12,
  5.0,
  0.08,
  3.0,
  3.0,
  0.10,
  0.10,
  jsonb_build_object(
    'validation_method', 'CHRONOLOGICAL_WALK_FORWARD',
    'promotion_statistics', 'DAY_NORMALIZED',
    'shadow_required', true,
    'production_change', 'EXPLICIT_USER_APPROVAL_ONLY'
  )
WHERE NOT EXISTS (
  SELECT 1 FROM public.learning_lab_config WHERE config_version = '5DR_V2_2_LAB_1'
);

CREATE TABLE IF NOT EXISTS public.learning_cycles (
  cycle_id BIGSERIAL PRIMARY KEY,
  cycle_type TEXT NOT NULL CHECK (cycle_type IN ('CHECKPOINT', 'DAILY', 'WEEKLY', 'MANUAL')),
  cycle_as_of TIMESTAMPTZ NOT NULL,
  source_cutoff TIMESTAMPTZ NOT NULL,
  run_status TEXT NOT NULL CHECK (run_status IN ('COMPLETE', 'NO_NEW_DATA', 'FAILED')),
  observations_created INTEGER NOT NULL DEFAULT 0 CHECK (observations_created >= 0),
  hypotheses_created INTEGER NOT NULL DEFAULT 0 CHECK (hypotheses_created >= 0),
  challengers_created INTEGER NOT NULL DEFAULT 0 CHECK (challengers_created >= 0),
  challengers_rejected INTEGER NOT NULL DEFAULT 0 CHECK (challengers_rejected >= 0),
  promotion_candidates_created INTEGER NOT NULL DEFAULT 0 CHECK (promotion_candidates_created >= 0),
  summary JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.learning_observations (
  observation_id BIGSERIAL PRIMARY KEY,
  cycle_id BIGINT NOT NULL REFERENCES public.learning_cycles(cycle_id),
  forecast_id TEXT REFERENCES public.forecasts(forecast_id),
  checkpoint_evaluation_id BIGINT REFERENCES public.forecast_checkpoint_evaluations(evaluation_id),
  recommendation_event_id BIGINT REFERENCES public.recommendation_events(event_id),
  horizon TEXT CHECK (horizon IS NULL OR horizon IN ('D+1','D+2','D+3','D+4','D+5','TRADE','GLOBAL')),
  regime TEXT CHECK (regime IS NULL OR regime IN ('TREND','RANGE','TRANSITION','EVENT_SHOCK')),
  dimension TEXT NOT NULL CHECK (dimension IN (
    'PRICE_STRUCTURE','PVPO','PARTICIPATION','MACRO_CATALYSTS','PROBABILITY_CALIBRATION',
    'MARKET_TRUST','REGIME','EXECUTION_EDGE','STRIKE_EXPIRY','ENTRY_STOP_TARGET',
    'EVENT_SHOCK','CROSS_ENGINE_INTERACTION','NO_TRADE'
  )),
  observation_type TEXT NOT NULL CHECK (observation_type IN ('SUCCESS','ERROR','CALIBRATION','PATTERN','INCONCLUSIVE')),
  outcome_classification TEXT NOT NULL,
  impact_score NUMERIC CHECK (impact_score IS NULL OR (impact_score >= -100 AND impact_score <= 100)),
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
  diagnosis TEXT NOT NULL,
  confidence NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (checkpoint_evaluation_id IS NOT NULL OR recommendation_event_id IS NOT NULL OR forecast_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_learning_observations_forecast
  ON public.learning_observations(forecast_id, horizon, dimension, created_at);
CREATE INDEX IF NOT EXISTS idx_learning_observations_regime
  ON public.learning_observations(regime, dimension, observation_type, created_at);

CREATE TABLE IF NOT EXISTS public.learning_hypotheses (
  hypothesis_id BIGSERIAL PRIMARY KEY,
  hypothesis_code TEXT NOT NULL UNIQUE,
  created_in_cycle_id BIGINT NOT NULL REFERENCES public.learning_cycles(cycle_id),
  statement TEXT NOT NULL,
  scope JSONB NOT NULL DEFAULT '{}'::jsonb,
  affected_metrics JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(affected_metrics) = 'array'),
  proposed_change JSONB NOT NULL,
  falsification_test JSONB NOT NULL,
  supporting_observation_ids JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(supporting_observation_ids) = 'array'),
  opposing_observation_ids JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(opposing_observation_ids) = 'array'),
  support_ratio NUMERIC CHECK (support_ratio IS NULL OR (support_ratio >= 0 AND support_ratio <= 1)),
  confidence NUMERIC NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.challenger_models (
  challenger_id BIGSERIAL PRIMARY KEY,
  challenger_code TEXT NOT NULL UNIQUE,
  hypothesis_id BIGINT REFERENCES public.learning_hypotheses(hypothesis_id),
  created_in_cycle_id BIGINT NOT NULL REFERENCES public.learning_cycles(cycle_id),
  base_model_version TEXT NOT NULL REFERENCES public.model_versions(model_version),
  scope JSONB NOT NULL DEFAULT '{}'::jsonb,
  change_specification JSONB NOT NULL,
  declared_differences JSONB NOT NULL,
  creation_reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.learning_lifecycle_events (
  lifecycle_event_id BIGSERIAL PRIMARY KEY,
  entity_type TEXT NOT NULL CHECK (entity_type IN ('HYPOTHESIS','CHALLENGER')),
  entity_id BIGINT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN (
    'PROPOSED','TESTING','BACKTEST_PASSED','BACKTEST_FAILED','SHADOW_STARTED',
    'SHADOW_PASSED','SHADOW_FAILED','PROMOTION_CANDIDATE','REJECTED','RETIRED'
  )),
  cycle_id BIGINT REFERENCES public.learning_cycles(cycle_id),
  reason TEXT,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_lifecycle_entity
  ON public.learning_lifecycle_events(entity_type, entity_id, created_at DESC, lifecycle_event_id DESC);

CREATE TABLE IF NOT EXISTS public.challenger_predictions (
  challenger_prediction_id BIGSERIAL PRIMARY KEY,
  challenger_id BIGINT NOT NULL REFERENCES public.challenger_models(challenger_id),
  base_forecast_id TEXT NOT NULL REFERENCES public.forecasts(forecast_id),
  issued_at TIMESTAMPTZ NOT NULL,
  target_trading_date DATE,
  prediction_mode TEXT NOT NULL CHECK (prediction_mode IN ('BACKTEST','OUT_OF_SAMPLE','SHADOW')),
  forecast_payload JSONB NOT NULL,
  recommendation_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  evidence_cutoff TIMESTAMPTZ NOT NULL,
  anti_leakage_passed BOOLEAN NOT NULL CHECK (anti_leakage_passed),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (challenger_id, base_forecast_id, prediction_mode)
);

CREATE TABLE IF NOT EXISTS public.challenger_evaluations (
  challenger_evaluation_id BIGSERIAL PRIMARY KEY,
  challenger_id BIGINT NOT NULL REFERENCES public.challenger_models(challenger_id),
  cycle_id BIGINT NOT NULL REFERENCES public.learning_cycles(cycle_id),
  evaluation_type TEXT NOT NULL CHECK (evaluation_type IN ('BACKTEST','OUT_OF_SAMPLE','SHADOW')),
  period_start DATE,
  period_end DATE,
  target_date_count INTEGER NOT NULL CHECK (target_date_count >= 0),
  forecast_count INTEGER NOT NULL CHECK (forecast_count >= 0),
  regime_mix JSONB NOT NULL DEFAULT '{}'::jsonb,
  baseline_metrics JSONB NOT NULL,
  challenger_metrics JSONB NOT NULL,
  metric_deltas JSONB NOT NULL,
  data_quality_status TEXT NOT NULL CHECK (data_quality_status IN ('PASS','WARN','FAIL')),
  anti_leakage_status TEXT NOT NULL CHECK (anti_leakage_status IN ('PASS','FAIL')),
  verdict TEXT NOT NULL CHECK (verdict IN ('PASS','FAIL','INSUFFICIENT_DATA')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_challenger_evaluations_latest
  ON public.challenger_evaluations(challenger_id, evaluation_type, created_at DESC, challenger_evaluation_id DESC);

CREATE TABLE IF NOT EXISTS public.promotion_proposals (
  promotion_proposal_id BIGSERIAL PRIMARY KEY,
  challenger_id BIGINT NOT NULL REFERENCES public.challenger_models(challenger_id),
  created_in_cycle_id BIGINT NOT NULL REFERENCES public.learning_cycles(cycle_id),
  proposed_model_version TEXT NOT NULL,
  eligibility_checks JSONB NOT NULL,
  baseline_vs_challenger JSONB NOT NULL,
  sample_breakdown JSONB NOT NULL,
  known_weaknesses JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(known_weaknesses) = 'array'),
  rollback_plan JSONB NOT NULL,
  implementation_plan JSONB NOT NULL,
  proposal_status TEXT NOT NULL DEFAULT 'PENDING_USER_APPROVAL' CHECK (proposal_status = 'PENDING_USER_APPROVAL'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.promotion_decisions (
  promotion_decision_id BIGSERIAL PRIMARY KEY,
  promotion_proposal_id BIGINT NOT NULL REFERENCES public.promotion_proposals(promotion_proposal_id),
  decision TEXT NOT NULL CHECK (decision IN ('APPROVE','REJECT','CONTINUE_TESTING')),
  decided_by TEXT NOT NULL DEFAULT 'USER' CHECK (decided_by = 'USER'),
  decision_reason TEXT,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.learning_reports (
  learning_report_id BIGSERIAL PRIMARY KEY,
  cycle_id BIGINT NOT NULL REFERENCES public.learning_cycles(cycle_id),
  report_type TEXT NOT NULL CHECK (report_type IN ('DAILY','WEEKLY','PROMOTION_ALERT','INTEGRITY_ALERT','AD_HOC')),
  period_start DATE,
  period_end DATE,
  what_worked JSONB NOT NULL DEFAULT '[]'::jsonb,
  what_failed JSONB NOT NULL DEFAULT '[]'::jsonb,
  patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
  challenger_scoreboard JSONB NOT NULL DEFAULT '[]'::jsonb,
  production_modification_recommended BOOLEAN NOT NULL DEFAULT FALSE,
  promotion_proposal_id BIGINT REFERENCES public.promotion_proposals(promotion_proposal_id),
  summary TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (NOT production_modification_recommended OR promotion_proposal_id IS NOT NULL)
);

-- Immutable learning evidence/audit records. New facts are appended; old facts are never rewritten.
CREATE OR REPLACE RULE no_update_learning_cycles AS
ON UPDATE TO public.learning_cycles DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_learning_cycles AS
ON DELETE TO public.learning_cycles DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_learning_observations AS
ON UPDATE TO public.learning_observations DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_learning_observations AS
ON DELETE TO public.learning_observations DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_learning_hypotheses AS
ON UPDATE TO public.learning_hypotheses DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_learning_hypotheses AS
ON DELETE TO public.learning_hypotheses DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_challenger_models AS
ON UPDATE TO public.challenger_models DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_challenger_models AS
ON DELETE TO public.challenger_models DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_learning_lifecycle_events AS
ON UPDATE TO public.learning_lifecycle_events DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_learning_lifecycle_events AS
ON DELETE TO public.learning_lifecycle_events DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_challenger_predictions AS
ON UPDATE TO public.challenger_predictions DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_challenger_predictions AS
ON DELETE TO public.challenger_predictions DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_challenger_evaluations AS
ON UPDATE TO public.challenger_evaluations DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_challenger_evaluations AS
ON DELETE TO public.challenger_evaluations DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_promotion_proposals AS
ON UPDATE TO public.promotion_proposals DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_promotion_proposals AS
ON DELETE TO public.promotion_proposals DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_promotion_decisions AS
ON UPDATE TO public.promotion_decisions DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_promotion_decisions AS
ON DELETE TO public.promotion_decisions DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_learning_reports AS
ON UPDATE TO public.learning_reports DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_learning_reports AS
ON DELETE TO public.learning_reports DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_update_learning_lab_config AS
ON UPDATE TO public.learning_lab_config DO INSTEAD NOTHING;
CREATE OR REPLACE RULE no_delete_learning_lab_config AS
ON DELETE TO public.learning_lab_config DO INSTEAD NOTHING;

CREATE OR REPLACE VIEW public.v_learning_challenger_scoreboard AS
WITH latest_eval AS (
  SELECT DISTINCT ON (challenger_id, evaluation_type)
    challenger_id,
    evaluation_type,
    target_date_count,
    forecast_count,
    baseline_metrics,
    challenger_metrics,
    metric_deltas,
    data_quality_status,
    anti_leakage_status,
    verdict,
    created_at
  FROM public.challenger_evaluations
  ORDER BY challenger_id, evaluation_type, created_at DESC, challenger_evaluation_id DESC
), latest_event AS (
  SELECT DISTINCT ON (entity_id)
    entity_id AS challenger_id,
    event_type,
    reason,
    created_at
  FROM public.learning_lifecycle_events
  WHERE entity_type = 'CHALLENGER'
  ORDER BY entity_id, created_at DESC, lifecycle_event_id DESC
)
SELECT
  c.challenger_id,
  c.challenger_code,
  c.base_model_version,
  c.scope,
  le.event_type AS lifecycle_status,
  le.reason AS lifecycle_reason,
  e.evaluation_type,
  e.target_date_count,
  e.forecast_count,
  e.baseline_metrics,
  e.challenger_metrics,
  e.metric_deltas,
  e.data_quality_status,
  e.anti_leakage_status,
  e.verdict,
  e.created_at AS evaluation_created_at
FROM public.challenger_models c
LEFT JOIN latest_event le ON le.challenger_id = c.challenger_id
LEFT JOIN latest_eval e ON e.challenger_id = c.challenger_id;

CREATE OR REPLACE VIEW public.v_learning_promotion_queue AS
SELECT
  p.*,
  d.decision,
  d.decision_reason,
  d.decided_at
FROM public.promotion_proposals p
LEFT JOIN LATERAL (
  SELECT decision, decision_reason, decided_at
  FROM public.promotion_decisions d0
  WHERE d0.promotion_proposal_id = p.promotion_proposal_id
  ORDER BY decided_at DESC, promotion_decision_id DESC
  LIMIT 1
) d ON TRUE
WHERE d.decision IS NULL;

CREATE OR REPLACE VIEW public.v_learning_lab_status AS
SELECT
  (SELECT config_version FROM public.learning_lab_config ORDER BY created_at DESC LIMIT 1) AS config_version,
  (SELECT COUNT(*) FROM public.learning_cycles) AS learning_cycles,
  (SELECT COUNT(*) FROM public.learning_observations) AS observations,
  (SELECT COUNT(*) FROM public.learning_hypotheses) AS hypotheses,
  (SELECT COUNT(*) FROM public.challenger_models) AS challengers,
  (SELECT COUNT(*) FROM public.challenger_evaluations WHERE evaluation_type = 'SHADOW') AS shadow_evaluations,
  (SELECT COUNT(*) FROM public.v_learning_promotion_queue) AS pending_promotion_proposals,
  (SELECT MAX(created_at) FROM public.learning_cycles) AS last_learning_cycle_at;

INSERT INTO public.schema_meta(schema_version)
SELECT 6
WHERE NOT EXISTS (SELECT 1 FROM public.schema_meta WHERE schema_version = 6);

INSERT INTO public.change_log(
  model_version, schema_version, change_type, description, rationale
)
VALUES (
  '5DR_V2_1',
  6,
  'AMENDMENT',
  'V2.2 Continuous Learning & Challenger Governance: autonomous learning cycles, diagnostic observations, hypotheses, challenger definitions/predictions/evaluations, shadow testing, promotion proposals/decisions and weekly learning reports.',
  'Enable continuous autonomous learning and experimentation while preserving immutable production forecasts and requiring explicit user approval before any production implementation.'
);
