"""Live non-publishing readiness gate for a screenshot-free V2.2.3 5DR shadow run.

This deliberately does not create a forecast. It proves current machine/chart/web lanes
in one invocation and refuses READY while any canonical evidence family lacks an
explicitly governed acquisition identity.
"""
import json
import os

from experiments.live_web_context import collect_live_web_context
from experiments.participation_universe import unresolved_participation_gate
from experiments.run_upstox_chart_probe import run as run_chart_probe
from experiments.run_upstox_quant_probe import run as run_quant_probe
from experiments.upstox_safe_diagnostics import diagnostic_code


def run(token):
    quant = run_quant_probe(token)
    if quant.get("status") != "5DR_QUANT_BACKBONE_BROAD_PROBE_PASSED":
        return {
            "status": "BLOCKED",
            "blockers": ["QUANTITATIVE_BACKBONE_NOT_READY"],
            "quant_status": quant.get("status"),
            "screenshot_required": False,
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "trading_enabled": False,
        }

    chart = run_chart_probe(token)
    if chart.get("status") != "5DR_LIVE_CHART_DERIVATION_PASSED":
        return {
            "status": "BLOCKED",
            "blockers": ["CHART_EVIDENCE_NOT_READY"],
            "chart_status": chart.get("status"),
            "screenshot_required": False,
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "trading_enabled": False,
        }

    web = collect_live_web_context()
    participation = unresolved_participation_gate()
    blockers = []
    if web.get("status") != "5DR_LIVE_WEB_CONTEXT_PASSED":
        blockers.append("WEB_CONTEXT_NOT_READY")
    if participation.get("status") != "READY":
        blockers.append(participation["blocker"])

    return {
        "status": "READY_FOR_GOVERNED_JUDGMENT" if not blockers else "BLOCKED",
        "blockers": blockers,
        "quant_status": quant["status"],
        "chart_status": chart["status"],
        "web_status": web["status"],
        "selected_nifty_expiry": quant["selected_nifty_expiry"],
        "nfo_session": quant["nfo_session"],
        "machine_families_proven": [
            "NIFTY_PRICE_CANDLES",
            "INDIA_VIX",
            "NIFTY_FUTURES",
            "NIFTY_OPTION_CONTRACTS",
            "NIFTY_OPTION_CHAIN",
            "NIFTY_DERIVATIVE_ANALYTICS",
            "FII_DII_CASH",
            "FII_INDEX_DERIVATIVES",
            "GLOBAL_RISK_INDICES",
            "CRUDE_USDINR",
        ],
        "missing_machine_variables": participation["missing_variables"],
        "web_roles": web["roles"],
        "chart_timeframes": sorted(chart["timeframes"]),
        "screenshot_required": False,
        "directional_score_assigned": False,
        "governed_judgment_created": False,
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "canonical_integration_enabled": False,
        "trading_enabled": False,
        "methodology_changed": False,
    }


if __name__ == "__main__":
    try:
        result = run(os.environ.get("UPSTOX_ANALYTICS_TOKEN", ""))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        # BLOCKED is an expected, successful fail-closed proof while an explicit
        # configuration gate remains unresolved. Infrastructure failures still exit 2.
        if result["status"] not in {"READY_FOR_GOVERNED_JUDGMENT", "BLOCKED"}:
            raise SystemExit(2)
    except Exception as error:
        print(json.dumps({
            "status": "ERROR",
            "diagnostic_code": diagnostic_code(error),
            "screenshot_required": False,
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "canonical_integration_enabled": False,
            "trading_enabled": False,
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
