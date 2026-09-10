-- 5DR V2.1.2 — Assessment-First Efficacy & Performance Control
-- Additive outcome/accounting layer. Core 5DR methodology is unchanged.

ALTER TABLE public.forecasts
  DROP CONSTRAINT IF EXISTS forecasts_output_contract_version_check;

ALTER TABLE public.forecasts
  ADD CONSTRAINT forecasts_output_contract_version_check
  CHECK (
    output_contract_version IS NULL
    OR output_contract_version IN ('5DR_V2_1_1', '5DR_V2_1_2')
  );

ALTER TABLE public.production_config
  ADD COLUMN IF NOT EXISTS active_output_contract_version TEXT NOT NULL
  DEFAULT '5DR_V2_1_2';

UPDATE public.production_config
SET active_output_contract_version = '5DR_V2_1_2',
    updated_at = now();

CREATE TABLE IF NOT EXISTS public.forecast_checkpoint_evaluations (
  evaluation_id BIGSERIAL PRIMARY KEY,
  forecast_id TEXT NOT NULL REFERENCES public.forecasts(forecast_id),
  day_number INTEGER NOT NULL CHECK (day_number BETWEEN 1 AND 5),
  trading_date DATE NOT NULL,
  evaluation_status TEXT NOT NULL CHECK (evaluation_status IN ('SCORABLE', 'NOT_SCORABLE')),
  actual_close NUMERIC,
  reference_spot NUMERIC,
  bias TEXT NOT NULL CHECK (bias IN ('BULLISH', 'RANGE', 'BEARISH')),
  directional_hit BOOLEAN,
  directional_margin_points NUMERIC,
  zone_hit BOOLEAN,
  zone_error_points NUMERIC CHECK (zone_error_points IS NULL OR zone_error_points >= 0),
  probability NUMERIC CHECK (probability IS NULL OR (probability >= 0 AND probability <= 100)),
  brier_score NUMERIC CHECK (brier_score IS NULL OR brier_score >= 0),
  source_ref TEXT,
  supersedes_evaluation_id BIGINT REFERENCES public.forecast_checkpoint_evaluations(evaluation_id),
  notes TEXT,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    evaluation_status = 'NOT_SCORABLE'
    OR (actual_close IS NOT NULL AND reference_spot IS NOT NULL
        AND directional_hit IS NOT NULL AND directional_margin_points IS NOT NULL
        AND zone_hit IS NOT NULL AND zone_error_points IS NOT NULL)
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_forecast_checkpoint_one_superseder
  ON public.forecast_checkpoint_evaluations(supersedes_evaluation_id)
  WHERE supersedes_evaluation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_forecast_checkpoint_eval_lookup
  ON public.forecast_checkpoint_evaluations(forecast_id, day_number, evaluated_at DESC, evaluation_id DESC);

CREATE TABLE IF NOT EXISTS public.recommendation_events (
  event_id BIGSERIAL PRIMARY KEY,
  forecast_id TEXT NOT NULL REFERENCES public.forecasts(forecast_id),
  event_type TEXT NOT NULL CHECK (event_type IN (
    'ISSUED', 'ENTRY_TRIGGERED', 'MARK', 'T1_HIT', 'T2_HIT',
    'SL_HIT', 'TIME_EXIT', 'NOT_SCORABLE', 'NO_TRADE_ASSESSED'
  )),
  event_timestamp TIMESTAMPTZ NOT NULL,
  premium NUMERIC,
  pnl_pct NUMERIC,
  r_multiple NUMERIC,
  source_ref TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recommendation_events_timeline
  ON public.recommendation_events(forecast_id, event_timestamp, event_id);

CREATE TABLE IF NOT EXISTS public.assessment_snapshots (
  assessment_snapshot_id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES public.runs(run_id),
  forecast_id TEXT NOT NULL UNIQUE REFERENCES public.forecasts(forecast_id),
  output_contract_version TEXT NOT NULL CHECK (output_contract_version = '5DR_V2_1_2'),
  assessment_as_of TIMESTAMPTZ NOT NULL,
  reconciled_through TIMESTAMPTZ NOT NULL,
  overall_forecast_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  day_metrics JSONB NOT NULL,
  recommendation_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  recommendation_ledger JSONB NOT NULL,
  all_recommendations_count INTEGER NOT NULL CHECK (all_recommendations_count >= 0),
  no_trade_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  completeness_status TEXT NOT NULL DEFAULT 'COMPLETE' CHECK (completeness_status = 'COMPLETE'),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (jsonb_typeof(day_metrics) = 'object'),
  CHECK (day_metrics ?& ARRAY['D+1','D+2','D+3','D+4','D+5']),
  CHECK (jsonb_typeof(recommendation_ledger) = 'array'),
  CHECK (jsonb_array_length(recommendation_ledger) = all_recommendations_count)
);

CREATE OR REPLACE RULE no_update_forecast_checkpoint_evaluations AS
ON UPDATE TO public.forecast_checkpoint_evaluations
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE no_delete_forecast_checkpoint_evaluations AS
ON DELETE TO public.forecast_checkpoint_evaluations
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE no_update_recommendation_events AS
ON UPDATE TO public.recommendation_events
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE no_delete_recommendation_events AS
ON DELETE TO public.recommendation_events
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE no_update_assessment_snapshots AS
ON UPDATE TO public.assessment_snapshots
DO INSTEAD NOTHING;

CREATE OR REPLACE RULE no_delete_assessment_snapshots AS
ON DELETE TO public.assessment_snapshots
DO INSTEAD NOTHING;

CREATE OR REPLACE VIEW public.v_latest_forecast_checkpoint_evaluation AS
SELECT DISTINCT ON (forecast_id, day_number)
  evaluation_id,
  forecast_id,
  day_number,
  trading_date,
  evaluation_status,
  actual_close,
  reference_spot,
  bias,
  directional_hit,
  directional_margin_points,
  zone_hit,
  zone_error_points,
  probability,
  brier_score,
  source_ref,
  supersedes_evaluation_id,
  notes,
  evaluated_at
FROM public.forecast_checkpoint_evaluations
ORDER BY forecast_id, day_number, evaluated_at DESC, evaluation_id DESC;

CREATE OR REPLACE VIEW public.v_forecast_horizon_efficacy AS
SELECT
  day_number,
  COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE') AS scorable_count,
  COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND directional_hit) AS directional_hits,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND directional_hit)
    / NULLIF(COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE'), 0), 2
  ) AS directional_accuracy_pct,
  COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND zone_hit) AS zone_hits,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND zone_hit)
    / NULLIF(COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE'), 0), 2
  ) AS zone_hit_rate_pct,
  ROUND(AVG(directional_margin_points) FILTER (WHERE evaluation_status = 'SCORABLE'), 2)
    AS avg_directional_margin_points,
  ROUND(AVG(zone_error_points) FILTER (WHERE evaluation_status = 'SCORABLE'), 2)
    AS avg_zone_error_points,
  ROUND(AVG(brier_score) FILTER (WHERE evaluation_status = 'SCORABLE' AND brier_score IS NOT NULL), 4)
    AS avg_brier_score
