"""Declarative consumer requirements registry for 5DR, EDGE Stocks and IPO EDGE.

Provisioning is broader than collection. `enabled_experiment` identifies only data
allowed to be actively exercised by the current isolated experiment. EDGE profiles
remain provisioned/on-demand until separately approved for integration.
"""
from copy import deepcopy

from experiments.data_contract import DataArchitectureError

SCHEMA = "market-evidence-consumer-requirements-v1"
CONSUMERS = {"5DR", "EDGE_STOCK", "EDGE_IPO"}
AVAILABILITY = {"AVAILABLE", "PARTIAL", "UNVERIFIED", "UNAVAILABLE", "DERIVED", "EXTERNAL_ONLY"}
MODES = {"SNAPSHOT", "INCREMENTAL", "ON_DEMAND", "DAILY", "EVENT_DRIVEN", "RESEARCH"}


def _r(variable_id, consumer, category, requirement, availability, mode,
       *, enabled=False, timeframes=(), lookback_days=None, retention_days=None,
       source_preference="UPSTOX", fallback="NONE"):
    return {
        "variable_id": variable_id,
        "consumer": consumer,
        "category": category,
        "requirement": requirement,
        "upstox_availability": availability,
        "collection_mode": mode,
        "enabled_experiment": bool(enabled),
        "timeframes": tuple(timeframes),
        "lookback_days": deepcopy(lookback_days),
        "retention_days": retention_days,
        "source_preference": source_preference,
        "fallback": fallback,
    }


