-- BT100 isolated research schema.
-- This migration is intentionally NOT referenced by production 5DR migrations.
-- Apply only to a dedicated replay database/schema after separate approval.

CREATE SCHEMA IF NOT EXISTS bt100_replay;

CREATE TABLE IF NOT EXISTS bt100_replay.batches (
    batch_id text PRIMARY KEY,
    observation_class text NOT NULL CHECK (observation_class = 'REPLAY'),
    official_efficacy_eligible boolean NOT NULL CHECK (official_efficacy_eligible = false),
    model_version text NOT NULL,
    baseline_5dr_sha char(40) NOT NULL,
    canonical_spec_version text NOT NULL,
    canonical_spec_sha256 char(64) NOT NULL,
    config_sha256 char(64) NOT NULL,
    target_manifest_sha256 char(64),
    dataset_sha256 char(64),
    production_neuron_budget integer NOT NULL CHECK (production_neuron_budget = 0),
    production_writes_allowed boolean NOT NULL CHECK (production_writes_allowed = false),
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bt100_replay.sessions (
    batch_id text NOT NULL REFERENCES bt100_replay.batches(batch_id),
    target_date date NOT NULL,
    cutoff_at timestamptz NOT NULL,
    d1_date date NOT NULL,
    d2_date date NOT NULL,
    d3_date date NOT NULL,
    d4_date date NOT NULL,
    d5_date date NOT NULL,
    readiness_status text NOT NULL,
    data_quality_status text NOT NULL,
    exclusion_reason text,
    PRIMARY KEY (batch_id, target_date)
);

CREATE TABLE IF NOT EXISTS bt100_replay.evidence_manifests (
    batch_id text NOT NULL,
    target_date date NOT NULL,
    manifest_sha256 char(64) NOT NULL,
    cutoff_at timestamptz NOT NULL,
    document jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, target_date, manifest_sha256),
    FOREIGN KEY (batch_id, target_date)
      REFERENCES bt100_replay.sessions(batch_id, target_date)
);

CREATE TABLE IF NOT EXISTS bt100_replay.forecasts (
    batch_id text NOT NULL,
    target_date date NOT NULL,
    forecast_id text NOT NULL,
    evidence_manifest_sha256 char(64) NOT NULL,
    payload_sha256 char(64) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, target_date, forecast_id),
    UNIQUE (batch_id, target_date, payload_sha256),
    FOREIGN KEY (batch_id, target_date)
      REFERENCES bt100_replay.sessions(batch_id, target_date)
);

CREATE TABLE IF NOT EXISTS bt100_replay.outcomes (
    batch_id text NOT NULL,
    target_date date NOT NULL,
    horizon text NOT NULL CHECK (horizon IN ('D+1','D+2','D+3','D+4','D+5')),
    outcome_sha256 char(64) NOT NULL,
    evaluation jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, target_date, horizon, outcome_sha256),
    FOREIGN KEY (batch_id, target_date)
      REFERENCES bt100_replay.sessions(batch_id, target_date)
);

CREATE TABLE IF NOT EXISTS bt100_replay.recommendation_events (
    batch_id text NOT NULL,
    target_date date NOT NULL,
    recommendation_id text NOT NULL,
    event_type text NOT NULL,
    event_at timestamptz,
    event_sha256 char(64) NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (batch_id, target_date, recommendation_id, event_sha256),
    FOREIGN KEY (batch_id, target_date)
      REFERENCES bt100_replay.sessions(batch_id, target_date)
);

-- Append-only protection: updates/deletes are prohibited by application role.
-- Database deployment must additionally GRANT INSERT/SELECT only to the BT100 writer.
