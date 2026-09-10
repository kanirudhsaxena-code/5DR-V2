"""5DR release-contract validation.

V2.1.1 is retained as a historical contract. New production releases use
V2.1.2 and must persist an assessment-first snapshot.
"""

LEGACY_OUTPUT_CONTRACT_VERSION = "5DR_V2_1_1"
OUTPUT_CONTRACT_VERSION = "5DR_V2_1_2"


def validate_output_contract(
    model_version,
    forecast_assessment,
    recommendation_assessment,
    output_contract_version,
    *,
    assessment_snapshot_complete=False,
    horizon_slots=None,
    recommendation_ledger_complete=False,
    historical=False,
):
    """Raise ValueError when a 5DR release is incomplete.

    `historical=True` permits validation of an already-issued V2.1.1 row under
    its original contract. It does not authorize a new V2.1.1 release.
    """
    if model_version != "5DR_V2_1":
        return True

    if historical and output_contract_version == LEGACY_OUTPUT_CONTRACT_VERSION:
        if not isinstance(forecast_assessment, str) or not forecast_assessment.strip():
            raise ValueError("Historical V2.1.1 row missing Forecast Assessment")
        if not isinstance(recommendation_assessment, str) or not recommendation_assessment.strip():
            raise ValueError("Historical V2.1.1 row missing Recommendation Assessment")
        return True

    if output_contract_version != OUTPUT_CONTRACT_VERSION:
        raise ValueError("5DR V2.1.2 release blocked: invalid output contract version")
    if not isinstance(forecast_assessment, str) or not forecast_assessment.strip():
        raise ValueError("5DR V2.1.2 release blocked: Forecast Assessment is mandatory")
    if not isinstance(recommendation_assessment, str) or not recommendation_assessment.strip():
        raise ValueError("5DR V2.1.2 release blocked: Recommendation Assessment is mandatory")
    if not assessment_snapshot_complete:
        raise ValueError("5DR V2.1.2 release blocked: assessment snapshot is mandatory")
    required = {"D+1", "D+2", "D+3", "D+4", "D+5"}
    if not isinstance(horizon_slots, dict) or not required.issubset(horizon_slots):
        raise ValueError("5DR V2.1.2 release blocked: D+1 through D+5 assessment slots are mandatory")
    if not recommendation_ledger_complete:
        raise ValueError("5DR V2.1.2 release blocked: recommendation ledger is incomplete")
    return True
