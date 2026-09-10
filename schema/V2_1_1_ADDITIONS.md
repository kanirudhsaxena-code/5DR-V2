# V2.1.1 Schema Additions

Added to `forecasts`:
- `forecast_assessment TEXT`
- `recommendation_assessment TEXT`
- `output_contract_version TEXT`

Added validation view:
- `v_forecast_output_completeness`

For `5DR_V2_1`, a complete new release requires:
- output_contract_version = `5DR_V2_1_1`
- non-empty forecast_assessment
- non-empty recommendation_assessment

Legacy records remain unchanged.
