"""Provider-neutral EDGE_STOCK market/fundamental acquisition primitives.

This module converts read-only provider payloads into normalized EDGE_STOCK evidence
records. It does not perform scoring, probability estimation, recommendation logic,
canonical persistence, lifecycle writes, account actions or trading.
"""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.edge_stock_bundle import build_edge_stock_bundle
from experiments.edge_stock_identity import resolve_nse_equity, resolve_stock_fo_identity
from experiments.edge_stock_upstox import EdgeStockReadOnlyClient
from experiments.upstox_catalog import PublicInstrumentCatalog


def _sha(*values):
    clean = [value for value in values if isinstance(value, str) and value]
    if not clean:
        raise DataArchitectureError("EDGE_STOCK source digest missing")
    return hashlib.sha256("|".join(sorted(clean)).encode()).hexdigest()


def _stamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    if not isinstance(value, str) or not value:
        raise DataArchitectureError("EDGE_STOCK timestamp missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise DataArchitectureError("EDGE_STOCK timestamp invalid") from None
    if parsed.tzinfo is None:
        raise DataArchitectureError("EDGE_STOCK timestamp naive")
    return parsed.astimezone(timezone.utc)


def _record(stock, variable_id, *, metric, values, timeframe, provider_timestamp,
            acquisition_timestamp, source_reference, source_sha256,
            freshness_status="LIVE"):
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id=variable_id,
        consumer="EDGE_STOCK",
        subject=stock,
        metric=metric,
        values=values,
        timeframe=timeframe,
        provider_timestamp=provider_timestamp,
        acquisition_timestamp=acquisition_timestamp,
        freshness_status=freshness_status,
        source_reference=source_reference,
        source_sha256=source_sha256,
    )


def _quote_snapshot(envelope, instrument_key):
    data = envelope["payload"]["data"]
    rows = [
        row for row in data.values()
        if isinstance(row, dict) and row.get("instrument_token") == instrument_key
    ]
    if len(rows) != 1:
        raise DataArchitectureError("EDGE_STOCK quote identity unresolved")
    row = rows[0]
    return {
        "last_price": row.get("last_price"),
        "volume": row.get("volume"),
        "open_interest": row.get("oi"),
        "average_price": row.get("average_price"),
        "total_buy_quantity": row.get("total_buy_quantity"),
        "total_sell_quantity": row.get("total_sell_quantity"),
        "ohlc": row.get("ohlc"),
        "timestamp": _stamp(row.get("timestamp")).isoformat(),
    }


def _candle_rows(envelope):
    rows = envelope["payload"]["data"].get("candles")
    if not isinstance(rows, list) or not rows:
        raise DataArchitectureError("EDGE_STOCK candle data missing")
    return rows


def derive_relative_strength(stock_daily_rows, benchmark_daily_rows):
    def closes(rows):
        out = {}
        for row in rows:
            if not isinstance(row, list) or len(row) != 7:
                raise DataArchitectureError("relative-strength candle invalid")
            stamp = _stamp(row[0]).date().isoformat()
            close = row[4]
            if not isinstance(close, (int, float)) or isinstance(close, bool) or close <= 0:
                raise DataArchitectureError("relative-strength close invalid")
            out[stamp] = float(close)
        return out

    stock = closes(stock_daily_rows)
    bench = closes(benchmark_daily_rows)
    common = sorted(set(stock) & set(bench))
    if len(common) < 2:
        raise DataArchitectureError("relative-strength overlap insufficient")
    first, last = common[0], common[-1]
    stock_return = stock[last] / stock[first] - 1.0
    bench_return = bench[last] / bench[first] - 1.0
    return {
        "first_date": first,
        "last_date": last,
        "stock_return_pct": round(stock_return * 100.0, 6),
        "benchmark_return_pct": round(bench_return * 100.0, 6),
        "relative_strength_pct_points": round((stock_return - bench_return) * 100.0, 6),
        "observations": len(common),
    }


