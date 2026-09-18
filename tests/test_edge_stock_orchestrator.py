import hashlib
import unittest
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.edge_stock_orchestrator import (
    assemble_edge_stock_bundle,
    build_shared_macro_record,
)
from experiments.edge_stock_research import build_research_record

NOW = datetime(2026, 9, 18, 7, 0, tzinfo=timezone.utc)
STOCK = {
    "kind": "STOCK",
    "id": "INE498L01015",
    "name": "L&T Finance Ltd",
    "exchange": "NSE",
    "segment": "NSE_EQ",
    "instrument_key": "NSE_EQ|INE498L01015",
    "symbol": "LTF",
    "isin": "INE498L01015",
}
FO = {
    "fo_eligible": False,
    "underlying_key": STOCK["instrument_key"],
    "symbol": "LTF",
    "active_expiries": [],
    "nearest_expiry": None,
    "has_future": False,
    "has_calls": False,
    "has_puts": False,
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def source(role, n):
    return {
        "role": role,
        "url": f"https://example.invalid/{role.lower()}/{n}",
        "authority": "OFFICIAL",
        "source_sha256": digest(role + str(n)),
        "retrieved_at": NOW.isoformat(),
        "facts": {"test": n},
    }


def core_record(variable):
    return build_record(
        provider_id="UPSTOX",
        source_semantic="UPSTOX_AUTHENTICATED",
        variable_id=variable,
        consumer="EDGE_STOCK",
        subject=STOCK,
        metric="TEST",
        values={"value": 1},
        timeframe="snapshot",
        provider_timestamp=NOW,
        acquisition_timestamp=NOW,
        freshness_status="LIVE",
        source_reference="/test",
        source_sha256=digest(variable),
    )


CORE_VARS = {
    "STOCK_PRICE_CANDLES", "STOCK_RELATIVE_STRENGTH", "STOCK_FUNDAMENTALS",
    "STOCK_SHAREHOLDING", "STOCK_PEERS", "STOCK_CORPORATE_ACTIONS",
    "STOCK_NEWS_RECENT",
}


class EdgeStockOrchestratorTests(unittest.TestCase):
    def research(self, include_peer_fallback=False):
        rows = [
            build_research_record(
                stock_identity=STOCK,
                variable_id="STOCK_FORWARD_CATALYSTS",
                sources=[source("COMPANY_IR", 1)],
                status="COMPLETE",
                acquisition_timestamp=NOW,
            ),
            build_research_record(
                stock_identity=STOCK,
                variable_id="STOCK_GOVERNANCE_RISK",
                sources=[source("SEBI_ORDER", 2), source("NSE_DISCLOSURE", 3)],
                status="COMPLETE",
                acquisition_timestamp=NOW,
            ),
            build_research_record(
                stock_identity=STOCK,
                variable_id="STOCK_INSTITUTIONAL_EVENTS",
                sources=[source("NSE_BLOCK_BULK", 4)],
                status="COMPLETE",
                acquisition_timestamp=NOW,
            ),
        ]
        if include_peer_fallback:
            rows.append(build_research_record(
                stock_identity=STOCK,
                variable_id="STOCK_PEERS",
                sources=[
                    source("COMPANY_IR", 5),
                    source("REPUTABLE_SECONDARY", 6),
                ],
                status="RECOVERED_VIA_FALLBACK",
                acquisition_timestamp=NOW,
            ))
        return rows

    def test_complete_non_fo_orchestration_is_ready(self):
        core = {
            "stock_identity": STOCK,
            "fo_identity": FO,
            "records": [core_record(v) for v in sorted(CORE_VARS)],
            "read_only": True,
            "methodology_applied": False,
        }
        macro = build_shared_macro_record(
            stock_identity=STOCK,
            macro_evidence={
                "source_sha256": digest("macro"),
                "source_reference": "shared-market-core:test",
                "observed_at": NOW,
                "values": {"usd_inr": 1},
                "transmission_channels": ["FX"],
            },
            acquisition_timestamp=NOW,
        )
        out = assemble_edge_stock_bundle(
            core_acquisition=core,
            research_records=self.research(),
            macro_record=macro,
            run_id="EDGE-STOCK-LTF-TEST",
            frozen_at=NOW,
        )
        self.assertEqual(out["status"], "READY")
        self.assertFalse(out["methodology_applied"])
        self.assertFalse(out["trading_enabled"])

    def test_governance_requires_two_distinct_official_roles(self):
        with self.assertRaises(DataArchitectureError):
            build_research_record(
                stock_identity=STOCK,
                variable_id="STOCK_GOVERNANCE_RISK",
                sources=[source("SEBI_ORDER", 1)],
                status="COMPLETE",
                acquisition_timestamp=NOW,
            )

    def test_conflicted_research_cannot_enter_ready_bundle(self):
        with self.assertRaises(DataArchitectureError):
            build_research_record(
                stock_identity=STOCK,
                variable_id="STOCK_FORWARD_CATALYSTS",
                sources=[source("COMPANY_IR", 1)],
                status="CONFLICTED",
                acquisition_timestamp=NOW,
            )

    def test_missing_research_variable_fails_closed(self):
        core = {
            "stock_identity": STOCK,
            "fo_identity": FO,
            "records": [core_record(v) for v in sorted(CORE_VARS)],
            "read_only": True,
            "methodology_applied": False,
        }
        macro = build_shared_macro_record(
            stock_identity=STOCK,
            macro_evidence={
                "source_sha256": digest("macro"),
                "source_reference": "shared-market-core:test",
                "observed_at": NOW,
                "values": {},
            },
            acquisition_timestamp=NOW,
        )
        with self.assertRaises(DataArchitectureError):
            assemble_edge_stock_bundle(
                core_acquisition=core,
                research_records=self.research()[:2],
                macro_record=macro,
                run_id="EDGE-STOCK-LTF-TEST2",
                frozen_at=NOW,
            )

    def test_peer_provider_gap_recovers_only_with_explicit_fallback(self):
        core = {
            "stock_identity": STOCK,
            "fo_identity": FO,
            "records": [core_record(v) for v in sorted(CORE_VARS - {"STOCK_PEERS"})],
            "provider_gaps": [{
                "variable_id": "STOCK_PEERS",
                "provider": "UPSTOX",
                "provider_lane": "competitors",
                "status": "PROVIDER_UNAVAILABLE",
                "fallback_required": True,
            }],
            "read_only": True,
            "methodology_applied": False,
        }
        macro = build_shared_macro_record(
            stock_identity=STOCK,
            macro_evidence={
                "source_sha256": digest("macro-peer"),
                "source_reference": "shared-market-core:test",
                "observed_at": NOW,
                "values": {},
            },
            acquisition_timestamp=NOW,
        )
        with self.assertRaises(DataArchitectureError):
            assemble_edge_stock_bundle(
                core_acquisition=core,
                research_records=self.research(),
                macro_record=macro,
                run_id="EDGE-STOCK-LTF-PEER-BLOCK",
                frozen_at=NOW,
            )
        out = assemble_edge_stock_bundle(
            core_acquisition=core,
            research_records=self.research(include_peer_fallback=True),
            macro_record=macro,
            run_id="EDGE-STOCK-LTF-PEER-RECOVERED",
            frozen_at=NOW,
        )
        self.assertEqual(out["status"], "READY")
        peer = [
            r for r in out["bundle"]["quantitative_records"]
            if r["variable_id"] == "STOCK_PEERS"
        ]
        self.assertEqual(
            peer[0]["values"]["reconciliation_status"],
            "RECOVERED_VIA_FALLBACK",
        )

    def test_peer_fallback_cannot_duplicate_provider_peer_record(self):
        core = {
            "stock_identity": STOCK,
            "fo_identity": FO,
            "records": [core_record(v) for v in sorted(CORE_VARS)],
            "provider_gaps": [],
            "read_only": True,
            "methodology_applied": False,
        }
        macro = build_shared_macro_record(
            stock_identity=STOCK,
            macro_evidence={
                "source_sha256": digest("macro-dupe"),
                "source_reference": "shared-market-core:test",
                "observed_at": NOW,
                "values": {},
            },
            acquisition_timestamp=NOW,
        )
        with self.assertRaises(DataArchitectureError):
            assemble_edge_stock_bundle(
                core_acquisition=core,
                research_records=self.research(include_peer_fallback=True),
                macro_record=macro,
                run_id="EDGE-STOCK-LTF-PEER-DUPE",
                frozen_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