ROWS = [
    # 5DR — quantitative inputs required by canonical V2.2.2.
    _r("NIFTY_PRICE_CANDLES", "5DR", "PRICE_STRUCTURE", "NIFTY spot + 5m/15m/30m/1H/Daily OHLC(V) for structure, close and efficacy", "AVAILABLE", "INCREMENTAL", enabled=True, timeframes=("5m","15m","30m","1h","1d"), lookback_days={"5m":30,"15m":180,"30m":180,"1h":365,"1d":365}, retention_days=400),
    _r("INDIA_VIX", "5DR", "VOLATILITY", "Current and historical India VIX", "AVAILABLE", "INCREMENTAL", enabled=True, timeframes=("quote","1h","1d"), lookback_days={"1h":365,"1d":365}, retention_days=400),
    _r("NIFTY_FUTURES", "5DR", "PVPO", "Exact active NIFTY future, price, volume, OI and spot/future basis", "AVAILABLE", "SNAPSHOT", enabled=True, timeframes=("quote",), retention_days=30),
    _r("NIFTY_OPTION_CONTRACTS", "5DR", "PVPO", "Expiries, strikes and exact CE/PE identity", "AVAILABLE", "SNAPSHOT", enabled=True, retention_days=7),
    _r("NIFTY_OPTION_CHAIN", "5DR", "PVPO_EXECUTION", "LTP, volume, OI, previous/change OI, bid/ask, IV/Greeks where supplied", "AVAILABLE", "SNAPSHOT", enabled=True, retention_days=30),
    _r("NIFTY_DERIVATIVE_ANALYTICS", "5DR", "PVPO", "OI/change-OI/PCR/max-pain supporting context", "AVAILABLE", "SNAPSHOT", enabled=True, retention_days=90),
    _r("NIFTY_HEAVYWEIGHTS", "5DR", "PARTICIPATION", "Approved top-heavyweight direction and volume", "AVAILABLE", "SNAPSHOT", enabled=True, retention_days=30),
    _r("NIFTY_SECTOR_INDICES", "5DR", "PARTICIPATION", "Approved material sector leadership/breadth", "AVAILABLE", "SNAPSHOT", enabled=True, retention_days=30),
    _r("FII_DII_CASH", "5DR", "PARTICIPATION", "FII/FPI and DII cash participation", "AVAILABLE", "DAILY", enabled=True, timeframes=("1d",), lookback_days={"1d":365}, retention_days=400),
    _r("FII_INDEX_DERIVATIVES", "5DR", "PARTICIPATION_PVPO", "FII index-futures/options positioning where canonical logic consumes it", "AVAILABLE", "DAILY", enabled=True, timeframes=("1d",), lookback_days={"1d":365}, retention_days=400),
    _r("GLOBAL_RISK_INDICES", "5DR", "MACRO", "GIFT Nifty, US, Europe and Asia risk indices required by 5DR", "AVAILABLE", "INCREMENTAL", enabled=True, timeframes=("quote","1h","1d"), lookback_days={"1h":365,"1d":365}, retention_days=400, fallback="WEB_RESEARCH"),
    _r("CRUDE_USDINR", "5DR", "MACRO", "Brent/WTI and USD/INR quantitative context", "AVAILABLE", "INCREMENTAL", enabled=True, timeframes=("quote","1h","1d"), lookback_days={"1h":365,"1d":365}, retention_days=400, fallback="WEB_RESEARCH"),
    _r("GOLD", "5DR", "MACRO", "Gold context where exact provider identity is verified", "UNVERIFIED", "SNAPSHOT", source_preference="UPSTOX_OR_FUTURE_PROVIDER", fallback="WEB_RESEARCH"),
    _r("DXY_RATES", "5DR", "MACRO", "DXY and global/India rates context", "UNVERIFIED", "RESEARCH", source_preference="FUTURE_PROVIDER_OR_WEB", fallback="WEB_RESEARCH"),
    _r("MACRO_EVENTS_GEOPOLITICS", "5DR", "MACRO", "Fed/RBI/CPI/GDP/PCE, geopolitics, sanctions and transmission", "EXTERNAL_ONLY", "RESEARCH", source_preference="OFFICIAL_WEB", fallback="WEB_RESEARCH"),
    _r("OPTION_LIFECYCLE_PRICES", "5DR", "EFFICACY_LEARNING", "Issuance and later option premiums/MFE/MAE when objectively verifiable", "PARTIAL", "EVENT_DRIVEN", enabled=True, retention_days=400, fallback="SCREENSHOT_OR_WEB"),

    # EDGE Stocks — provisioned on demand; no background market-wide collection.
    _r("STOCK_PRICE_CANDLES", "EDGE_STOCK", "PRICE_STRUCTURE", "Current quote and daily/intraday OHLCV for selected stock", "AVAILABLE", "ON_DEMAND", timeframes=("quote","15m","30m","1h","1d"), lookback_days={"15m":180,"30m":180,"1h":365,"1d":730}, retention_days=730),
    _r("STOCK_RELATIVE_STRENGTH", "EDGE_STOCK", "RELATIVE_STRENGTH", "Stock versus relevant sector/index", "DERIVED", "ON_DEMAND", fallback="WEB_RESEARCH"),
    _r("STOCK_OPTIONS", "EDGE_STOCK", "PVPO_EXECUTION", "For optionable stocks: contracts, chain, premium, OI, IV/Greeks and liquidity", "AVAILABLE", "ON_DEMAND", retention_days=90, fallback="SCREENSHOT_OR_WEB"),
    _r("STOCK_FUNDAMENTALS", "EDGE_STOCK", "FUNDAMENTALS_VALUATION", "Revenue/profit/margins/cash flow/debt/returns/valuation ratios", "AVAILABLE", "ON_DEMAND", retention_days=30, fallback="OFFICIAL_WEB"),
    _r("STOCK_SHAREHOLDING", "EDGE_STOCK", "INSTITUTIONAL", "Promoter/FII/DII/MF/retail ownership trends where supplied", "AVAILABLE", "ON_DEMAND", retention_days=180, fallback="OFFICIAL_WEB"),
    _r("STOCK_PEERS", "EDGE_STOCK", "VALUATION", "Peer set and sector-relative valuation context", "PARTIAL", "ON_DEMAND", retention_days=30, fallback="WEB_RESEARCH"),
    _r("STOCK_CORPORATE_ACTIONS", "EDGE_STOCK", "EVENTS", "Dividend/split/bonus/rights and other structured corporate actions", "AVAILABLE", "ON_DEMAND", retention_days=365, fallback="OFFICIAL_WEB"),
    _r("STOCK_NEWS_RECENT", "EDGE_STOCK", "CATALYSTS", "Recent provider news for selected stock", "AVAILABLE", "ON_DEMAND", retention_days=14, fallback="WEB_RESEARCH"),
    _r("STOCK_FORWARD_CATALYSTS", "EDGE_STOCK", "CATALYSTS", "10–15 day upcoming results/regulatory/company events", "PARTIAL", "RESEARCH", source_preference="OFFICIAL_WEB_PLUS_PROVIDER", fallback="WEB_RESEARCH"),
    _r("STOCK_GOVERNANCE_RISK", "EDGE_STOCK", "GOVERNANCE", "Fraud/litigation/auditor/default/regulatory/management evidence", "EXTERNAL_ONLY", "RESEARCH", source_preference="OFFICIAL_WEB", fallback="WEB_RESEARCH"),
    _r("STOCK_INSTITUTIONAL_EVENTS", "EDGE_STOCK", "INSTITUTIONAL", "Block/bulk deals, insider/promoter transactions and large-holder events", "PARTIAL", "RESEARCH", source_preference="OFFICIAL_WEB_PLUS_PROVIDER", fallback="WEB_RESEARCH"),
    _r("STOCK_RELEVANT_MACRO", "EDGE_STOCK", "MACRO", "Only macro variables with a direct stock transmission channel", "DERIVED", "ON_DEMAND", fallback="SHARED_MARKET_CORE_PLUS_WEB"),

    # IPO EDGE — structured lifecycle spine + official/web research lanes.
    _r("IPO_DISCOVERY", "EDGE_IPO", "DISCOVERY", "Mainboard/SME universe and lifecycle stage", "AVAILABLE", "DAILY", retention_days=365, fallback="NSE_BSE_SEBI"),
    _r("IPO_CORE_TERMS", "EDGE_IPO", "ISSUE_TERMS", "Issue size, price band, dates, lot/minimum, face value, exchange and industry", "AVAILABLE", "EVENT_DRIVEN", retention_days=3650, fallback="RHP_EXCHANGE"),
    _r("IPO_DOCUMENTS_TIMELINE", "EDGE_IPO", "DOCUMENTS", "DRHP/RHP links, registrar and offer/listing timeline", "AVAILABLE", "EVENT_DRIVEN", retention_days=3650, fallback="SEBI_EXCHANGE"),
    _r("IPO_SUBSCRIPTION", "EDGE_IPO", "MARKET_DEMAND", "Total and category demand plus offer-period acceleration when provider schema proves it", "PARTIAL", "EVENT_DRIVEN", retention_days=3650, fallback="NSE_BSE"),
    _r("IPO_ANCHOR_QIB", "EDGE_IPO", "INSTITUTIONAL", "Anchor book size/quality/diversity and QIB evidence", "PARTIAL", "RESEARCH", source_preference="OFFICIAL_WEB_PLUS_PROVIDER", fallback="NSE_BSE_RHP"),
    _r("IPO_BUSINESS_QUALITY", "EDGE_IPO", "BUSINESS", "Business model, competitive position, TAM, concentration, scalability and risks", "EXTERNAL_ONLY", "RESEARCH", source_preference="DRHP_RHP", fallback="OFFICIAL_WEB"),
    _r("IPO_FINANCIALS", "EDGE_IPO", "FINANCIAL", "Revenue/profit/margins/ROE-ROCE/debt/cash flow/working capital/earnings quality", "EXTERNAL_ONLY", "RESEARCH", source_preference="DRHP_RHP", fallback="OFFICIAL_WEB"),
    _r("IPO_VALUATION", "EDGE_IPO", "VALUATION", "Issue valuation, listed peers, growth/profitability context and upside room", "DERIVED", "RESEARCH", source_preference="RHP_PLUS_LISTED_PEER_DATA", fallback="WEB_RESEARCH"),
    _r("IPO_GOVERNANCE_STRUCTURE", "EDGE_IPO", "GOVERNANCE", "Promoters, litigation, fresh/OFS mix, use of proceeds, dilution/sellers", "EXTERNAL_ONLY", "RESEARCH", source_preference="DRHP_RHP", fallback="OFFICIAL_WEB"),
    _r("IPO_BROKER_RESEARCH", "EDGE_IPO", "ANALYST", "Reputable broker recommendations, rationale, consensus/disagreement and date", "EXTERNAL_ONLY", "RESEARCH", source_preference="BROKER_WEB", fallback="WEB_RESEARCH"),
    _r("IPO_GMP", "EDGE_IPO", "GMP", "GMP level/percent/trend as secondary sentiment evidence", "UNAVAILABLE", "RESEARCH", source_preference="SPECIALIST_SECONDARY", fallback="GMP_SPECIALIST"),
    _r("IPO_LISTING_OUTCOME", "EDGE_IPO", "OUTCOME", "Issue price, listing/open price and derived listing gain", "AVAILABLE", "EVENT_DRIVEN", retention_days=3650, fallback="NSE_BSE"),
    _r("IPO_ENVIRONMENT", "EDGE_IPO", "ENVIRONMENT", "Sector momentum, broad market, IPO regime and relevant macro", "DERIVED", "ON_DEMAND", fallback="SHARED_MARKET_CORE_PLUS_WEB"),
]


