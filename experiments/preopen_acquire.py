"""Read-only acquisition runner for one 5DR PREOPEN evidence bundle.

No scoring, forecast release, canonical/lifecycle writes or trading are reachable here.
The runner is intentionally not scheduled in production until a separate live PASS gate.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from experiments.data_contract import DataArchitectureError, build_record
from experiments.live_shadow_bundle import _quote_map, _quote_snapshot, _sha, _stamp
from experiments.live_web_context import collect_live_web_context
from experiments.preopen_evidence import (
    build_preopen_evidence_bundle,
    verify_preopen_evidence_bundle,
)
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_instruments import resolve_global_instruments
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_session import get_nfo_market_status, select_session_valid_expiry
from experiments.upstox_transport import CurlOpener
from phase1.upstox import NIFTY, ReadOnlyClient, PipelineError

IST = ZoneInfo("Asia/Kolkata")
OUTPUT_DIR = Path(".preopen/evidence")
BUNDLE_FILE = OUTPUT_DIR / "bundle.json"
AUDIT_FILE = OUTPUT_DIR / "audit.json"

RISK_TARGETS = (
    "gift_nifty", "sp500", "dow_jones", "us_tech_100",
    "nikkei_225", "hang_seng", "dax", "ftse_100",
)
MACRO_TARGETS = ("brent", "wti", "usd_inr")


def classify_preopen_window(now):
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise DataArchitectureError("preopen time must be timezone-aware")
    local = now.astimezone(IST)
    if local.weekday() >= 5:
        raise DataArchitectureError("preopen target is not a weekday")
    clock = local.timetz().replace(tzinfo=None)
    if not (time(8, 45) <= clock < time(9, 0)):
        raise DataArchitectureError("outside PREOPEN validation window")
    return {
        "label": "PREOPEN",
        "target_session_date": local.date().isoformat(),
        "captured_at_ist": local.isoformat(),
        "window_start_ist": "08:45:00",
        "window_end_exclusive_ist": "09:00:00",
    }


def _latest_prior_candle(rows, target_date):
    valid = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 7:
            raise DataArchitectureError("preopen historical candle invalid")
        stamp = _stamp(row[0])
        if stamp.date() < target_date:
            valid.append((stamp, row))
    if not valid:
        raise DataArchitectureError("preopen prior-session candle missing")
    valid.sort(key=lambda item: item[0])
    return valid[-1]


def _global_record(variable_id, targets, global_values, global_envs, frozen_at):
    values = {target: global_values[target] for target in targets}
    times = [_stamp(values[target]["timestamp"]) for target in targets]
    max_latency = max(values[target]["provider_latency_seconds"] for target in targets)
    age = max((frozen_at - stamp).total_seconds() for stamp in times)
    if age < -60:
        raise DataArchitectureError("preopen global timestamp is in the future")
    if age > max_latency + 1800:
        freshness = "HISTORICAL"
        latency = None
    else:
        freshness = {
            20: "DELAYED_20S",
            120: "DELAYED_120S",
            900: "DELAYED_15M",
        }[max_latency]
        latency = max_latency
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id=variable_id,
        consumer="5DR",
        subject={
            "kind": "MARKET_INSTRUMENT",
            "id": variable_id,
            "name": (
                "Approved global risk indices"
                if variable_id == "GLOBAL_RISK_INDICES"
                else "Crude and USD/INR"
            ),
        },
        metric="preopen_overnight_market_snapshots",
        values={
            "instruments": values,
            "aggregate_timestamp_policy": "earliest constituent provider timestamp; individual timestamps preserved",
        },
        timeframe="quote_or_1m",
        provider_timestamp=min(times).isoformat(),
        acquisition_timestamp=frozen_at,
        freshness_status=freshness,
        source_reference=f"UPSTOX_COMPOSITE:{variable_id}:PREOPEN",
        source_sha256=_sha(*(global_envs[target]["sha256"] for target in targets)),
        provider_latency_seconds=latency,
    )


def acquire_preopen_bundle(token, *, now=None, completed_run_keys=()):
    if not isinstance(token, str) or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")
    now = now or datetime.now(IST)
    window = classify_preopen_window(now)
    target_date = now.astimezone(IST).date()
    frozen_at = datetime.now(timezone.utc)

    legacy = ReadOnlyClient(token, opener=CurlOpener())
    contracts = legacy.contracts()
    contract_rows = contracts["payload"]["data"]
    expiries = sorted({
        row["expiry"] for row in contract_rows
        if isinstance(row, dict)
        and row.get("underlying_key") == NIFTY
        and isinstance(row.get("expiry"), str)
        and datetime.fromisoformat(row["expiry"]).date() >= target_date
    })
    market_status = get_nfo_market_status(token)
    expiry = select_session_valid_expiry(expiries, target_date, market_status["status"])

    catalogs = PublicInstrumentCatalog()
    globals_by_id = resolve_global_instruments(catalogs.global_instruments()["records"])
    approved = {NIFTY} | {item["instrument_key"] for item in globals_by_id.values()}
    client = QuantReadOnlyClient(token, approved, opener=CurlOpener())

    history = client.historical(
        NIFTY, "days", 1,
        target_date - timedelta(days=10),
        target_date - timedelta(days=1),
    )
    prior_stamp, prior_row = _latest_prior_candle(
        history["payload"]["data"]["candles"], target_date
    )
    previous_session = prior_stamp.date()
    prior_close_record = build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id="NIFTY_PRICE_CANDLES",
        consumer="5DR",
        subject={
            "kind": "MARKET_INSTRUMENT",
            "id": "NIFTY_50",
            "name": "NIFTY 50",
            "instrument_key": NIFTY,
            "segment": "NSE_INDEX",
        },
        metric="prior_session_final_ohlc",
        values={
            "open": prior_row[1],
            "high": prior_row[2],
            "low": prior_row[3],
            "close": prior_row[4],
            "volume": prior_row[5],
            "open_interest": prior_row[6],
        },
        timeframe="1d",
        provider_timestamp=prior_stamp,
        acquisition_timestamp=frozen_at,
        freshness_status="SESSION_FINAL",
        source_reference=history["source_path"],
        source_sha256=history["sha256"],
    )

    global_values = {}
    global_envs = {}
    for target, identity in sorted(globals_by_id.items()):
        key = identity["instrument_key"]
        if identity["segment"] == "GLOBAL_INDEX":
            env = client.full_quotes([key])
            snap = _quote_snapshot(_quote_map(env)[key])
        else:
            env = client.intraday(key, "minutes", 1)
            latest = max(
                env["payload"]["data"]["candles"],
                key=lambda row: _stamp(row[0]),
            )
            snap = {
                "last_price": latest[4],
                "volume": latest[5],
                "open_interest": latest[6],
                "previous_close": None,
                "change_pct_vs_previous_close": None,
                "timestamp": _stamp(latest[0]).isoformat(),
            }
        latency = identity["provider_latency"]
        global_values[target] = {
            **snap,
            "instrument_key": key,
            "segment": identity["segment"],
            "provider_declared_latency": latency["declared"],
            "provider_latency_seconds": latency["seconds"],
        }
        global_envs[target] = env

    overnight_records = [
        _global_record(
            "GLOBAL_RISK_INDICES", RISK_TARGETS,
            global_values, global_envs, frozen_at,
        ),
        _global_record(
            "CRUDE_USDINR", MACRO_TARGETS,
            global_values, global_envs, frozen_at,
        ),
    ]
    web = collect_live_web_context(now=frozen_at)
    run_id = f"V223-PREOPEN-{target_date.strftime('%Y%m%d')}-{frozen_at.strftime('%H%M%SZ')}"
    bundle = build_preopen_evidence_bundle(
        target_session_date=target_date.isoformat(),
        previous_session_date=previous_session.isoformat(),
        frozen_at=frozen_at,
        prior_close_record=prior_close_record,
        overnight_records=overnight_records,
        external_evidence=web["items"],
        active_expiry=expiry,
        run_id=run_id,
        completed_run_keys=completed_run_keys,
    )
    verification = verify_preopen_evidence_bundle(bundle)
    return bundle, {
        "schema": "5dr-preopen-acquisition-audit-v1",
        "status": verification["status"],
        "label": window["label"],
        "target_session_date": target_date.isoformat(),
        "previous_session_date": previous_session.isoformat(),
        "active_derivative_expiry": expiry,
        "bundle_sha256": verification["bundle_sha256"],
        "run_key": verification["run_key"],
        "market_status": market_status["status"],
        "forecast_released": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_execution_enabled": False,
        "methodology_changed": False,
        "production_activation_allowed": False,
    }


def run():
    token = os.environ.get("UPSTOX_ANALYTICS_TOKEN", "").strip()
    bundle, audit = acquire_preopen_bundle(token)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_FILE.write_text(
        json.dumps(bundle, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    AUDIT_FILE.write_text(
        json.dumps(audit, sort_keys=True, separators=(",", ":"), default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, sort_keys=True, separators=(",", ":")))
    return audit


if __name__ == "__main__":
    run()
