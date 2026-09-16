"""Freeze validated quantitative, derived-chart and external evidence for one 5DR run.

The bundle is an immutable handoff boundary.  It does not score, forecast, recommend,
write storage, invoke the web, or invoke a broker.  It exists so production 5DR can
consume one auditable evidence snapshot instead of screenshots or mutable live objects.
"""
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError
from experiments.data_requirements import requirements

SCHEMA = "5dr-frozen-evidence-bundle-v1"
RECORD_SCHEMA = "market-evidence-data-contract-v1"
CHART_SCHEMA = "5dr-multi-timeframe-chart-evidence-v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CORE_CHART_TIMEFRAMES = frozenset({"1d", "1h", "30m", "15m"})
EXTERNAL_SOURCE_SEMANTICS = frozenset({"WEB_RESEARCH", "OFFICIAL_WEB"})


def _aware_utc(value, field):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} missing")
    if parsed.tzinfo is None:
        raise DataArchitectureError(f"{field} naive")
    return parsed.astimezone(timezone.utc)


def enabled_5dr_machine_variables(*, include_lifecycle=True):
    rows = [row for row in requirements("5DR") if row["enabled_experiment"]]
    ids = [row["variable_id"] for row in rows]
    if not include_lifecycle:
        ids = [value for value in ids if value != "OPTION_LIFECYCLE_PRICES"]
    return tuple(ids)


def _validate_record(record):
    if not isinstance(record, dict) or record.get("schema_version") != RECORD_SCHEMA:
        raise DataArchitectureError("evidence record schema invalid")
    if record.get("consumer") != "5DR":
        raise DataArchitectureError("non-5DR record in 5DR bundle")
    if record.get("eligible_for_consumer") is not True:
        raise DataArchitectureError("ineligible record in 5DR bundle")
    fingerprint = record.get("record_fingerprint")
    if not isinstance(fingerprint, str) or not SHA256_RE.fullmatch(fingerprint):
        raise DataArchitectureError("evidence record fingerprint invalid")
    variable_id = record.get("variable_id")
    if not isinstance(variable_id, str) or not variable_id:
        raise DataArchitectureError("evidence variable id invalid")
    source_semantic = record.get("source_semantic")
    if not isinstance(source_semantic, str) or not source_semantic:
        raise DataArchitectureError("evidence source semantic invalid")
    source_sha = record.get("source_sha256")
    if not isinstance(source_sha, str) or not SHA256_RE.fullmatch(source_sha):
        raise DataArchitectureError("evidence source digest invalid")
    return {
        "variable_id": variable_id,
        "fingerprint": fingerprint,
        "source_semantic": source_semantic,
    }


def _validate_chart(chart):
    if not isinstance(chart, dict) or chart.get("schema") != CHART_SCHEMA:
        raise DataArchitectureError("derived chart bundle invalid")
    if chart.get("directional_score_assigned") is not False:
        raise DataArchitectureError("derived chart layer cannot assign directional score")
    if chart.get("forecast_released") is not False or chart.get("trading_enabled") is not False:
        raise DataArchitectureError("derived chart layer crossed execution boundary")
    timeframes = chart.get("timeframes")
    if not isinstance(timeframes, dict):
        raise DataArchitectureError("derived chart timeframes missing")
    for timeframe, item in timeframes.items():
        if not isinstance(item, dict) or item.get("schema") != "5dr-derived-chart-evidence-v1":
            raise DataArchitectureError("derived chart timeframe invalid")
        if item.get("timeframe") != timeframe:
            raise DataArchitectureError("derived chart timeframe identity mismatch")
        if item.get("directional_score_assigned") is not False:
            raise DataArchitectureError("timeframe chart evidence assigned a score")
    return set(timeframes)


def _validate_external(item):
    if not isinstance(item, dict):
        raise DataArchitectureError("external evidence invalid")
    category = item.get("category")
    semantic = item.get("source_semantic")
    reference = item.get("source_reference")
    digest = item.get("source_sha256")
    if not isinstance(category, str) or not category.strip():
        raise DataArchitectureError("external evidence category invalid")
    if semantic not in EXTERNAL_SOURCE_SEMANTICS:
        raise DataArchitectureError("external evidence semantic invalid")
    if not isinstance(reference, str) or not reference.strip():
        raise DataArchitectureError("external evidence reference invalid")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise DataArchitectureError("external evidence digest invalid")
    retrieved = _aware_utc(item.get("retrieved_at"), "external evidence retrieval")
    if item.get("validation_status") != "VALID":
        raise DataArchitectureError("external evidence is not validated")
    return {
        "category": category.strip().upper(),
        "source_semantic": semantic,
        "source_reference": reference.strip(),
        "source_sha256": digest,
        "retrieved_at": retrieved.isoformat(),
    }


