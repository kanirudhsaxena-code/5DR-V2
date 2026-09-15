"""5DR-only quantitative evidence coverage map for the isolated Upstox experiment.

This module is declarative. It does not fetch data, score 5DR, write databases,
release forecasts, or perform any trading/account operation.
"""
from copy import deepcopy

from phase1.upstox import PipelineError

SCHEMA = "5dr-upstox-coverage-v1"
REQUIRED_FIELDS = {
    "id", "engine", "role", "5dr_input", "upstox_source", "instrument",
    "availability", "latency", "frequency", "freshness_rule",
    "fallback_requirement", "validation_state",
}


def _row(id, engine, role, input_name, source, instrument, availability,
         latency, frequency, freshness, fallback, validation):
    return {
        "id": id,
        "engine": engine,
        "role": role,
        "5dr_input": input_name,
        "upstox_source": source,
        "instrument": instrument,
        "availability": availability,
        "latency": latency,
        "frequency": frequency,
        "freshness_rule": freshness,
        "fallback_requirement": fallback,
        "validation_state": validation,
    }


ROWS = [
    _row("nifty_spot", "PVS/PVPO", "CORE", "NIFTY 50 spot/index level",
         "/v3/market-quote/ltp", "NSE_INDEX|Nifty 50", "PROVEN",
         "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Use authenticated receipt plus exchange/session freshness gate; fail closed when stale.",
         "SCREENSHOT_OR_WEB", "LIVE_PROVEN"),
    _row("nifty_intraday_1h", "PVS", "CORE", "NIFTY 1H OHLCV structure",
         "/v3/historical-candle/intraday/{instrument}/hours/1", "NSE_INDEX|Nifty 50",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Latest bar must match the requested market state and pass OHLC/timestamp validation.",
         "SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("nifty_intraday_30m", "PVS", "CORE", "NIFTY 30m OHLCV persistence",
         "/v3/historical-candle/intraday/{instrument}/minutes/30", "NSE_INDEX|Nifty 50",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Latest bar must match the requested market state and pass OHLC/timestamp validation.",
         "SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("nifty_intraday_15m", "PVS", "CORE", "NIFTY 15m OHLCV persistence",
         "/v3/historical-candle/intraday/{instrument}/minutes/15", "NSE_INDEX|Nifty 50",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Latest bar must match the requested market state and pass OHLC/timestamp validation.",
         "SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("nifty_intraday_5m", "EXECUTION_EDGE", "CORE", "NIFTY 5m execution context",
         "/v3/historical-candle/intraday/{instrument}/minutes/5", "NSE_INDEX|Nifty 50",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "WHEN_TRADEABILITY_ASSESSED",
         "Execution-only bar; never permitted to determine the five-day directional score.",
         "SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("nifty_daily", "PVS/LIFECYCLE/LEARNING", "CORE", "NIFTY daily/historical OHLCV and outcome closes",
         "/v3/historical-candle/{instrument}/days/1/{to}/{from}", "NSE_INDEX|Nifty 50",
         "PROVEN", "SESSION_FINAL", "EACH_5DR_RUN_AND_CHECKPOINT",
         "Completed daily bars only for outcome scoring; no future-bar leakage.",
         "WEB_RESEARCH", "LIVE_PROVEN"),
    _row("nifty_future_contract", "PVPO", "CORE", "Nearest valid NIFTY futures contract identity",
         "Upstox BOD instrument master", "NSE_FO FUT with underlying NSE_INDEX|Nifty 50",
         "SUPPORTED_UNPROVEN", "SESSION_METADATA", "DAILY_OR_EXPIRY_CHANGE",
         "Resolve exact underlying/type/expiry from current BOD master; never substitute another contract.",
         "WEB_RESEARCH_OR_SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("nifty_futures_basis", "PVPO", "CORE", "NIFTY futures price and spot premium/discount basis",
         "/v3/market-quote/quotes", "Resolved NIFTY future instrument_key",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Spot and future observations must be current enough for the same analytical cutoff.",
         "SCREENSHOT_OR_WEB", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("option_contracts", "PVPO/EXECUTION_EDGE", "CORE", "NIFTY option expiries, strikes and exact CE/PE identities",
         "/v2/option/contract", "NSE_INDEX|Nifty 50",
         "PROVEN", "SESSION_METADATA", "EACH_5DR_RUN",
         "Exact underlying, expiry, strike and CE/PE identity required; ambiguous/duplicate identity rejected.",
         "SCREENSHOT_OR_WEB", "LIVE_PROVEN"),
    _row("option_chain", "PVPO/EXECUTION_EDGE", "CORE", "Option LTP, OI, volume, bid/ask, previous OI, IV/Greeks where present",
         "/v2/option/chain", "NSE_INDEX|Nifty 50 + selected expiry",
         "PARTIALLY_PROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Exact expiry/strike/side identity; non-negative price/OI/volume; missing fields remain missing.",
         "SCREENSHOT_OR_WEB", "LTP_OI_VOLUME_LIVE_PROVEN_EXTENDED_FIELDS_UNPROVEN"),
    _row("change_oi", "PVPO", "CORE", "Strike-level change in OI / build-up and unwinding",
         "/v2/market/change-oi", "NSE_INDEX|Nifty 50 + selected expiry",
         "SUPPORTED_UNPROVEN", "SESSION_FINAL_OR_PROVIDER_BUCKET", "EACH_5DR_RUN_WHEN_AVAILABLE",
         "Requested date/interval must be explicit and source timestamp/bucket retained.",
         "SCREENSHOT_OR_WEB", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("pcr", "PVPO", "SUPPLEMENTAL", "Put-call ratio supporting derivative context",
         "/v2/market/pcr", "NSE_INDEX|Nifty 50 + selected expiry",
         "SUPPORTED_UNPROVEN", "SESSION_FINAL_OR_PROVIDER_BUCKET", "EACH_5DR_RUN_WHEN_AVAILABLE",
         "Retain requested date and bucket interval; never substitute PCR for core PVPO ordering.",
         "SCREENSHOT_OR_WEB", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("max_pain", "PVPO", "SUPPLEMENTAL", "Max Pain supporting derivative context",
         "/v2/market/max-pain", "NSE_INDEX|Nifty 50 + selected expiry",
         "SUPPORTED_UNPROVEN", "SESSION_FINAL_OR_PROVIDER_BUCKET", "EACH_5DR_RUN_WHEN_AVAILABLE",
         "Retain requested date/bucket; supporting evidence only, never a standalone direction signal.",
         "SCREENSHOT_OR_WEB", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("india_vix", "MACRO_CATALYSTS/EXECUTION_EDGE", "CORE", "India VIX",
         "/v3/market-quote/quotes and candle APIs", "NSE_INDEX|India VIX",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "Apply exchange/session freshness rules; stale VIX cannot be represented as current.",
         "WEB_RESEARCH", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("nifty_heavyweights", "PARTICIPATION", "CORE", "Top NIFTY heavyweight direction and volume",
         "/v3/market-quote/quotes and candle APIs", "5DR-supplied heavyweight instrument set",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "The data layer may resolve/fetch only the constituent set supplied by 5DR; it must not invent a new weighting methodology.",
         "WEB_RESEARCH_OR_SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("sector_leadership", "PARTICIPATION", "CORE", "Material NIFTY sector leadership/breadth",
         "/v3/market-quote/quotes and candle APIs", "5DR-supplied NSE sector-index instrument set",
         "SUPPORTED_UNPROVEN", "EXCHANGE_SNAPSHOT", "EACH_5DR_RUN",
         "The data layer fetches the approved sector set only; no autonomous sector-scoring changes.",
         "WEB_RESEARCH_OR_SCREENSHOT", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("fii_cash", "PARTICIPATION", "CORE", "FII/FPI NSE cash participation",
         "/v2/market/fii", "data_type=NSE_EQ|CASH; interval=1D",
         "SUPPORTED_UNPROVEN", "SESSION_FINAL", "DAILY_POST_PUBLICATION",
         "Use provider timestamp; current session is not inferred before provider publication.",
         "WEB_RESEARCH", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("dii_cash", "PARTICIPATION", "CORE", "DII NSE cash participation",
         "/v2/market/dii", "data_type=NSE_EQ|CASH; interval=1D",
         "SUPPORTED_UNPROVEN", "SESSION_FINAL", "DAILY_POST_PUBLICATION",
         "Use provider timestamp; current session is not inferred before provider publication.",
         "WEB_RESEARCH", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
    _row("fii_derivatives", "PVPO/PARTICIPATION", "SUPPLEMENTAL", "FII index-futures/options positioning",
         "/v2/market/fii", "NSE_FO|INDEX_FUTURES and NSE_FO|INDEX_OPTIONS; interval=1D",
         "SUPPORTED_UNPROVEN", "SESSION_FINAL", "DAILY_POST_PUBLICATION",
         "Use provider timestamp and retain long/short contract fields; contextual only unless canonical logic explicitly uses it.",
         "WEB_RESEARCH", "DOC_VERIFIED_NOT_LIVE_PROVEN"),
]

for gid, label in [
    ("gift_nifty", "GIFT NIFTY"),
    ("sp500", "S&P 500"),
    ("dow_jones", "DOW JONES"),
    ("us_tech_100", "US Tech 100"),
    ("nikkei_225", "NIKKEI 225"),
    ("hang_seng", "HANG SENG"),
    ("dax", "DAX"),
    ("ftse_100", "FTSE 100"),
    ("brent", "Oil (Brent)"),
    ("wti", "Oil (WTI)"),
    ("usd_inr", "USD INR"),
]:
    ROWS.append(_row(
        gid, "MACRO_CATALYSTS", "CORE", label,
        "Global Instruments master + /v3/market-quote/quotes and candle APIs",
        f"Exact GLOBAL instrument resolved by name={label}",
        "SUPPORTED_UNPROVEN", "PROVIDER_DECLARED_FROM_GLOBAL_MASTER", "PREOPEN_AND_EACH_5DR_RUN",
        "Read latency from the current Upstox Global Instruments master; classify only 20/120/900-second values; reject unknown/missing latency.",
        "WEB_RESEARCH", "DOC_VERIFIED_NOT_LIVE_PROVEN",
    ))

ROWS.extend([
    _row("dxy", "MACRO_CATALYSTS", "CORE", "US dollar index / DXY context",
         "No verified Upstox mapping in this audit", "N/A", "UPSTOX_UNVERIFIED",
         "UNAVAILABLE", "EACH_5DR_RUN", "No Upstox substitution without exact verified instrument identity.",
         "WEB_RESEARCH", "WEB_REQUIRED"),
    _row("rates", "MACRO_CATALYSTS", "CORE", "Global/India rates context",
         "No verified Upstox mapping sufficient for canonical macro interpretation", "N/A", "UPSTOX_UNVERIFIED",
         "UNAVAILABLE", "EACH_5DR_RUN", "Do not infer policy/rate context from unrelated instruments.",
         "WEB_RESEARCH", "WEB_REQUIRED"),
    _row("scheduled_macro", "MACRO_CATALYSTS", "CORE", "Fed/RBI/CPI/GDP/PCE and scheduled high-impact catalysts",
         "Not a market-price data function", "N/A", "NOT_APPLICABLE",
         "UNAVAILABLE", "EACH_5DR_RUN", "Requires current event/context research with publication timestamps.",
         "WEB_RESEARCH", "WEB_REQUIRED"),
    _row("geopolitics", "MACRO_CATALYSTS", "CORE", "Geopolitics, sanctions and commodity-shock transmission",
         "Not a structured Upstox market-price substitute", "N/A", "NOT_APPLICABLE",
         "UNAVAILABLE", "EACH_5DR_RUN", "Requires current qualitative/contextual evidence and independent verification.",
         "WEB_RESEARCH", "WEB_REQUIRED"),
    _row("option_lifecycle_prices", "LIFECYCLE/LEARNING", "CORE",
         "Issuance and later option premiums for recommendation reconciliation/MFE/MAE when verifiable",
         "Market quote + historical candle/expired-instrument capability to be proven", "Exact frozen recommendation instrument_key",
         "SUPPORTED_UNPROVEN", "CONTEXT_DEPENDENT", "EACH_RECONCILIATION",
         "Never guess entry/touch time/event ordering; unresolved path remains NOT_SCORABLE/ENTRY_NOT_VERIFIABLE.",
         "WEB_RESEARCH_OR_SCREENSHOT", "REQUIRES_LIVE_AND_HISTORICAL_PROOF"),
])


def validate_coverage_matrix(rows=None):
    rows = ROWS if rows is None else rows
    if not isinstance(rows, list) or not rows:
        raise PipelineError("Coverage matrix missing")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != REQUIRED_FIELDS:
            raise PipelineError("Coverage row schema invalid")
        if any(not isinstance(row[field], str) or not row[field].strip() for field in REQUIRED_FIELDS):
            raise PipelineError("Coverage row value invalid")
        if row["id"] in ids:
            raise PipelineError("Duplicate coverage id")
        ids.add(row["id"])
    return len(rows)


def coverage_matrix():
    validate_coverage_matrix()
    return {"schema": SCHEMA, "rows": deepcopy(ROWS)}
