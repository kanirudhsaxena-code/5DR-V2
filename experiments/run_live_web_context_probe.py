"""Non-publishing live proof for the V2.2.3 governed web-context lane."""
import json

from experiments.data_contract import DataArchitectureError
from experiments.live_web_context import collect_live_web_context


def _safe_item(item):
    return {
        "category": item["category"],
        "source_semantic": item["source_semantic"],
        "authority": item["authority"],
        "source_reference": item["source_reference"],
        "source_sha256": item["source_sha256"],
        "research_sha256": item["research_sha256"],
        "retrieved_at": item["retrieved_at"],
        "fact_summary_chars": len(item["fact_summary"]),
    }


def run():
    result = collect_live_web_context()
    return {
        "status": result["status"],
        "roles": result["roles"],
        "items": [_safe_item(item) for item in result["items"]],
        "screenshot_required": False,
        "directional_score_assigned": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "trading_enabled": False,
    }


if __name__ == "__main__":
    try:
        result = run()
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        if result["status"] != "5DR_LIVE_WEB_CONTEXT_PASSED":
            raise SystemExit(2)
    except DataArchitectureError as error:
        print(json.dumps({
            "status": "BLOCKED",
            "diagnostic": str(error),
            "screenshot_required": False,
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "trading_enabled": False,
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