def normalize_option_chain(chain_envelope, *, spot_price):
    rows = chain_envelope["payload"]["data"]
    result = []
    for row in rows:
        strike = row.get("strike_price")
        if not isinstance(strike, (int, float)) or isinstance(strike, bool):
            continue
        item = {
            "strike": strike,
            "expiry": row.get("expiry"),
            "pcr": row.get("pcr"),
        }
        for label, field in (("CE", "call_options"), ("PE", "put_options")):
            leg = row.get(field) or {}
            market = leg.get("market_data") or {}
            greeks = leg.get("option_greeks") or {}
            bid = market.get("bid_price")
            ask = market.get("ask_price")
            spread = None
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and ask >= bid:
                spread = round(float(ask) - float(bid), 6)
            item[label] = {
                "instrument_key": leg.get("instrument_key"),
                "ltp": market.get("ltp"),
                "volume": market.get("volume"),
                "oi": market.get("oi"),
                "prev_oi": market.get("prev_oi"),
                "change_oi": (
                    market.get("oi") - market.get("prev_oi")
                    if isinstance(market.get("oi"), (int, float))
                    and isinstance(market.get("prev_oi"), (int, float))
                    else None
                ),
                "bid_price": bid,
                "bid_qty": market.get("bid_qty"),
                "ask_price": ask,
                "ask_qty": market.get("ask_qty"),
                "bid_ask_spread": spread,
                "iv": greeks.get("iv"),
                "delta": greeks.get("delta"),
                "gamma": greeks.get("gamma"),
                "theta": greeks.get("theta"),
                "vega": greeks.get("vega"),
            }
        result.append(item)
    if not result:
        raise DataArchitectureError("normalized stock option chain empty")
    result.sort(key=lambda item: item["strike"])
    return {
        "underlying_spot_price": spot_price,
        "strikes": result,
        "liquidity_fields_preserved": True,
        "greeks_preserved_where_available": True,
    }


