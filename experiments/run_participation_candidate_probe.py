"""Live read-only proof for the non-binding Participation candidate universe."""
import json
import os

from experiments.participation_candidate import resolve_candidate
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_safe_diagnostics import diagnostic_code
from experiments.upstox_transport import CurlOpener


def run(token):
    master = PublicInstrumentCatalog().nse_instruments()
    candidate = resolve_candidate(master["records"])
    universe = {
        f"candidate_{index}": {"instrument_key": key}
        for index, key in enumerate(candidate["instrument_keys"])
    }
    client = QuantReadOnlyClient(token, universe, opener=CurlOpener())

    quote_proofs = []
    for key in candidate["instrument_keys"]:
        envelope = client.full_quotes([key])
        if envelope["validated_instrument_tokens"] != [key]:
            raise ValueError("candidate quote identity mismatch")
        quote_proofs.append({
            "instrument_key": key,
            "source_path": envelope["source_path"],
            "source_sha256": envelope["sha256"],
            "received_at": envelope["received_at"],
        })

    return {
        "status": "5DR_PARTICIPATION_CANDIDATE_LIVE_PROVEN",
        "candidate_status": candidate["status"],
        "heavyweights": candidate["heavyweights"],
        "sectors": candidate["sectors"],
        "quote_proofs": quote_proofs,
        "master_sha256": master["sha256"],
        "master_received_at": master["received_at"],
        "validated_instrument_count": len(quote_proofs),
        "screening_enabled": False,
        "activation_enabled": False,
        "methodology_changed": False,
        "screenshot_required": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "trading_enabled": False,
    }


if __name__ == "__main__":
    try:
        result = run(os.environ.get("UPSTOX_ANALYTICS_TOKEN", ""))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if result["status"] != "5DR_PARTICIPATION_CANDIDATE_LIVE_PROVEN":
            raise SystemExit(2)
    except Exception as error:
        print(json.dumps({
            "status": "BLOCKED",
            "diagnostic_code": diagnostic_code(error),
            "candidate_status": "PROPOSED_NOT_APPROVED",
            "activation_enabled": False,
            "screening_enabled": False,
            "methodology_changed": False,
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "trading_enabled": False,
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
