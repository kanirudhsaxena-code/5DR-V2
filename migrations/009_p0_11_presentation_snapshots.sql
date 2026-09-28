-- P0-11 immutable 5DR presentation snapshot storage.
--
-- IMPORTANT: repository presence is NOT production activation. Validate this
-- migration on a temporary Neon branch before any production application.
-- It is additive only and does not alter 5DR scoring, forecast methodology,
-- canonical selection, efficacy populations, recommendations or trading logic.

CREATE TABLE IF NOT EXISTS public.presentation_snapshots (
  presentation_snapshot_id bigserial PRIMARY KEY,
  presentation_contract_version text NOT NULL
    CHECK (presentation_contract_version='P0_11_PRESENTATION_V1'),
  engine text NOT NULL CHECK (engine='5DR'),
  run_id bigint NOT NULL REFERENCES public.runs(run_id) ON DELETE RESTRICT,
  result_id text NOT NULL REFERENCES public.forecasts(forecast_id) ON DELETE RESTRICT,
  checkpoint_id text CHECK (checkpoint_id IS NULL),
  governance_state text NOT NULL CHECK (btrim(governance_state) <> ''),
  sections jsonb NOT NULL
    CHECK (jsonb_typeof(sections)='array' AND jsonb_array_length(sections)=2),
  source_payload_hash text NOT NULL CHECK (btrim(source_payload_hash) <> ''),
  presentation_hash text NOT NULL CHECK (presentation_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_5dr_presentation_exact_identity
ON public.presentation_snapshots(run_id,result_id);

CREATE INDEX IF NOT EXISTS idx_5dr_presentation_result
ON public.presentation_snapshots(result_id,created_at DESC);

-- A P0-11 snapshot is valid only when the exact immutable forecast belongs to
-- the supplied run. Separate foreign keys are not enough to prove that relation.
CREATE OR REPLACE FUNCTION public.validate_p0_11_5dr_presentation_identity()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
DECLARE
  forecast_run bigint;
BEGIN
  SELECT f.run_id INTO forecast_run
    FROM public.forecasts f
   WHERE f.forecast_id=NEW.result_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'P0-11 5DR presentation forecast % does not exist', NEW.result_id
      USING ERRCODE='23503';
  END IF;

  IF forecast_run <> NEW.run_id THEN
    RAISE EXCEPTION 'P0-11 5DR presentation run/forecast identity mismatch'
      USING ERRCODE='23514';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER presentation_snapshots_validate_identity
BEFORE INSERT ON public.presentation_snapshots
FOR EACH ROW EXECUTE FUNCTION public.validate_p0_11_5dr_presentation_identity();

CREATE RULE presentation_snapshots_no_update AS
ON UPDATE TO public.presentation_snapshots DO INSTEAD NOTHING;

CREATE RULE presentation_snapshots_no_delete AS
ON DELETE TO public.presentation_snapshots DO INSTEAD NOTHING;

-- No INSERT/backfill is performed by this migration. Existing canonicals remain
-- presentation-unavailable until a contemporaneous governed snapshot is written.
-- The live 5DR project currently exposes only its owner role, so no unverified
-- runtime-role grant is invented here.
