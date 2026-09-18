"""Non-publishing live proof for the V2.2.3 governed web-context lane."""
import json
import re

from experiments.data_contract import DataArchitectureError
from experiments.live_web_context import collect_live_web_context

SAFE_FACT_KEYS = frozenset({
    "release_date",
    "treasury_10y_percent",
    "effective_fed_funds_percent",
    "meeting_type",
    "meeting_start_date",
    "meeting_end_date",
    "decision_day_matches_retrieval_date",
    "statement_time_et",
    "press_conference_time_et",
    "policy_repo_rate_percent",
    "rbi_displayed_usdinr",
    "rbi_displayed_usdinr_as_at",
})


def _bounded_facts(summary):
    quality_match = re.search(r"fact_quality=([A-Z_]+);", summary)
    facts_match = re.search(r"facts_json=(\{.*?\});\s+source_excerpt=", summary)
    quality = quality_match.group(1) if quality_match else "UNKNOWN"
    facts = {}
    if facts_match:
        try:
            parsed = json.loads(facts_match.group(1))
        except (TypeError, ValueError):
            parsed = {}
        if isinstance(parsed, dict):
            facts = {key: parsed[key] for key in sorted(parsed) if key in SAFE_FACT_KEYS}
    return {"fact_quality": quality, "facts": facts}


def _safe_item(item):
    bounded = _bounded_facts(item["fact_summary"])
    return {
        "category": item["category"],
        "source_semantic": item["source_semantic"],
        "authority": item["authority"],
        "source_reference": item["source_reference"],
        "source_sha256": item["source_sha256"],
        "research_sha256": item["research_sha256"],
        "retrieved_at": item["retrieved_at"],
        "fact_summary_chars": len(item["fact_summary"]),
        "fact_quality": bounded["fact_quality"],
        "facts": bounded["facts"],
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