FROM public.v_latest_forecast_checkpoint_evaluation
GROUP BY day_number
ORDER BY day_number;

DROP VIEW IF EXISTS public.v_forecast_output_completeness;
CREATE VIEW public.v_forecast_output_completeness AS
SELECT
  f.forecast_id,
  f.model_version,
  f.output_contract_version,
  CASE
    WHEN f.model_version <> '5DR_V2_1' THEN 'NOT_APPLICABLE'
    WHEN f.output_contract_version = '5DR_V2_1_1'
      AND NULLIF(btrim(f.forecast_assessment), '') IS NOT NULL
      AND NULLIF(btrim(f.recommendation_assessment), '') IS NOT NULL
      THEN 'COMPLETE'
    WHEN f.output_contract_version = '5DR_V2_1_2'
      AND NULLIF(btrim(f.forecast_assessment), '') IS NOT NULL
      AND NULLIF(btrim(f.recommendation_assessment), '') IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.assessment_snapshots a
        WHERE a.forecast_id = f.forecast_id
          AND a.output_contract_version = '5DR_V2_1_2'
          AND a.completeness_status = 'COMPLETE'
      )
      THEN 'COMPLETE'
    ELSE 'INCOMPLETE'
  END AS completeness_status
FROM public.forecasts f;

INSERT INTO public.schema_meta(schema_version)
SELECT 5
WHERE NOT EXISTS (SELECT 1 FROM public.schema_meta WHERE schema_version = 5);

INSERT INTO public.change_log(
  model_version, schema_version, change_type, description, rationale
)
VALUES (
  '5DR_V2_1',
  5,
  'AMENDMENT',
  'V2.1.2 Assessment-First Efficacy & Performance Control: checkpoint evaluations, recommendation events, immutable assessment snapshots, active output contract and assessment-first completeness gate.',
  'Make every 5DR run self-auditing across D+1 through D+5 and all recommendations while preserving the frozen forecasting methodology and immutable historical forecasts.'
);
