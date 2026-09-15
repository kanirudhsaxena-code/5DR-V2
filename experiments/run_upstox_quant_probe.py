"""One-shot broad authenticated proof for the isolated 5DR quantitative backbone.

Output is deliberately sanitized: identities, counts, latency classes and digests only.
Live prices are test evidence and are not emitted as canonical 5DR market inputs.
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from experiments.upstox_acquire import AcquisitionStageError, acquire_live_sample
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_instruments import resolve_global_instruments, resolve_nearest_nifty_future
from experiments.upstox_quant_client import QuantReadOnlyClient
from experiments.upstox_universe import build_core_5dr_universe
from phase1.upstox import PipelineError, safe_failure

IST = ZoneInfo("Asia/Kolkata")


def _proof(envelope):
    return {"source_path": envelope["source_path"], "sha256": envelope["sha256"], "received_at": envelope["received_at"]}


def run(token):
    now = datetime.now(IST)
    today = now.date()

    existing = acquire_live_sample(token)
    expiry = existing["selected_expiry"]

    catalogs = PublicInstrumentCatalog()
    global_master = catalogs.global_instruments()
    nse_master = catalogs.nse_instruments()
    globals_by_id = resolve_global_instruments(global_master["records"])
    future = resolve_nearest_nifty_future(nse_master["records"], today)
    universe = build_core_5dr_universe(globals_by_id, future)

    client = QuantReadOnlyClient(token, universe)
    quotes = client.full_quotes(sorted(universe))
    candle_15m = client.intraday("NSE_INDEX|Nifty 50", "minutes", 15)
    candle_30m = client.intraday("NSE_INDEX|Nifty 50", "minutes", 30)
    candle_1h = client.intraday("NSE_INDEX|Nifty 50", "hours", 1)
    fii = client.institutional("fii", ["NSE_EQ|CASH", "NSE_FO|INDEX_FUTURES", "NSE_FO|INDEX_OPTIONS"])
    dii = client.institutional("dii", "NSE_EQ|CASH")
    oi = client.option_analytics("oi", expiry=expiry, date_value=today.isoformat())
    change_oi = client.option_analytics("change_oi", expiry=expiry, date_value=today.isoformat(), interval=1)
    pcr = client.option_analytics("pcr", expiry=expiry, date_value=today.isoformat(), bucket_interval=60)
    max_pain = client.option_analytics("max_pain", expiry=expiry, date_value=today.isoformat(), bucket_interval=60)

    return {
        "status": "5DR_QUANT_BACKBONE_BROAD_PROBE_PASSED",
        "source_semantic": "UPSTOX_AUTHENTICATED",
        "read_only": True,
        "trading_enabled": False,
        "production_5dr_write_enabled": False,
        "canonical_integration_enabled": False,
        "as_of_date_ist": today.isoformat(),
        "selected_nifty_expiry": expiry,
        "core_quote_instruments_validated": len(quotes["validated_instrument_tokens"]),
        "nifty_intraday_candles": {
            "15m": candle_15m["validated_candles"],
            "30m": candle_30m["validated_candles"],
            "1h": candle_1h["validated_candles"],
        },
        "institutional_data_types_validated": {
            "fii": fii["validated_data_types"],
            "dii": dii["validated_data_types"],
        },
        "option_analytics_validated": ["oi", "change_oi", "pcr", "max_pain"],
        "global_instruments": {
            target: {
                "instrument_key": identity["instrument_key"],
                "provider_latency": identity["provider_latency"],
            }
            for target, identity in sorted(globals_by_id.items())
        },
        "nifty_future": {"instrument_key": future["instrument_key"], "expiry": future["expiry"]},
        "catalog_provenance": {
            "global": {"sha256": global_master["sha256"], "received_at": global_master["received_at"]},
            "nse": {"sha256": nse_master["sha256"], "received_at": nse_master["received_at"]},
        },
        "source_provenance": {
            "quotes": _proof(quotes), "15m": _proof(candle_15m), "30m": _proof(candle_30m), "1h": _proof(candle_1h),
            "fii": _proof(fii), "dii": _proof(dii), "oi": _proof(oi), "change_oi": _proof(change_oi),
            "pcr": _proof(pcr), "max_pain": _proof(max_pain),
        },
        "global_freshness_note": "Retrieval and provider-declared latency proven here; timestamp freshness enforcement remains a separate reliability gate.",
    }


if __name__ == "__main__":
    try:
        print(json.dumps(run(os.getenv("UPSTOX_ANALYTICS_TOKEN")), sort_keys=True))
    except AcquisitionStageError as error:
        print(json.dumps({"status": "BLOCKED", "trading_enabled": False, "diagnostic_code": safe_failure(error.error)}))
        raise SystemExit(2)
    except (PipelineError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "trading_enabled": False, "diagnostic_code": safe_failure(error)}))
        raise SystemExit(2)
