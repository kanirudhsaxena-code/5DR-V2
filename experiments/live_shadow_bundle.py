"""Build one consumer-grade frozen live evidence bundle for a V2.2.3 shadow run.

The module is experimental and read-only. It acquires approved 5DR market evidence,
normalizes the actual market values into the provider-neutral evidence contract,
derives chart structure from frozen candle series, adds governed live web context, and
returns one immutable bundle. It never publishes a forecast, writes production state,
places orders, or changes methodology.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from experiments.chart_structure import derive_multi_timeframe_evidence
from experiments.cache_reconcile import reconcile_candles
from experiments.data_contract import DataArchitectureError, build_record
from experiments.evidence_bundle import build_evidence_bundle
from experiments.live_web_context import collect_live_web_context
from experiments.participation_universe import approved_participation_universe
from experiments.production_cache_read import build_reader_from_database_url
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_instruments import resolve_global_instruments, resolve_nearest_nifty_future
from experiments.upstox_quality import classify_timestamp_freshness
from experiments.upstox_quant_client import INDIA_VIX, QuantReadOnlyClient
from experiments.upstox_sanitizer import sanitize_live_envelopes
from experiments.upstox_session import CLOSED_STATUSES, get_nfo_market_status, select_session_valid_expiry
from experiments.upstox_transport import CurlOpener
from experiments.upstox_universe import build_core_5dr_universe
from phase1.upstox import NIFTY, PipelineError, ReadOnlyClient

IST = ZoneInfo("Asia/Kolkata")
PROVIDER = "UPSTOX"
SOURCE = "UPSTOX_AUTHENTICATED"


def _sha(*values):
    clean = [str(value) for value in values if isinstance(value, str) and value]
    if not clean:
        raise DataArchitectureError("composite source digest missing")
    return hashlib.sha256("|".join(sorted(clean)).encode()).hexdigest()


def _stamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise DataArchitectureError("provider timestamp missing")
    text = value.strip()
    if text.isdigit():
        return _stamp(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise DataArchitectureError("provider timestamp invalid") from None
    if parsed.tzinfo is None:
        raise DataArchitectureError("provider timestamp naive")
    return parsed.astimezone(timezone.utc)


def _quote_map(envelope):
    data = envelope["payload"]["data"]
    if not isinstance(data, dict) or not data:
        raise DataArchitectureError("quote payload missing")
    result = {}
    for row in data.values():
        if not isinstance(row, dict):
            raise DataArchitectureError("quote row invalid")
        key = row.get("instrument_token")
        if not isinstance(key, str) or not key or key in result:
            raise DataArchitectureError("quote identity invalid")
        result[key] = row
    return result


def _quote_snapshot(row):
    timestamp = _stamp(row.get("timestamp"))
    ohlc = row.get("ohlc") if isinstance(row.get("ohlc"), dict) else {}
    close = ohlc.get("close")
    last = row.get("last_price")
    change_pct = None
    if isinstance(last, (int, float)) and not isinstance(last, bool) and isinstance(close, (int, float)) and not isinstance(close, bool) and close:
        change_pct = round((float(last) - float(close)) * 100.0 / float(close), 6)
    return {
        "last_price": last,
        "volume": row.get("volume"),
        "open_interest": row.get("oi"),
        "average_price": row.get("average_price"),
        "total_buy_quantity": row.get("total_buy_quantity"),
        "total_sell_quantity": row.get("total_sell_quantity"),
        "previous_close": close,
        "change_pct_vs_previous_close": change_pct,
        "timestamp": timestamp.isoformat(),
    }


def _require_recent(timestamp, frozen_at, *, max_age_seconds=420):
    status = classify_timestamp_freshness(timestamp, frozen_at, "LIVE", max_age_seconds)
    if status != "LIVE":
        raise DataArchitectureError("required live domestic quote is stale")
    return status


def _merge_candles(*collections):
    merged = {}
    for rows in collections:
        for row in rows:
            if not isinstance(row, list) or len(row) != 7:
                raise DataArchitectureError("candle row invalid")
            stamp = _stamp(row[0]).isoformat()
            merged[stamp] = [stamp] + list(row[1:])
    return [merged[key] for key in sorted(merged)]


def _series_digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _merge_session_intraday(rows, client, market_status, unit, interval, provenance, audit):
    """Overlay the current-session intraday series when the provider exposes it.

    On a closed exchange session, Upstox can legitimately return an empty intraday
    candle array (for example on weekends). That must not invalidate already
    verified historical/cache evidence. Any other provider error still fails closed.
    """
    try:
        intraday = client.intraday(NIFTY, unit, interval)
    except PipelineError as error:
        if market_status in CLOSED_STATUSES and str(error) == "Candle array missing":
            audit["intraday_overlay"] = "UNAVAILABLE_MARKET_CLOSED"
            audit["intraday_provider_call_made"] = 1
            return _merge_candles(rows)
        raise
    provenance.append(intraday["sha256"])
    audit["intraday_overlay"] = "UPSTOX_INTRADAY"
    audit["intraday_provider_call_made"] = 1
    return _merge_candles(rows, intraday["payload"]["data"]["candles"])


def _historical_window(client, cache_reader, cache_mode, timeframe, unit, interval, start, end):
    """Return historical candles plus auditable cache-source metadata."""
    direct = lambda a, b: client.historical(NIFTY, unit, interval, a, b)
    audit = {
        "source": "UPSTOX_DIRECT",
        "cache_document_sha": None,
        "dataset_sha": None,
        "latest_cached_timestamp": None,
        "provider_calls_avoided": 0,
        "tail_calls_made": 0,
        "shadow_exact_match": None,
    }
    if cache_mode == "OFF" or cache_reader is None:
        env = direct(start, end)
        return env["payload"]["data"]["candles"], [env["sha256"]], audit

    try:
        cached = cache_reader.read_nifty_window(timeframe, start, end)
        audit.update({
            "cache_document_sha": cached.get("document_sha256"),
            "dataset_sha": cached.get("dataset_sha256"),
            "latest_cached_timestamp": cached.get("latest_cached_timestamp"),
        })
    except Exception as error:
        env = direct(start, end)
        audit.update({"source": "FALLBACK", "fallback_reason": f"CACHE_INTEGRITY:{type(error).__name__}"})
        return env["payload"]["data"]["candles"], [env["sha256"]], audit

    if cache_mode == "SHADOW":
        env = direct(start, end)
        direct_rows = _merge_candles(env["payload"]["data"]["candles"])
        cache_rows = _merge_candles(cached["rows"])
        exact = cached["covers_required_window"] and _series_digest(direct_rows) == _series_digest(cache_rows)
        audit.update({"source": "CACHE_SHADOW", "shadow_exact_match": exact})
        if not exact:
            raise DataArchitectureError(f"production cache shadow mismatch for {timeframe}")
        return env["payload"]["data"]["candles"], [env["sha256"]], audit

    if cache_mode != "CACHE_FIRST":
        raise DataArchitectureError("production historical cache mode invalid")

    if cached["covers_required_window"]:
        audit.update({"source": "CACHE", "provider_calls_avoided": 1})
        return cached["rows"], [cached["document_sha256"], cached["dataset_sha256"]], audit

    earliest = cached.get("earliest_session_date")
    latest = cached.get("latest_session_date")
    if earliest is not None and latest is not None and date.fromisoformat(earliest) <= start and date.fromisoformat(latest) < end:
        tail_start = date.fromisoformat(latest)
        env = direct(tail_start, end)
        reconciled = reconcile_candles(
            cached["records"], env["payload"]["data"]["candles"], env
        )
        rows = [
            list(record["candle"])
            for record in reconciled["records"]
            if start <= _stamp(record["timestamp"]).astimezone(IST).date() <= end
        ]
        audit.update({
            "source": "UPSTOX_TAIL",
            "tail_calls_made": 1,
            "tail_duplicate_count": reconciled["duplicate_count"],
            "tail_correction_count": reconciled["correction_count"],
            "tail_reconciled_dataset_sha": reconciled["dataset_sha256"],
        })
        return rows, [cached["document_sha256"], cached["dataset_sha256"], env["sha256"]], audit

    env = direct(start, end)
    audit.update({"source": "FALLBACK", "fallback_reason": "CACHE_WINDOW_INCOMPLETE"})
    return env["payload"]["data"]["candles"], [env["sha256"]], audit


def _subject(subject_id, name, *, instrument_key=None, segment=None):
    result = {"kind": "MARKET_INSTRUMENT", "id": subject_id, "name": name}
    if instrument_key:
        result["instrument_key"] = instrument_key
    if segment:
        result["segment"] = segment
    return result


def _record(*, variable_id, subject, metric, values, timeframe, provider_timestamp,
            acquisition_timestamp, freshness, source_reference, source_sha256,
            provider_latency_seconds=None):
    return build_record(
        provider_id=PROVIDER,
        source_semantic=SOURCE,
        variable_id=variable_id,
        consumer="5DR",
        subject=subject,
        metric=metric,
        values=values,
        timeframe=timeframe,
        provider_timestamp=provider_timestamp,
        acquisition_timestamp=acquisition_timestamp,
        freshness_status=freshness,
        source_reference=source_reference,
        source_sha256=source_sha256,
        provider_latency_seconds=provider_latency_seconds,
    )


def _latest_institutional(data):
    if not isinstance(data, dict):
        raise DataArchitectureError("institutional payload invalid")
    out = {}
    for key, rows in data.items():
        if not isinstance(rows, list) or not rows:
            raise DataArchitectureError("institutional rows missing")
        valid = [row for row in rows if isinstance(row, dict) and isinstance(row.get("time_stamp"), int)]
        if not valid:
            raise DataArchitectureError("institutional timestamp missing")
        out[key] = max(valid, key=lambda row: row["time_stamp"])
    return out


def _bounded_web_preview(item, word_limit=20):
    summary = item.get("fact_summary", "")
    excerpt = summary.split("source_excerpt=", 1)[-1]
    return " ".join(excerpt.split()[:word_limit])


def _analytics_summary(data):
    if not isinstance(data, dict):
        return {"fields": []}
    out = {"fields": sorted(str(key) for key in data)}
    for field in ("total_puts", "total_calls", "pcr", "max_pain", "instrument_key", "expiry"):
        if field in data:
            out[field] = data[field]
    insights = data.get("insights")
    if isinstance(insights, list):
        out["insights_preview"] = insights[:5]
    rows = data.get("call_put_oi_data_list")
    if isinstance(rows, list) and rows:
        call_rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("call_oi"), (int, float))]
        put_rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get("put_oi"), (int, float))]
        if call_rows:
            top = max(call_rows, key=lambda row: row["call_oi"])
            out["top_call_oi"] = {"strike_price": top.get("strike_price"), "call_oi": top.get("call_oi")}
        if put_rows:
            top = max(put_rows, key=lambda row: row["put_oi"])
            out["top_put_oi"] = {"strike_price": top.get("strike_price"), "put_oi": top.get("put_oi")}
    return out


def build_public_judgment_summary(bundle):
    if bundle.get("status") != "READY":
        raise DataArchitectureError("cannot summarize blocked live bundle")
    by_var = {record["variable_id"]: record for record in bundle["quantitative_records"]}
    chart = bundle["derived_chart_evidence"]
    web = bundle["external_evidence"]
    return {
        "bundle_sha256": bundle["bundle_sha256"],
        "frozen_at": bundle["frozen_at"],
        "status": bundle["status"],
        "nifty": by_var["NIFTY_PRICE_CANDLES"]["values"],
        "india_vix": by_var["INDIA_VIX"]["values"],
        "nifty_futures": by_var["NIFTY_FUTURES"]["values"],
        "option_chain": by_var["NIFTY_OPTION_CHAIN"]["values"],
        "derivative_analytics": by_var["NIFTY_DERIVATIVE_ANALYTICS"]["values"]["summary"],
        "heavyweights": by_var["NIFTY_HEAVYWEIGHTS"]["values"],
        "sectors": by_var["NIFTY_SECTOR_INDICES"]["values"],
        "fii_dii_cash": by_var["FII_DII_CASH"]["values"],
        "fii_index_derivatives": by_var["FII_INDEX_DERIVATIVES"]["values"],
        "global_risk": by_var["GLOBAL_RISK_INDICES"]["values"],
        "crude_usdinr": by_var["CRUDE_USDINR"]["values"],
        "chart": {
            "directional_alignment_excluding_5m": chart["directional_alignment_excluding_5m"],
            "timeframes": {
                tf: {
                    "latest_close": evidence["latest_close"],
                    "trend_structure": evidence["trend_structure"],
                    "range_event": evidence["range_event"],
                    "failed_breakout": evidence["failed_breakout"],
                    "recent_gaps": evidence["recent_gaps"],
                    "volume_confirmation": evidence["volume_confirmation"],
                }
                for tf, evidence in chart["timeframes"].items()
            },
        },
        "web_context": [
            {
                "category": item["category"],
                "authority": item["authority"],
                "source_reference": item["source_reference"],
                "research_sha256": item["research_sha256"],
                "preview_max_20_words": _bounded_web_preview(item),
            }
            for item in web
        ],
        "side_effects": {
            "forecast_released": False,
            "production_5dr_write_enabled": False,
            "lifecycle_write_enabled": False,
            "trading_enabled": False,
            "canonical_integration_enabled": False,
        },
    }


def build_live_shadow_bundle(token):
    if not isinstance(token, str) or not token.strip():
        raise PipelineError("UPSTOX_ANALYTICS_TOKEN is missing")
    now_ist = datetime.now(IST)
    today = now_ist.date()
    frozen_at = datetime.now(timezone.utc)

    legacy = ReadOnlyClient(token, opener=CurlOpener())
    contracts = legacy.contracts()
    contract_rows = contracts["payload"]["data"]
    expiries = sorted({
        row["expiry"] for row in contract_rows
        if isinstance(row, dict) and row.get("underlying_key") == NIFTY
        and isinstance(row.get("expiry"), str) and date.fromisoformat(row["expiry"]) >= today
    })
    market_status = get_nfo_market_status(token)
    expiry = select_session_valid_expiry(expiries, today, market_status["status"])

    catalogs = PublicInstrumentCatalog()
    global_master = catalogs.global_instruments()
    nse_master = catalogs.nse_instruments()
    globals_by_id = resolve_global_instruments(global_master["records"])
    future = resolve_nearest_nifty_future(nse_master["records"], today)
    core_universe = build_core_5dr_universe(globals_by_id, future)
    client = QuantReadOnlyClient(token, core_universe, opener=CurlOpener())

    domestic = client.full_quotes([NIFTY, INDIA_VIX, future["instrument_key"]])
    domestic_map = _quote_map(domestic)
    nifty_quote = _quote_snapshot(domestic_map[NIFTY])
    vix_quote = _quote_snapshot(domestic_map[INDIA_VIX])
    future_quote = _quote_snapshot(domestic_map[future["instrument_key"]])
    for snapshot in (nifty_quote, vix_quote, future_quote):
        _require_recent(snapshot["timestamp"], frozen_at)

    history_cfg = {
        "5m": ("minutes", 5, 4),
        "15m": ("minutes", 15, 8),
        "30m": ("minutes", 30, 15),
        "1h": ("hours", 1, 30),
        "1d": ("days", 1, 120),
    }
    cache_mode = os.environ.get("FIVE_DR_HISTORICAL_CACHE_MODE", "OFF").strip().upper()
    if cache_mode not in {"OFF", "SHADOW", "CACHE_FIRST"}:
        raise DataArchitectureError("production historical cache mode invalid")
    cache_reader = None
    if cache_mode != "OFF":
        cache_reader = build_reader_from_database_url(os.environ.get("DATABASE_URL", ""))

    source_series = {}
    series_provenance = {}
    cache_audit = {}
    for timeframe, (unit, interval, lookback_days) in history_cfg.items():
        end = today - timedelta(days=1)
        start = today - timedelta(days=lookback_days)
        rows, provenance, history_audit = _historical_window(
            client, cache_reader, cache_mode, timeframe, unit, interval, start, end
        )
        cache_audit[timeframe] = history_audit
        if timeframe != "1d":
            rows = _merge_session_intraday(
                rows,
                client,
                market_status["status"],
                unit,
                interval,
                provenance,
                history_audit,
            )
        else:
            rows = _merge_candles(rows)
        source_series[timeframe] = rows
        series_provenance[timeframe] = {
            "source_sha256": _sha(*provenance),
            "series_sha256": _series_digest(rows),
            "bar_count": len(rows),
        }

    chart = derive_multi_timeframe_evidence(source_series)
    chart["source_series"] = source_series
    chart["source_series_provenance"] = series_provenance
    chart["calculation_version"] = "5dr-derived-chart-evidence-v1"

    intraday_1m = legacy.intraday()
    chain = legacy.chain(expiry)
    sanitized = sanitize_live_envelopes(contracts, intraday_1m, chain, today, selected_expiry=expiry)
    option_keys = []
    for strike in sanitized["sample_strikes"]:
        option_keys.extend((strike["CE"]["instrument_key"], strike["PE"]["instrument_key"]))
    option_client = QuantReadOnlyClient(token, set(option_keys), opener=CurlOpener())
    option_quotes = option_client.full_quotes(option_keys)
    option_map = _quote_map(option_quotes)
    option_snapshot_times = []
    option_sample = []
    for strike in sanitized["sample_strikes"]:
        row = {"strike": strike["strike"]}
        for side in ("CE", "PE"):
            key = strike[side]["instrument_key"]
            snap = _quote_snapshot(option_map[key])
            _require_recent(snap["timestamp"], frozen_at)
            option_snapshot_times.append(_stamp(snap["timestamp"]))
            row[side] = {"instrument_key": key, "trading_symbol": strike[side]["trading_symbol"], **snap}
        option_sample.append(row)

    analytics = {}
    analytics_envs = []
    for name in ("oi", "change_oi", "pcr", "max_pain"):
        kwargs = {"expiry": expiry, "date_value": today.isoformat()}
        if name == "change_oi":
            kwargs["interval"] = 1
        elif name in {"pcr", "max_pain"}:
            kwargs["bucket_interval"] = 60
        env = client.option_analytics(name, **kwargs)
        analytics[name] = env["payload"]["data"]
        analytics_envs.append(env)

    fii = client.institutional("fii", ["NSE_EQ|CASH", "NSE_FO|INDEX_FUTURES", "NSE_FO|INDEX_OPTIONS"])
    dii = client.institutional("dii", "NSE_EQ|CASH")
    fii_latest = _latest_institutional(fii["payload"]["data"])
    dii_latest = _latest_institutional(dii["payload"]["data"])

    participation = approved_participation_universe()
    participation_keys = list(participation.heavyweight_keys + participation.sector_index_keys)
    participation_client = QuantReadOnlyClient(token, set(participation_keys), opener=CurlOpener())
    participation_env = participation_client.full_quotes(participation_keys)
    participation_map = _quote_map(participation_env)
    heavyweight_values, sector_values = {}, {}
    participation_times = []
    for key in participation.heavyweight_keys:
        snap = _quote_snapshot(participation_map[key])
        _require_recent(snap["timestamp"], frozen_at)
        participation_times.append(_stamp(snap["timestamp"]))
        heavyweight_values[key] = snap
    for key in participation.sector_index_keys:
        snap = _quote_snapshot(participation_map[key])
        _require_recent(snap["timestamp"], frozen_at)
        participation_times.append(_stamp(snap["timestamp"]))
        sector_values[key] = snap

    global_values = {}
    global_envs = {}
    for target, identity in sorted(globals_by_id.items()):
        key = identity["instrument_key"]
        if identity["segment"] == "GLOBAL_INDEX":
            env = client.full_quotes([key])
            snap = _quote_snapshot(_quote_map(env)[key])
        else:
            env = client.intraday(key, "minutes", 1)
            latest = max(env["payload"]["data"]["candles"], key=lambda row: _stamp(row[0]))
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

    risk_targets = ("gift_nifty", "sp500", "dow_jones", "us_tech_100", "nikkei_225", "hang_seng", "dax", "ftse_100")
    macro_targets = ("brent", "wti", "usd_inr")

    quantitative = []
    nifty_source_sha = _sha(domestic["sha256"], *(item["source_sha256"] for item in series_provenance.values()))
    quantitative.append(_record(
        variable_id="NIFTY_PRICE_CANDLES",
        subject=_subject("NIFTY_50", "NIFTY 50", instrument_key=NIFTY, segment="NSE_INDEX"),
        metric="spot_and_multitimeframe_ohlc",
        values={
            "spot": nifty_quote,
            "series": series_provenance,
            "latest_by_timeframe": {tf: {"timestamp": rows[-1][0], "close": rows[-1][4]} for tf, rows in source_series.items()},
        },
        timeframe="MULTI",
        provider_timestamp=nifty_quote["timestamp"],
        acquisition_timestamp=frozen_at,
        freshness="LIVE",
        source_reference="UPSTOX_COMPOSITE:NIFTY_PRICE_CANDLES",
        source_sha256=nifty_source_sha,
    ))
    quantitative.append(_record(
        variable_id="INDIA_VIX",
        subject=_subject("INDIA_VIX", "India VIX", instrument_key=INDIA_VIX, segment="NSE_INDEX"),
        metric="quote",
        values=vix_quote,
        timeframe="quote",
        provider_timestamp=vix_quote["timestamp"],
        acquisition_timestamp=frozen_at,
        freshness="LIVE",
        source_reference=domestic["source_path"],
        source_sha256=domestic["sha256"],
    ))
    basis = float(future_quote["last_price"]) - float(nifty_quote["last_price"])
    quantitative.append(_record(
        variable_id="NIFTY_FUTURES",
        subject=_subject("NIFTY_FUTURE", future["trading_symbol"], instrument_key=future["instrument_key"], segment="NSE_FO"),
        metric="quote_basis_volume_oi",
        values={
            "future": future_quote,
            "spot_last_price": nifty_quote["last_price"],
            "basis_points": round(basis, 6),
            "basis_pct_of_spot": round(100.0 * basis / float(nifty_quote["last_price"]), 6),
            "expiry": future["expiry"],
        },
        timeframe="quote",
        provider_timestamp=future_quote["timestamp"],
        acquisition_timestamp=frozen_at,
        freshness="LIVE",
        source_reference=domestic["source_path"],
        source_sha256=domestic["sha256"],
    ))
    quantitative.append(_record(
        variable_id="NIFTY_OPTION_CONTRACTS",
        subject=_subject("NIFTY_OPTION_CONTRACTS", "NIFTY option contracts", instrument_key=NIFTY, segment="NSE_FO"),
        metric="selected_expiry_and_exact_sample_contracts",
        values={
            "selected_expiry": expiry,
            "available_expiries": sanitized["available_expiries"],
            "sample_contracts": [
                {"strike": row["strike"], "CE": {"instrument_key": row["CE"]["instrument_key"], "trading_symbol": row["CE"]["trading_symbol"]}, "PE": {"instrument_key": row["PE"]["instrument_key"], "trading_symbol": row["PE"]["trading_symbol"]}}
                for row in option_sample
            ],
        },
        timeframe="reference",
        provider_timestamp=None,
        acquisition_timestamp=frozen_at,
        freshness="HISTORICAL",
        source_reference=contracts["source_path"],
        source_sha256=contracts["sha256"],
    ))
    option_provider_timestamp = min(option_snapshot_times).isoformat()
    quantitative.append(_record(
        variable_id="NIFTY_OPTION_CHAIN",
        subject=_subject("NIFTY_OPTION_CHAIN", "NIFTY option chain", instrument_key=NIFTY, segment="NSE_FO"),
        metric="atm_plus_minus_two_live_quotes",
        values={"selected_expiry": expiry, "underlying_spot_price": sanitized["underlying_spot_price"], "sample_strikes": option_sample},
        timeframe="quote",
        provider_timestamp=option_provider_timestamp,
        acquisition_timestamp=frozen_at,
        freshness="LIVE",
        source_reference="UPSTOX_COMPOSITE:OPTION_CHAIN_AND_EXACT_QUOTES",
        source_sha256=_sha(chain["sha256"], option_quotes["sha256"]),
    ))
    quantitative.append(_record(
        variable_id="NIFTY_DERIVATIVE_ANALYTICS",
        subject=_subject("NIFTY_DERIVATIVE_ANALYTICS", "NIFTY derivative analytics", instrument_key=NIFTY, segment="NSE_FO"),
        metric="oi_change_oi_pcr_max_pain",
        values={
            "selected_expiry": expiry,
            "analytics": analytics,
            "summary": {name: _analytics_summary(data) for name, data in analytics.items()},
            "timestamp_semantics": "Provider analytics payloads contain no uniform row timestamp; retained as acquisition-current but freshness-labeled HISTORICAL rather than fabricating provider time.",
        },
        timeframe="mixed",
        provider_timestamp=None,
        acquisition_timestamp=frozen_at,
        freshness="HISTORICAL",
        source_reference="UPSTOX_COMPOSITE:NIFTY_DERIVATIVE_ANALYTICS",
        source_sha256=_sha(*(env["sha256"] for env in analytics_envs)),
    ))
    participation_provider_timestamp = min(participation_times).isoformat()
    quantitative.append(_record(
        variable_id="NIFTY_HEAVYWEIGHTS",
        subject=_subject("NIFTY_HEAVYWEIGHTS", "Approved NIFTY heavyweight set", segment="NSE_EQ"),
        metric="approved_constituent_live_quotes",
        values={"approval_ref": participation.approval_ref, "instruments": heavyweight_values},
        timeframe="quote",
        provider_timestamp=participation_provider_timestamp,
        acquisition_timestamp=frozen_at,
        freshness="LIVE",
        source_reference=participation_env["source_path"],
        source_sha256=participation_env["sha256"],
    ))
    quantitative.append(_record(
        variable_id="NIFTY_SECTOR_INDICES",
        subject=_subject("NIFTY_SECTOR_INDICES", "Approved NIFTY sector index set", segment="NSE_INDEX"),
        metric="approved_sector_live_quotes",
        values={"approval_ref": participation.approval_ref, "instruments": sector_values},
        timeframe="quote",
        provider_timestamp=participation_provider_timestamp,
        acquisition_timestamp=frozen_at,
        freshness="LIVE",
        source_reference=participation_env["source_path"],
        source_sha256=participation_env["sha256"],
    ))
    quantitative.append(_record(
        variable_id="FII_DII_CASH",
        subject={"kind": "INSTITUTIONAL", "id": "FII_DII_CASH", "name": "FII/FPI and DII cash"},
        metric="latest_daily_cash_rows",
        values={"fii": fii_latest["NSE_EQ|CASH"], "dii": dii_latest["NSE_EQ|CASH"]},
        timeframe="1d",
        provider_timestamp=None,
        acquisition_timestamp=frozen_at,
        freshness="HISTORICAL",
        source_reference="UPSTOX_COMPOSITE:FII_DII_CASH",
        source_sha256=_sha(fii["sha256"], dii["sha256"]),
    ))
    quantitative.append(_record(
        variable_id="FII_INDEX_DERIVATIVES",
        subject={"kind": "INSTITUTIONAL", "id": "FII_INDEX_DERIVATIVES", "name": "FII index derivatives"},
        metric="latest_daily_index_futures_options_rows",
        values={"index_futures": fii_latest["NSE_FO|INDEX_FUTURES"], "index_options": fii_latest["NSE_FO|INDEX_OPTIONS"]},
        timeframe="1d",
        provider_timestamp=None,
        acquisition_timestamp=frozen_at,
        freshness="HISTORICAL",
        source_reference=fii["source_path"],
        source_sha256=fii["sha256"],
    ))

    def global_record(variable_id, targets, subject_id, name):
        values = {target: global_values[target] for target in targets}
        times = [_stamp(values[target]["timestamp"]) for target in targets]
        max_latency = max(values[target]["provider_latency_seconds"] for target in targets)
        age = max((frozen_at - timestamp).total_seconds() for timestamp in times)
        if age > max_latency + 1800:
            freshness = "HISTORICAL"
            latency = None
        else:
            freshness = {20: "DELAYED_20S", 120: "DELAYED_120S", 900: "DELAYED_15M"}[max_latency]
            latency = max_latency
        return _record(
            variable_id=variable_id,
            subject=_subject(subject_id, name),
            metric="approved_global_market_snapshots",
            values={"instruments": values, "aggregate_timestamp_policy": "earliest constituent provider timestamp; individual timestamps preserved"},
            timeframe="quote_or_1m",
            provider_timestamp=min(times).isoformat(),
            acquisition_timestamp=frozen_at,
            freshness=freshness,
            source_reference=f"UPSTOX_COMPOSITE:{variable_id}",
            source_sha256=_sha(*(global_envs[target]["sha256"] for target in targets)),
            provider_latency_seconds=latency,
        )

    quantitative.append(global_record("GLOBAL_RISK_INDICES", risk_targets, "GLOBAL_RISK_INDICES", "Approved global risk indices"))
    quantitative.append(global_record("CRUDE_USDINR", macro_targets, "CRUDE_USDINR", "Crude and USD/INR"))

    web = collect_live_web_context()
    freeze_final = datetime.now(timezone.utc)
    run_id = f"V223-SHADOW-{freeze_final.strftime('%Y%m%dT%H%M%SZ')}"
    bundle = build_evidence_bundle(
        run_id=run_id,
        frozen_at=freeze_final,
        quantitative_records=quantitative,
        chart_evidence=chart,
        external_evidence=web["items"],
        required_external_categories={"DXY_RATES", "MACRO_EVENTS_GEOPOLITICS"},
        require_screenshot_free=True,
    )
    bundle["runtime_context"] = {
        "nfo_session": market_status["status"],
        "selected_nifty_expiry": expiry,
        "participation_approval_ref": participation.approval_ref,
        "source_semantic": SOURCE,
        "screenshot_required": False,
        "forecast_release_enabled": False,
        "production_5dr_write_enabled": False,
        "lifecycle_write_enabled": False,
        "trading_enabled": False,
        "canonical_integration_enabled": False,
        "methodology_changed": False,
        "historical_cache_mode": cache_mode,
        "historical_cache_audit": cache_audit,
        "historical_provider_calls_avoided": sum(row["provider_calls_avoided"] for row in cache_audit.values()),
        "historical_tail_calls_made": sum(row["tail_calls_made"] for row in cache_audit.values()),
    }
    # runtime_context is part of the frozen object, so recompute the bundle digest.
    base = dict(bundle)
    base.pop("bundle_sha256", None)
    bundle["bundle_sha256"] = hashlib.sha256(json.dumps(base, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return bundle
