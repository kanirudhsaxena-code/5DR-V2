# Schema V2.1.2 additions

Target schema version: `5`.

Adds:

- `forecast_checkpoint_evaluations` — append-only D+1…D+5 evaluation records, including supersession support.
- `recommendation_events` — append-only recommendation lifecycle/mark events.
- `assessment_snapshots` — immutable per-run assessment dashboard snapshots.
- `v_latest_forecast_checkpoint_evaluation` — latest evaluation per forecast/horizon.
- `v_forecast_horizon_efficacy` — aggregate D+1…D+5 accuracy/margin/zone metrics.
- `production_config.active_output_contract_version` — current release contract.

Updates:

- `forecasts.output_contract_version` constraint to retain historical `5DR_V2_1_1` while allowing `5DR_V2_1_2`.
- `v_forecast_output_completeness` so V2.1.2 requires a persisted assessment snapshot in addition to both current-run assessments.

Historical forecast rows are not modified.