def acquire_upstox_stock_core(token, *, symbol, benchmark_identity, as_of=None):
    as_of = as_of or datetime.now(timezone.utc)
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise DataArchitectureError("EDGE_STOCK as_of must be timezone-aware")
    today = as_of.date()

    catalog = PublicInstrumentCatalog()
    nse_master = catalog.nse_instruments()
    stock = resolve_nse_equity(nse_master["records"], symbol=symbol)
    fo = resolve_stock_fo_identity(nse_master["records"], stock, as_of=today)

    if not isinstance(benchmark_identity, dict):
        raise DataArchitectureError("EDGE_STOCK benchmark identity required")
    benchmark_key = benchmark_identity.get("instrument_key")
    if not isinstance(benchmark_key, str) or not benchmark_key:
        raise DataArchitectureError("EDGE_STOCK benchmark instrument key invalid")

    approved = {stock["instrument_key"], benchmark_key}
    client = EdgeStockReadOnlyClient(token, approved_instruments=approved)
    quote_env = client.full_quotes([stock["instrument_key"], benchmark_key])
    stock_quote = _quote_snapshot(quote_env, stock["instrument_key"])

    history_cfg = {
        "15m": ("minutes", 15, 45),
        "30m": ("minutes", 30, 90),
        "1h": ("hours", 1, 180),
        "1d": ("days", 1, 730),
    }
    series = {}
    series_sources = []
    for timeframe, (unit, interval, lookback) in history_cfg.items():
        env = client.historical(
            stock["instrument_key"], unit, interval,
            today - timedelta(days=lookback - 1), today,
        )
        series[timeframe] = _candle_rows(env)
        series_sources.append(env["sha256"])

    benchmark_env = client.historical(
        benchmark_key, "days", 1,
        today - timedelta(days=179), today,
    )
    relative = derive_relative_strength(series["1d"], _candle_rows(benchmark_env))

    fundamentals = {}
    fundamental_sources = []
    for name, params in (
        ("profile", {}),
        ("income_statement", {"type": "consolidated", "time_period": "quarterly", "fs": True}),
        ("balance_sheet", {"type": "consolidated", "fs": True}),
        ("cash_flow", {"type": "consolidated", "fs": True}),
        ("key_ratios", {}),
    ):
        env = client.fundamental(name, stock["isin"], **params)
        fundamentals[name] = env["payload"]["data"]
        fundamental_sources.append(env["sha256"])

    share = client.fundamental("share_holdings", stock["isin"])
    peers = client.fundamental("competitors", stock["isin"])
    corp = client.fundamental("corporate_actions", stock["isin"])
    news = client.news(stock["instrument_key"])

    records = [
        _record(
            stock, "STOCK_PRICE_CANDLES",
            metric="quote_and_multitimeframe_ohlcv",
            values={"quote": stock_quote, "series": series},
            timeframe="MULTI",
            provider_timestamp=stock_quote["timestamp"],
            acquisition_timestamp=as_of,
            source_reference="UPSTOX_COMPOSITE:EDGE_STOCK_PRICE",
            source_sha256=_sha(quote_env["sha256"], *series_sources),
        ),
        _record(
            stock, "STOCK_RELATIVE_STRENGTH",
            metric="stock_vs_benchmark_daily_return",
            values={"benchmark": benchmark_identity, **relative},
            timeframe="1d",
            provider_timestamp=as_of,
            acquisition_timestamp=as_of,
            source_reference="UPSTOX_COMPOSITE:EDGE_STOCK_RELATIVE_STRENGTH",
            source_sha256=_sha(series_sources[-1], benchmark_env["sha256"]),
        ),
        _record(
            stock, "STOCK_FUNDAMENTALS",
            metric="profile_financial_statements_and_key_ratios",
            values=fundamentals,
            timeframe="fundamental",
            provider_timestamp=None,
            acquisition_timestamp=as_of,
            freshness_status="HISTORICAL",
            source_reference="UPSTOX_COMPOSITE:EDGE_STOCK_FUNDAMENTALS",
            source_sha256=_sha(*fundamental_sources),
        ),
        _record(
            stock, "STOCK_SHAREHOLDING",
            metric="quarterly_shareholding_history",
            values={"share_holdings": share["payload"]["data"]},
            timeframe="quarterly",
            provider_timestamp=None,
            acquisition_timestamp=as_of,
            freshness_status="HISTORICAL",
            source_reference=share["source_path"],
            source_sha256=share["sha256"],
        ),
        _record(
            stock, "STOCK_PEERS",
            metric="provider_competitor_set",
            values={"competitors": peers["payload"]["data"]},
            timeframe="snapshot",
            provider_timestamp=None,
            acquisition_timestamp=as_of,
            freshness_status="HISTORICAL",
            source_reference=peers["source_path"],
            source_sha256=peers["sha256"],
        ),
        _record(
            stock, "STOCK_CORPORATE_ACTIONS",
            metric="structured_corporate_actions",
            values={"corporate_actions": corp["payload"]["data"]},
            timeframe="event",
            provider_timestamp=None,
            acquisition_timestamp=as_of,
            freshness_status="HISTORICAL",
            source_reference=corp["source_path"],
            source_sha256=corp["sha256"],
        ),
        _record(
            stock, "STOCK_NEWS_RECENT",
            metric="provider_news_last_7_days",
            values={"news": news["payload"]["data"]},
            timeframe="7d",
            provider_timestamp=None,
            acquisition_timestamp=as_of,
            freshness_status="HISTORICAL",
            source_reference=news["source_path"],
            source_sha256=news["sha256"],
        ),
    ]

    if fo["fo_eligible"]:
        option_client = EdgeStockReadOnlyClient(
            token,
            approved_instruments={stock["instrument_key"]},
        )
        contracts = option_client.option_contracts(
            stock["instrument_key"],
            expiry_date=fo["nearest_expiry"],
        )
        chain = option_client.option_chain(
            stock["instrument_key"],
            fo["nearest_expiry"],
        )
        records.append(_record(
            stock, "STOCK_OPTIONS",
            metric="exact_expiry_chain_premium_oi_change_volume_depth_greeks",
            values={
                "fo_identity": fo,
                "contracts": contracts["payload"]["data"],
                "chain": normalize_option_chain(
                    chain,
                    spot_price=stock_quote["last_price"],
                ),
            },
            timeframe="quote",
            provider_timestamp=as_of,
            acquisition_timestamp=as_of,
            source_reference="UPSTOX_COMPOSITE:EDGE_STOCK_OPTIONS",
            source_sha256=_sha(contracts["sha256"], chain["sha256"]),
        ))

    return {
        "stock_identity": stock,
        "fo_identity": fo,
        "benchmark_identity": benchmark_identity,
        "records": records,
        "provider": "UPSTOX",
        "provider_neutral_output": True,
        "read_only": True,
        "methodology_applied": False,
        "trading_enabled": False,
    }
