-- 5DR V2.2.2 — Definitive Recommendation Lifecycle & Efficacy Amendment
-- Additive lifecycle/accounting patch only. Core forecast methodology is unchanged.
-- Historical forecasts, execution plans, recommendation events and assessment snapshots remain immutable.

ALTER TABLE public.recommendation_events
  DROP CONSTRAINT IF EXISTS recommendation_events_event_type_check;

ALTER TABLE public.recommendation_events
  ADD CONSTRAINT recommendation_events_event_type_check
  CHECK (event_type IN (
    'ISSUED',
    'ENTRY_TRIGGERED',
    'ENTRY_REFERENCE_SET',
    'ENTRY_NOT_VERIFIABLE',
    'MARK',
    'T1_HIT',
    'T2_HIT',
    'SL_HIT',
    'THESIS_EXIT',
    'TIME_EXIT',
    'NOT_SCORABLE',
    'NO_TRADE_ASSESSED'
  ));

ALTER TABLE public.production_config
  ADD COLUMN IF NOT EXISTS recommendation_lifecycle_version TEXT NOT NULL
  DEFAULT '5DR_V2_2_2';

UPDATE public.production_config
SET recommendation_lifecycle_version = '5DR_V2_2_2',
    updated_at = now();

CREATE OR REPLACE VIEW public.v_latest_recommendation_event AS
SELECT DISTINCT ON (forecast_id)
  event_id,
  forecast_id,
  event_type,
  event_timestamp,
  premium,
  pnl_pct,
  r_multiple,
  source_ref,
  notes,
  created_at
FROM public.recommendation_events
ORDER BY forecast_id, event_timestamp DESC, event_id DESC;

CREATE OR REPLACE VIEW public.v_recommendation_lifecycle_v222 AS
WITH actionable AS (
  SELECT
    f.forecast_id,
    f.run_timestamp AS issuance_timestamp,
    f.recommendation,
    ep.instrument,
    ep.strike,
    ep.expiry,
    ep.observed_premium,
    ep.entry_low,
    ep.entry_high,
    ep.stop_premium,
    ep.target1_premium,
    ep.target2_premium
  FROM public.forecasts f
  LEFT JOIN public.execution_plans ep USING (forecast_id)
  WHERE f.recommendation IN ('BUY_CE', 'BUY_PE', 'BUY_CONVEXITY')
),
flags AS (
  SELECT
    a.*,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type IN ('ENTRY_REFERENCE_SET', 'ENTRY_TRIGGERED')
    ) AS has_entry_reference,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'ENTRY_NOT_VERIFIABLE'
    ) AS entry_not_verifiable,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'T1_HIT'
    ) AS t1_hit,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'T2_HIT'
    ) AS t2_hit,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'SL_HIT'
    ) AS sl_hit,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'THESIS_EXIT'
    ) AS thesis_exit,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'TIME_EXIT'
    ) AS time_exit,
    EXISTS (
      SELECT 1 FROM public.recommendation_events r
      WHERE r.forecast_id = a.forecast_id
        AND r.event_type = 'NOT_SCORABLE'
    ) AS not_scorable
  FROM actionable a
)
SELECT
  flags.*,
  CASE
    WHEN not_scorable THEN 'NOT_SCORABLE'
    WHEN entry_not_verifiable AND NOT has_entry_reference THEN 'ENTRY_NOT_VERIFIABLE'
    WHEN t2_hit THEN 'CLOSED_T2'
    WHEN sl_hit THEN 'CLOSED_SL'
    WHEN thesis_exit THEN 'CLOSED_THESIS_EXIT'
    WHEN time_exit THEN 'CLOSED_TIME_EXIT'
    WHEN t1_hit THEN 'OPEN_T1_HIT'
    ELSE 'OPEN'
  END AS lifecycle_status,
  CASE
    WHEN t1_hit AND NOT sl_hit THEN 'WIN'
    WHEN sl_hit AND NOT t1_hit THEN 'LOSS'
    ELSE NULL
  END AS primary_outcome
FROM flags;

INSERT INTO public.schema_meta(schema_version)
SELECT 7
WHERE NOT EXISTS (SELECT 1 FROM public.schema_meta WHERE schema_version = 7);

INSERT INTO public.change_log(
  model_version, schema_version, change_type, description, rationale
)
VALUES (
  '5DR_V2_1',
  7,
  'AMENDMENT',
  'V2.2.2 definitive recommendation lifecycle: actionable calls are tracked from issuance; standardized model-entry references are explicit; UNTRIGGERED is removed as a normal current lifecycle; thesis exits and entry-verification exceptions are append-only events.',
  'Align recommendation efficacy with the definitive 5DR decision contract while preserving historical immutability and leaving the production forecasting methodology and Learning Lab promotion firewall unchanged.'
);
