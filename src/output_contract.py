"""5DR V2.1.1 output completeness validation."""

OUTPUT_CONTRACT_VERSION = "5DR_V2_1_1"

def validate_output_contract(model_version, forecast_assessment,
                             recommendation_assessment, output_contract_version):
    """Raise ValueError when a new 5DR V2.1 release is incomplete."""
    if model_version != "5DR_V2_1":
        return True
    if output_contract_version != OUTPUT_CONTRACT_VERSION:
        raise ValueError("5DR V2.1.1 release blocked: invalid output contract version")
    if not isinstance(forecast_assessment, str) or not forecast_assessment.strip():
        raise ValueError("5DR V2.1.1 release blocked: Forecast Assessment is mandatory")
    if not isinstance(recommendation_assessment, str) or not recommendation_assessment.strip():
        raise ValueError("5DR V2.1.1 release blocked: Recommendation Assessment is mandatory")
    return True
