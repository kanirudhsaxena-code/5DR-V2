-- 5DR emergency governance hotfix — forecast payload completeness / official efficacy
-- Production DB hotfix validated and applied 2026-09-22.
-- Analytical methodology is unchanged.

CREATE OR REPLACE VIEW public.v_forecast_payload_completeness AS
SELECT
  f.forecast_id,
  COUNT(d.daily_forecast_id)::integer AS persisted_day_rows,
  COUNT(*) FILTER (
    WHERE d.day_number BETWEEN 1 AND 5
      AND d.trading_date IS NOT NULL
      AND d.bias IN ('BULLISH','RANGE','BEARISH')
      AND d.probability IS NOT NULL
      AND d.zone_low IS NOT NULL
      AND d.zone_high IS NOT NULL
      AND d.zone_high >= d.zone_low
  )::integer AS complete_day_rows,
  CASE
    WHEN COUNT(d.daily_forecast_id) = 5
     AND COUNT(*) FILTER (
       WHERE d.day_number BETWEEN 1 AND 5
         AND d.trading_date IS NOT NULL
         AND d.bias IN ('BULLISH','RANGE','BEARISH')
         AND d.probability IS NOT NULL
         AND d.zone_low IS NOT NULL
         AND d.zone_high IS NOT NULL
         AND d.zone_high >= d.zone_low
     ) = 5
    THEN 'COMPLETE'
    WHEN COUNT(d.daily_forecast_id) = 0 THEN 'DATA_GAP'
    ELSE 'INCOMPLETE'
  END AS forecast_payload_status
FROM public.forecasts f
LEFT JOIN public.daily_forecasts d ON d.forecast_id = f.forecast_id
GROUP BY f.forecast_id;

CREATE OR REPLACE VIEW public.v_forecast_output_completeness AS
SELECT
  f.forecast_id,
  f.model_version,
  f.output_contract_version,
  CASE
    WHEN f.model_version <> '5DR_V2_1' THEN 'NOT_APPLICABLE'
    WHEN pc.forecast_payload_status <> 'COMPLETE' THEN 'INCOMPLETE'
    WHEN f.output_contract_version = '5DR_V2_1_1'
      AND NULLIF(btrim(f.forecast_assessment), '') IS NOT NULL
      AND NULLIF(btrim(f.recommendation_assessment), '') IS NOT NULL
      THEN 'COMPLETE'
    WHEN f.output_contract_version = '5DR_V2_1_2'
      AND NULLIF(btrim(f.forecast_assessment), '') IS NOT NULL
      AND NULLIF(btrim(f.recommendation_assessment), '') IS NOT NULL
      AND EXISTS (
        SELECT 1
        FROM public.assessment_snapshots a
        WHERE a.forecast_id = f.forecast_id
          AND a.output_contract_version = '5DR_V2_1_2'
          AND a.completeness_status = 'COMPLETE'
      )
      THEN 'COMPLETE'
    ELSE 'INCOMPLETE'
  END AS completeness_status
FROM public.forecasts f
JOIN public.v_forecast_payload_completeness pc ON pc.forecast_id = f.forecast_id;

CREATE OR REPLACE VIEW public.v_official_forecast_eligibility AS
SELECT
  c.target_trading_date,
  c.selected_forecast_id AS forecast_id,
  pc.persisted_day_rows,
  pc.complete_day_rows,
  pc.forecast_payload_status,
  COUNT(e.evaluation_id)::integer AS evaluation_rows,
  COUNT(e.evaluation_id) FILTER (WHERE e.evaluation_status = 'SCORABLE')::integer AS scorable_count,
  CASE
    WHEN pc.forecast_payload_status <> 'COMPLETE' THEN 'DATA_GAP'
    WHEN COUNT(e.evaluation_id) = 0 THEN 'PENDING'
    WHEN COUNT(e.evaluation_id) FILTER (WHERE e.evaluation_status = 'SCORABLE') = 0 THEN 'NOT_SCORABLE'
    WHEN COUNT(e.evaluation_id) FILTER (WHERE e.evaluation_status = 'SCORABLE') < 5 THEN 'PARTIAL'
    ELSE 'COMPLETE'
  END AS assessment_state,
  (pc.forecast_payload_status = 'COMPLETE') AS official_forecast_eligible
FROM public.canonical_selections c
JOIN public.v_forecast_payload_completeness pc
  ON pc.forecast_id = c.selected_forecast_id
LEFT JOIN public.v_latest_forecast_checkpoint_evaluation e
  ON e.forecast_id = c.selected_forecast_id
WHERE c.selection_status = 'SELECTED'
GROUP BY
  c.target_trading_date,
  c.selected_forecast_id,
  pc.persisted_day_rows,
  pc.complete_day_rows,
  pc.forecast_payload_status;

CREATE OR REPLACE VIEW public.v_official_forecast_checkpoint_evaluation AS
SELECT e.*
FROM public.v_latest_forecast_checkpoint_evaluation e
JOIN public.v_official_forecast_eligibility g
  ON g.forecast_id = e.forecast_id
WHERE g.official_forecast_eligible
  AND e.evaluation_status = 'SCORABLE';

CREATE OR REPLACE VIEW public.v_diagnostic_forecast_horizon_efficacy AS
SELECT
  day_number,
  COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE') AS scorable_count,
  COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND directional_hit) AS directional_hits,
  ROUND(100.0 * COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND directional_hit)
    / NULLIF(COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE'), 0), 2) AS directional_accuracy_pct,
  COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND zone_hit) AS zone_hits,
  ROUND(100.0 * COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE' AND zone_hit)
    / NULLIF(COUNT(*) FILTER (WHERE evaluation_status = 'SCORABLE'), 0), 2) AS zone_hit_rate_pct,
  ROUND(AVG(directional_margin_points) FILTER (WHERE evaluation_status = 'SCORABLE'), 2)
    AS avg_directional_margin_points,
  ROUND(AVG(zone_error_points) FILTER (WHERE evaluation_status = 'SCORABLE'), 2)
    AS avg_zone_error_points,
  ROUND(AVG(brier_score) FILTER (WHERE evaluation_status = 'SCORABLE' AND brier_score IS NOT NULL), 4)
    AS avg_brier_score
FROM public.v_latest_forecast_checkpoint_evaluation
GROUP BY day_number
ORDER BY day_number;

CREATE OR REPLACE VIEW public.v_forecast_horizon_efficacy AS
SELECT
  day_number,
  COUNT(*) AS scorable_count,
  COUNT(*) FILTER (WHERE directional_hit) AS directional_hits,
  ROUND(100.0 * COUNT(*) FILTER (WHERE directional_hit) / NULLIF(COUNT(*), 0), 2)
    AS directional_accuracy_pct,
  COUNT(*) FILTER (WHERE zone_hit) AS zone_hits,
  ROUND(100.0 * COUNT(*) FILTER (WHERE zone_hit) / NULLIF(COUNT(*), 0), 2)
    AS zone_hit_rate_pct,
  ROUND(AVG(directional_margin_points), 2) AS avg_directional_margin_points,
  ROUND(AVG(zone_error_points), 2) AS avg_zone_error_points,
  ROUND(AVG(brier_score) FILTER (WHERE brier_score IS NOT NULL), 4) AS avg_brier_score
FROM public.v_official_forecast_checkpoint_evaluation
GROUP BY day_number
ORDER BY day_number;
