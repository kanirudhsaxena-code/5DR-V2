"""Bounded 18-Sep-2026 research snapshot for EDGE_STOCK acceptance only.

The snapshot records source roles and normalized factual observations. It is not a
production research executor and must not be reused as evergreen evidence.
"""
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone

SNAPSHOT_AT = datetime(2026, 9, 18, 6, 55, tzinfo=timezone.utc)

MANIFEST = {
    "LTF": {
        "STOCK_PEERS": {
            "status": "RECOVERED_VIA_FALLBACK",
            "sources": [
                {
                    "role": "COMPANY_IR",
                    "url": "https://www.ltfinance.com/investors",
                    "authority": "L&T Finance official investor relations",
                    "facts": {"company_context": "Official investor information, FY2026-27 results and FY2025-26 annual report lane."},
                },
                {
                    "role": "REPUTABLE_SECONDARY",
                    "url": "https://www.screener.in/company/LTF/consolidated/",
                    "authority": "Screener market-data classification",
                    "facts": {"peer_classification": "Financial Services / Finance / Non Banking Financial Company (NBFC)."},
                },
            ],
        },
        "STOCK_FORWARD_CATALYSTS": {
            "status": "VERIFIED_PARTIAL",
            "sources": [{
                "role": "COMPANY_IR",
                "url": "https://www.ltfinance.com/investors",
                "authority": "L&T Finance official investor relations",
                "facts": {"scope": "Official results, investor presentation and analyst-meet lanes checked; no unsupported future-event assertion embedded."},
            }],
        },
        "STOCK_GOVERNANCE_RISK": {
            "status": "VERIFIED_PARTIAL",
            "sources": [
                {
                    "role": "COMPANY_IR",
                    "url": "https://www.ltfinance.com/investors/corporate-disclosures",
                    "authority": "L&T Finance official corporate disclosures",
                    "facts": {"scope": "Governance/statutory disclosure lane."},
                },
                {
                    "role": "NSE_DISCLOSURE",
                    "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
                    "authority": "National Stock Exchange of India",
                    "facts": {"symbol": "LTF", "scope": "Exchange corporate-filings lane; no independent adverse-risk conclusion embedded."},
                },
            ],
        },
        "STOCK_INSTITUTIONAL_EVENTS": {
            "status": "VERIFIED_PARTIAL",
            "sources": [{
                "role": "NSE_BLOCK_BULK",
                "url": "https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
                "authority": "National Stock Exchange of India",
                "facts": {"symbol": "LTF", "scope": "Authoritative bulk/block archive lane; evidence snapshot does not infer an event from absence."},
            }],
        },
    },
    "RELIANCE": {
        "STOCK_PEERS": {
            "status": "RECOVERED_VIA_FALLBACK",
            "sources": [
                {
                    "role": "COMPANY_IR",
                    "url": "https://www.ril.com/investors/financial-reporting/online-annual-report",
                    "authority": "Reliance Industries official investor relations",
                    "facts": {"company_context": "Official FY2025-26 annual-report lane."},
                },
                {
                    "role": "SECTOR_INDEX",
                    "url": "https://www.screener.in/company/NIFTOILGAS/",
                    "authority": "Screener Nifty Oil & Gas constituent/valuation view",
                    "facts": {"peer_context": "Nifty Oil & Gas constituent set includes Reliance Industries and other listed oil/gas companies with valuation fields."},
                },
            ],
        },
        "STOCK_FORWARD_CATALYSTS": {
            "status": "VERIFIED_PARTIAL",
            "sources": [{
                "role": "COMPANY_IR",
                "url": "https://www.ril.com/investor/resource-center/corporate-announcements",
                "authority": "Reliance Industries official corporate announcements",
                "facts": {"latest_context": "September 2026 analyst/institutional-meeting and regulatory announcements lane checked; no unsupported future-event assertion embedded."},
            }],
        },
        "STOCK_GOVERNANCE_RISK": {
            "status": "VERIFIED_PARTIAL",
            "sources": [
                {
                    "role": "COMPANY_IR",
                    "url": "https://www.ril.com/investors/shareholders-information/integrated-filing",
                    "authority": "Reliance Industries official integrated filings",
                    "facts": {"scope": "Financial and governance integrated filings through quarter ended June 30, 2026."},
                },
                {
                    "role": "NSE_DISCLOSURE",
                    "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
                    "authority": "National Stock Exchange of India",
                    "facts": {"symbol": "RELIANCE", "scope": "Exchange corporate-filings lane; no independent adverse-risk conclusion embedded."},
                },
            ],
        },
        "STOCK_INSTITUTIONAL_EVENTS": {
            "status": "VERIFIED_PARTIAL",
            "sources": [{
                "role": "NSE_BLOCK_BULK",
                "url": "https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
                "authority": "National Stock Exchange of India",
                "facts": {"symbol": "RELIANCE", "scope": "Authoritative bulk/block archive lane; evidence snapshot does not infer an event from absence."},
            }],
        },
    },
    "TATVA": {
        "STOCK_PEERS": {
            "status": "RECOVERED_VIA_FALLBACK",
            "sources": [
                {
                    "role": "COMPANY_IR",
                    "url": "https://www.tatvachintan.com/financial-information-and-other-disclosures.aspx",
                    "authority": "Tatva Chintan official investor disclosures",
                    "facts": {"company_context": "FY2025-26 annual report and FY2026-27 disclosure lane."},
                },
                {
                    "role": "REPUTABLE_SECONDARY",
                    "url": "https://www.screener.in/market/IN01/IN0101/IN010101/IN010101002/?order=desc&sort=current+price",
                    "authority": "Screener Specialty Chemicals category",
                    "facts": {"peer_context": "Tatva Chintan appears in a listed Specialty Chemicals universe with P/E, market cap, ROCE and quarterly metrics."},
                },
            ],
        },
        "STOCK_FORWARD_CATALYSTS": {
            "status": "COMPLETE",
            "sources": [{
                "role": "COMPANY_IR",
                "url": "https://www.tatvachintan.com/financial-information-and-other-disclosures.aspx",
                "authority": "Tatva Chintan official investor disclosures",
                "facts": {"forward_event": "Investor meet intimated for 23 September 2026."},
            }],
        },
        "STOCK_GOVERNANCE_RISK": {
            "status": "VERIFIED_PARTIAL",
            "sources": [
                {
                    "role": "COMPANY_IR",
                    "url": "https://www.tatvachintan.com/financial-information-and-other-disclosures.aspx",
                    "authority": "Tatva Chintan official investor disclosures",
                    "facts": {"scope": "Corporate-governance, shareholding, director/SMP and exchange-disclosure lane."},
                },
                {
                    "role": "NSE_DISCLOSURE",
                    "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
                    "authority": "National Stock Exchange of India",
                    "facts": {"symbol": "TATVA", "scope": "Exchange corporate-filings lane; no independent adverse-risk conclusion embedded."},
                },
            ],
        },
        "STOCK_INSTITUTIONAL_EVENTS": {
            "status": "VERIFIED_PARTIAL",
            "sources": [{
                "role": "NSE_BLOCK_BULK",
                "url": "https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
                "authority": "National Stock Exchange of India",
                "facts": {"symbol": "TATVA", "scope": "Authoritative bulk/block archive lane; evidence snapshot does not infer an event from absence."},
            }],
        },
    },
}


def validation_manifest(symbol):
    rows = deepcopy(MANIFEST.get(symbol))
    if rows is None:
        raise KeyError(symbol)
    for variable in rows.values():
        for source in variable["sources"]:
            canonical = json.dumps(
                {
                    "role": source["role"],
                    "url": source["url"],
                    "authority": source["authority"],
                    "facts": source["facts"],
                    "snapshot_at": SNAPSHOT_AT.isoformat(),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            source["source_sha256"] = hashlib.sha256(canonical).hexdigest()
            source["retrieved_at"] = SNAPSHOT_AT.isoformat()
            source["facts"]["validation_snapshot"] = True
    return rows
