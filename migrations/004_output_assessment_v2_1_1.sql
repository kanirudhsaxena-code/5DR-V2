-- 5DR V2.1.1 — Output Assessment & Completeness Contract
ALTER TABLE public.forecasts ADD COLUMN forecast_assessment TEXT;
ALTER TABLE public.forecasts ADD COLUMN recommendation_assessment TEXT;
ALTER TABLE public.forecasts ADD COLUMN output_contract_version TEXT;

ALTER TABLE public.forecasts
  ADD CONSTRAINT forecasts_output_contract_version_check
  CHECK (output_contract_version IS NULL OR output_contract_version = '5DR_V2_1_1');

CREATE VIEW public.v_forecast_output_completeness AS
SELECT f.forecast_id,
       f.model_version,
       f.output_contract_version,
       CASE
         WHEN f.model_version <> '5DR_V2_1' THEN 'NOT_APPLICABLE'
         WHEN f.output_contract_version = '5DR_V2_1_1'
          AND NULLIF(btrim(f.forecast_assessment), '') IS NOT NULL
          AND NULLIF(btrim(f.recommendation_assessment), '') IS NOT NULL
           THEN 'COMPLETE'
         ELSE 'INCOMPLETE'
       END AS completeness_status
FROM public.forecasts AS f;

-- Schema version is advanced to 4 when this migration is applied in production.
