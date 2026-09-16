"""One-shot broad authenticated proof for the isolated 5DR quantitative backbone.

Output is deliberately sanitized: identities, counts, latency classes and digests only.
Live prices are test evidence and are not emitted as canonical 5DR market inputs.
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_instruments import resolve_global_instruments, resolve_nearest_nifty_future
from experiments.upstox_quant_client import INDIA_VIX, QuantReadOnlyClient
from experiments.upstox_safe_diagnostics import diagnostic_code
from experiments.upstox_session import get_nfo_market_status, select_session_valid_expiry
from experiments.upstox_transport import CurlOpener
from experiments.upstox_universe import build_core_5dr_universe
from phase1.upstox import NIFTY, PipelineError, ReadOnlyClient

IST = ZoneInfo("Asia/Kolkata")
EXPECTED = (PipelineError, ValueError, KeyError, TypeError, StopIteration)


class QuantProbeStageError(Exception):
    def __init__(self, stage, error):
        super().__init__(stage)
        self.stage = stage
        self.error = error


def _proof(envelope):
    return {"source_path": envelope["source_path"], "sha256": envelope["sha256"], "received_at": envelope["received_at"]}


def _prove_global_live(client, target, identity):
    """Use the provider surface empirically proven for each global segment.

    Current Upstox documentation says Global Indicators are supported by intraday and
    historical V3. A live Full Quote V3 request for Brent returned HTTP 400 on 16 Sep
    2026, so indicators are proven via one-minute intraday candles instead of assuming
    the quote surface. Global indices continue through Full Quote V3.
    """
    key = identity["instrument_key"]
    segment = identity["segment"]
    if segment == "GLOBAL_INDEX":
        envelope = client.full_quotes([key])
        return {"surface": "FULL_QUOTE_V3", "validated_records": len(envelope["validated_instrument_tokens"]), "envelope": envelope}
    if segment == "GLOBAL_INDICATOR":
        envelope = client.intraday(key, "minutes", 1)
        return {"surface": "INTRADAY_CANDLE_V3", "validated_records": envelope["validated_candles"], "envelope": envelope}
    raise PipelineError(f"Unsupported global segment for live proof: {target}")


def run(token):
    stage = "INIT"
    try:
        now = datetime.now(IST)
        today = now.date()

        stage = "OPTION_CONTRACT_DISCOVERY"
        legacy = ReadOnlyClient(token, opener=CurlOpener())
        contracts = legacy.contracts()
        rows = contracts["payload"]["data"]
        if not isinstance(rows, list):
            raise PipelineError("Contract array missing")
        expiries = sorted({row["expiry"] for row in rows if isinstance(row, dict) and row.get("underlying_key") == NIFTY and isinstance(row.get("expiry"), str)})

        stage = "MARKET_STATUS_EXPIRY"
        market_session = get_nfo_market_status(token)
        expiry = select_session_valid_expiry(expiries, today, market_session["status"])

        stage = "GLOBAL_INSTRUMENT_MASTER"
        catalogs = PublicInstrumentCatalog()
        global_master = catalogs.global_instruments()
        globals_by_id = resolve_global_instruments(global_master["records"])

        stage = "NSE_INSTRUMENT_MASTER"
        nse_master = catalogs.nse_instruments()
        future = resolve_nearest_nifty_future(nse_master["records"], today)
        universe = build_core_5dr_universe(globals_by_id, future)

        client = QuantReadOnlyClient(token, universe)

        stage = "DOMESTIC_QUOTES_NIFTY_VIX_FUTURE"
        domestic_quotes = client.full_quotes([NIFTY, INDIA_VIX, future["instrument_key"]])

        global_live = {}
        for target, identity in sorted(globals_by_id.items()):
            stage = "GLOBAL_LIVE_" + target.upper()
            global_live[target] = _prove_global_live(client, target, identity)

        stage = "NIFTY_INTRADAY_15M"
        candle_15m = client.intraday(NIFTY, "minutes", 15)
        stage = "NIFTY_INTRADAY_30M"
        candle_30m = client.intraday(NIFTY, "minutes", 30)
        stage = "NIFTY_INTRADAY_1H"
        candle_1h = client.intraday(NIFTY, "hours", 1)

        stage = "FII"
        fii = client.institutional("fii", ["NSE_EQ|CASH", "NSE_FO|INDEX_FUTURES", "NSE_FO|INDEX_OPTIONS"])
        stage = "DII"
        dii = client.institutional("dii", "NSE_EQ|CASH")

        stage = "OI"
        oi = client.option_analytics("oi", expiry=expiry, date_value=today.isoformat())
        stage = "CHANGE_OI"
        change_oi = client.option_analytics("change_oi", expiry=expiry, date_value=today.isoformat(), interval=1)
        stage = "PCR"
        pcr = client.option_analytics("pcr", expiry=expiry, date_value=today.isoformat(), bucket_interval=60)
        stage = "MAX_PAIN"
        max_pain = client.option_analytics("max_pain", expiry=expiry, date_value=today.isoformat(), bucket_interval=60)

        global_count = len(global_live)
        live_instrument_count = len(domestic_quotes["validated_instrument_tokens"]) + global_count
        if live_instrument_count != len(universe):
            raise PipelineError("Broad live proof count mismatch")

        return {
            "status": "5DR_QUANT_BACKBONE_BROAD_PROBE_PASSED",
            "source_semantic": "UPSTOX_AUTHENTICATED",
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "canonical_integration_enabled": False,
            "as_of_date_ist": today.isoformat(),
            "selected_nifty_expiry": expiry,
            "nfo_session": market_session["status"],
            "core_live_instruments_validated": live_instrument_count,
            "live_surface_proof": {
                "domestic_full_quote_instruments": len(domestic_quotes["validated_instrument_tokens"]),
                "global_indices_full_quote": sum(1 for p in global_live.values() if p["surface"] == "FULL_QUOTE_V3"),
                "global_indicators_intraday": sum(1 for p in global_live.values() if p["surface"] == "INTRADAY_CANDLE_V3"),
                "mixed_full_quote_batch": "NOT_USED_AFTER_PROVIDER_HTTP_400",
                "global_indicator_full_quote": "NOT_USED_AFTER_BRENT_HTTP_400",
            },
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
                    "segment": identity["segment"],
                    "provider_latency": identity["provider_latency"],
                    "live_surface": global_live[target]["surface"],
                    "validated_records": global_live[target]["validated_records"],
                    "provenance": _proof(global_live[target]["envelope"]),
                }
                for target, identity in sorted(globals_by_id.items())
            },
            "nifty_future": {"instrument_key": future["instrument_key"], "expiry": future["expiry"]},
            "catalog_provenance": {
                "global": {"sha256": global_master["sha256"], "received_at": global_master["received_at"]},
                "nse": {"sha256": nse_master["sha256"], "received_at": nse_master["received_at"]},
            },
            "source_provenance": {
                "contracts": _proof(contracts), "domestic_quotes": _proof(domestic_quotes),
                "15m": _proof(candle_15m), "30m": _proof(candle_30m), "1h": _proof(candle_1h),
                "fii": _proof(fii), "dii": _proof(dii), "oi": _proof(oi), "change_oi": _proof(change_oi),
                "pcr": _proof(pcr), "max_pain": _proof(max_pain),
            },
            "global_freshness_note": "Retrieval and provider-declared latency proven here; timestamp freshness enforcement remains a separate reliability gate.",
        }
    except QuantProbeStageError:
        raise
    except EXPECTED as error:
        raise QuantProbeStageError(stage, error) from None


if __name__ == "__main__":
    try:
        print(json.dumps(run(os.getenv("UPSTOX_ANALYTICS_TOKEN")), sort_keys=True, separators=(",", ":")))
    except QuantProbeStageError as failure:
        print(json.dumps({
            "status": "BLOCKED",
            "read_only": True,
            "trading_enabled": False,
            "production_5dr_write_enabled": False,
            "canonical_integration_enabled": False,
            "stage": failure.stage,
            "diagnostic_code": diagnostic_code(failure.error),
        }, sort_keys=True, separators=(",", ":")))
        raise SystemExit(2)
