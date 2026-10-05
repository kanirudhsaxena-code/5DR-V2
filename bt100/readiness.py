"""Fail-closed BT100 readiness validation.

No network access, production database access, trading action, or inference call is
implemented here. This module validates only frozen research configuration and
readiness evidence produced by separate read-only probes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ALLOWED_EVIDENCE_STATUS = {
    "PROVEN", "DOCUMENTED", "PROBE_REQUIRED", "PARTIAL", "MISSING",
    "CONTAMINATED", "EXTERNAL_ONLY", "NOT_APPLICABLE",
}
HORIZONS = ["D+1", "D+2", "D+3", "D+4", "D+5"]


class ReadinessError(ValueError):
    pass


def canonical_sha256(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_config(config):
    if config.get("batch_id") != "BT-5DR-100-V1":
        raise ReadinessError("unexpected batch id")
    if config.get("run_role") != "REPLAY":
        raise ReadinessError("run role must be REPLAY")
    if config.get("official_efficacy_eligible") is not False:
        raise ReadinessError("replay cannot be official efficacy eligible")
    if config.get("target_session_count") != 100:
        raise ReadinessError("target session count must be exactly 100")
    if config.get("horizons") != HORIZONS:
        raise ReadinessError("horizons must be D+1 through D+5")
    if config.get("formal_run_requires_g5_1_pass") is not True:
        raise ReadinessError("formal run must require G5.1 PASS")
    if config.get("production_neuron_budget") != 0:
        raise ReadinessError("production neuron budget must be zero")
    for flag in (
        "production_writes_allowed",
        "trading_allowed",
        "canonical_table_writes_allowed",
        "methodology_tuning_allowed",
    ):
        if config.get(flag) is not False:
            raise ReadinessError(f"{flag} must be false")
    if config.get("evidence_policy") != "POINT_IN_TIME_FAIL_CLOSED":
        raise ReadinessError("evidence policy must fail closed")
    if config.get("missing_evidence_policy") != "DATA_GAP_OR_NOT_SCORABLE":
        raise ReadinessError("missing evidence policy invalid")
    return True


def validate_evidence(requirements_doc):
    rows = requirements_doc.get("requirements")
    if not isinstance(rows, list) or not rows:
        raise ReadinessError("evidence requirements missing")
    seen = set()
    for row in rows:
        rid = row.get("id")
        if not isinstance(rid, str) or not rid:
            raise ReadinessError("evidence requirement id invalid")
        if rid in seen:
            raise ReadinessError("duplicate evidence requirement")
        seen.add(rid)
        if row.get("status") not in ALLOWED_EVIDENCE_STATUS:
            raise ReadinessError(f"invalid evidence status for {rid}")
        if not isinstance(row.get("critical"), bool):
            raise ReadinessError(f"critical flag invalid for {rid}")
    return rows


def validate_target_dates(doc, expected=100):
    sessions = doc.get("sessions")
    if not isinstance(sessions, list) or len(sessions) != expected:
        raise ReadinessError(f"target date count must equal {expected}")
    targets = []
    for row in sessions:
        target = row.get("target_date")
        horizons = row.get("horizon_dates")
        if not isinstance(target, str) or not target:
            raise ReadinessError("target date missing")
        if not isinstance(horizons, dict) or list(horizons) != HORIZONS:
            raise ReadinessError(f"horizon map invalid for {target}")
        if horizons["D+1"] != target:
            raise ReadinessError(f"D+1 must equal target date for {target}")
        if len(set(horizons.values())) != 5:
            raise ReadinessError(f"horizon dates must be unique for {target}")
        targets.append(target)
    if len(set(targets)) != expected:
        raise ReadinessError("target dates must be independent and unique")
    return sessions


def build_report(config, requirements_doc, target_dates=None, probe=None):
    validate_config(config)
    rows = validate_evidence(requirements_doc)
    blockers = []
    warnings = []
    for row in rows:
        status = row["status"]
        if row["critical"] and status in {"MISSING", "CONTAMINATED"}:
            blockers.append(f"{row['id']}:{status}")
        elif status in {"PROBE_REQUIRED", "PARTIAL", "EXTERNAL_ONLY"}:
            warnings.append(f"{row['id']}:{status}")

    targets_valid = False
    target_count = 0
    if target_dates is not None:
        sessions = validate_target_dates(target_dates, config["target_session_count"])
        targets_valid = True
        target_count = len(sessions)

    probe_status = None
    if probe is not None:
        probe_status = probe.get("status")
        if probe_status not in {"PASSED", "PARTIAL"}:
            blockers.append(f"live_probe:{probe_status or 'UNKNOWN'}")
        if probe.get("production_neuron_calls", 0) != 0:
            blockers.append("live_probe:production_neuron_calls_nonzero")
        if probe.get("production_writes", 0) != 0:
            blockers.append("live_probe:production_writes_nonzero")

    g5_pass = config.get("g5_1_status") == "PASS"
    baseline_frozen = config.get("baseline_sha_state") not in {
        None, "", "PENDING_G5_1_PASS",
    }
    formal_ready = (
        g5_pass
        and baseline_frozen
        and targets_valid
        and not blockers
        and probe_status in {"PASSED", "PARTIAL"}
    )
    phase = "FORMAL_REPLAY_READY" if formal_ready else (
        "READINESS_IN_PROGRESS" if not blockers else "READINESS_BLOCKED"
    )
    return {
        "schema": "bt100-readiness-report-v0",
        "batch_id": config["batch_id"],
        "phase": phase,
        "formal_replay_ready": formal_ready,
        "g5_1_passed": g5_pass,
        "baseline_frozen": baseline_frozen,
        "target_dates_valid": targets_valid,
        "target_date_count": target_count,
        "production_neuron_budget": config["production_neuron_budget"],
        "production_writes_allowed": config["production_writes_allowed"],
        "trading_allowed": config["trading_allowed"],
        "blockers": blockers,
        "warnings": warnings,
        "config_sha256": canonical_sha256(config),
        "evidence_requirements_sha256": canonical_sha256(requirements_doc),
        "target_dates_sha256": canonical_sha256(target_dates) if target_dates else None,
        "probe_sha256": canonical_sha256(probe) if probe else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="bt100/config/readiness_v0.json")
    parser.add_argument("--evidence", default="bt100/evidence_requirements.json")
    parser.add_argument("--target-dates")
    parser.add_argument("--probe")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = build_report(
        load_json(args.config),
        load_json(args.evidence),
        load_json(args.target_dates) if args.target_dates else None,
        load_json(args.probe) if args.probe else None,
    )
    rendered = json.dumps(report, sort_keys=True, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if not report["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
