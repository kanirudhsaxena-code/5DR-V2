"""Non-publishing shadow runner for autonomous 5DR evidence acquisition."""
import json
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

from phase1.upstox import NIFTY, PipelineError, ReadOnlyClient, safe_failure
from src.autonomous_acquisition import AcquisitionBlocked, build_evidence_envelope
from src.upstox_evidence import acquire_market_observations


def run_shadow(request_id: str, client: ReadOnlyClient, today: date) -> dict:
    contracts = client.contracts()
    rows = contracts["payload"]["data"]
    expiries = sorted({r["expiry"] for r in rows if r.get("underlying_key") == NIFTY and date.fromisoformat(r["expiry"]) >= today})
    if not expiries:
        raise PipelineError("No active NIFTY expiries returned")
    market = acquire_market_observations(client, expiries[0])
    # EVENT_SHOCK is intentionally not synthesized here. Until the controlled
    # web/event registry has a live fetcher, the envelope remains blocked.
    envelope = build_evidence_envelope(request_id, market)
    envelope["mode"] = "SHADOW_NON_PUBLISHING"
    return envelope


if __name__ == "__main__":
    try:
        result = run_shadow(
            os.getenv("REQUEST_ID", "5drreq_shadow"),
            ReadOnlyClient(os.getenv("UPSTOX_ANALYTICS_TOKEN")),
            datetime.now(ZoneInfo("Asia/Kolkata")).date(),
        )
        print(json.dumps(result))
        raise SystemExit(0 if result["status"] == "AUTONOMOUS_EVIDENCE_BLOCKED" else 3)
    except (PipelineError, AcquisitionBlocked, KeyError, TypeError, ValueError) as error:
        diagnostic = safe_failure(error) if isinstance(error, PipelineError) else "ACQUISITION_GOVERNANCE_BLOCKED"
        print(json.dumps({"status": "AUTONOMOUS_EVIDENCE_BLOCKED", "mode": "SHADOW_NON_PUBLISHING", "trading_enabled": False, "forecast_release_enabled": False, "diagnostic_code": diagnostic}))
        raise SystemExit(2)