def validate_registry(rows=None):
    rows = ROWS if rows is None else rows
    if not isinstance(rows, list) or not rows:
        raise DataArchitectureError("requirements registry missing")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise DataArchitectureError("requirements row invalid")
        key = (row.get("consumer"), row.get("variable_id"))
        if key in seen:
            raise DataArchitectureError("duplicate consumer variable")
        seen.add(key)
        if row.get("consumer") not in CONSUMERS:
            raise DataArchitectureError("consumer invalid")
        if row.get("upstox_availability") not in AVAILABILITY:
            raise DataArchitectureError("availability invalid")
        if row.get("collection_mode") not in MODES:
            raise DataArchitectureError("collection mode invalid")
        if not isinstance(row.get("enabled_experiment"), bool):
            raise DataArchitectureError("enabled flag invalid")
        for field in ("variable_id","category","requirement","source_preference","fallback"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise DataArchitectureError(f"requirements {field} invalid")
        if not isinstance(row.get("timeframes"), tuple):
            raise DataArchitectureError("timeframes invalid")
        if row.get("retention_days") is not None and (isinstance(row["retention_days"], bool) or not isinstance(row["retention_days"], int) or row["retention_days"] <= 0):
            raise DataArchitectureError("retention invalid")
    return len(rows)


def requirements(consumer=None):
    validate_registry()
    rows = ROWS if consumer is None else [row for row in ROWS if row["consumer"] == consumer]
    if consumer is not None and consumer not in CONSUMERS:
        raise DataArchitectureError("unknown consumer")
    return deepcopy(rows)