def build_evidence_bundle(*, run_id, frozen_at, quantitative_records,
                          chart_evidence, external_evidence=(),
                          required_variables=None,
                          required_external_categories=(),
                          require_screenshot_free=True):
    if not isinstance(run_id, str) or not run_id.strip():
        raise DataArchitectureError("evidence bundle run id invalid")
    frozen = _aware_utc(frozen_at, "evidence freeze")
    if not isinstance(quantitative_records, list):
        raise DataArchitectureError("quantitative evidence list invalid")
    if not isinstance(require_screenshot_free, bool):
        raise DataArchitectureError("screenshot-free gate invalid")

    record_meta = [_validate_record(record) for record in quantitative_records]
    fingerprints = [row["fingerprint"] for row in record_meta]
    if len(fingerprints) != len(set(fingerprints)):
        raise DataArchitectureError("duplicate quantitative evidence record")
    variables_present = {row["variable_id"] for row in record_meta}
    source_semantics = {row["source_semantic"] for row in record_meta}

    if required_variables is None:
        required_variables = enabled_5dr_machine_variables(include_lifecycle=False)
    if not isinstance(required_variables, (list, tuple, set, frozenset)):
        raise DataArchitectureError("required variable set invalid")
    required_variables = tuple(sorted(set(required_variables)))
    if any(not isinstance(value, str) or not value for value in required_variables):
        raise DataArchitectureError("required variable id invalid")
    missing_variables = sorted(set(required_variables) - variables_present)

    chart_timeframes = _validate_chart(chart_evidence)
    missing_chart_timeframes = sorted(CORE_CHART_TIMEFRAMES - chart_timeframes)

    if not isinstance(external_evidence, (list, tuple)):
        raise DataArchitectureError("external evidence list invalid")
    external = [_validate_external(item) for item in external_evidence]
    external_categories = {item["category"] for item in external}
    if not isinstance(required_external_categories, (list, tuple, set, frozenset)):
        raise DataArchitectureError("required external categories invalid")
    required_external = {str(value).strip().upper() for value in required_external_categories if str(value).strip()}
    missing_external = sorted(required_external - external_categories)

    screenshot_semantics = sorted(value for value in source_semantics if "SCREENSHOT" in value)
    screenshot_dependency = bool(screenshot_semantics)
    blocked_reasons = []
    if missing_variables:
        blocked_reasons.append("MISSING_QUANTITATIVE_VARIABLES")
    if missing_chart_timeframes:
        blocked_reasons.append("MISSING_CORE_CHART_TIMEFRAMES")
    if missing_external:
        blocked_reasons.append("MISSING_EXTERNAL_CONTEXT")
    if require_screenshot_free and screenshot_dependency:
        blocked_reasons.append("SCREENSHOT_DEPENDENCY_PRESENT")

    bundle = {
        "schema": SCHEMA,
        "run_id": run_id.strip(),
        "frozen_at": frozen.isoformat(),
        "status": "READY" if not blocked_reasons else "BLOCKED",
        "blocked_reasons": blocked_reasons,
        "quantitative_records": deepcopy(quantitative_records),
        "derived_chart_evidence": deepcopy(chart_evidence),
        "external_evidence": external,
        "coverage": {
            "required_variables": list(required_variables),
            "variables_present": sorted(variables_present),
            "missing_variables": missing_variables,
            "required_chart_timeframes": sorted(CORE_CHART_TIMEFRAMES),
            "chart_timeframes_present": sorted(chart_timeframes),
            "missing_chart_timeframes": missing_chart_timeframes,
            "required_external_categories": sorted(required_external),
            "external_categories_present": sorted(external_categories),
            "missing_external_categories": missing_external,
        },
        "screenshot_policy": {
            "require_screenshot_free": require_screenshot_free,
            "screenshot_dependency": screenshot_dependency,
            "screenshot_semantics": screenshot_semantics,
        },
        "directional_score_assigned": False,
        "forecast_released": False,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
    }
    encoded = json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str).encode()
    bundle["bundle_sha256"] = hashlib.sha256(encoded).hexdigest()
    return bundle
