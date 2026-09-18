"""One-off governed judgment for the macro-enriched 2026-09-16 live bundle.

This is an auditable intelligence-layer interpretation of one exact frozen snapshot.
It does not create reusable regime/scoring thresholds or change frozen 5DR methodology.
"""
from copy import deepcopy

from experiments.engine_handoff import JUDGMENT_SCHEMA, JUDGMENT_SOURCE
from src.scoring import weighted_component

EXPECTED_BUNDLE_SHA256 = "1016031fee2463372584e7eb74528de3efc8226a9c80a10035d17547b1382914"

PVS_WEIGHTS = {
    "DAILY_1H_STRUCTURE": 40.0,
    "KEY_LEVEL_ACCEPTANCE": 25.0,
    "VOLUME_CONFIRMATION": 20.0,
    "30M_15M_PERSISTENCE": 15.0,
}
PVPO_WEIGHTS = {
    "PRICE_FUTURES_BASIS": 30.0,
    "VOLUME_PARTICIPATION": 20.0,
    "PREMIUM_BEHAVIOUR": 25.0,
    "OI_STRUCTURE_CHANGE": 25.0,
}
PARTICIPATION_WEIGHTS = {
    "HEAVYWEIGHTS": 45.0,
    "SECTORS": 35.0,
    "INSTITUTIONAL_CASH": 20.0,
}
MACRO_WEIGHTS = {
    "GLOBAL_RISK": 35.0,
    "INDIA_MACRO_RATES": 25.0,
    "CRUDE_GEOPOLITICS": 25.0,
    "SCHEDULED_CATALYST": 15.0,
}

RAW_SCORES = {
    "PRICE_STRUCTURE": {
        "DAILY_1H_STRUCTURE": -1,
        "KEY_LEVEL_ACCEPTANCE": 0,
        "VOLUME_CONFIRMATION": 1,
        "30M_15M_PERSISTENCE": 0,
    },
    "PVPO": {
        "PRICE_FUTURES_BASIS": 1,
        "VOLUME_PARTICIPATION": 0,
        "PREMIUM_BEHAVIOUR": 2,
        "OI_STRUCTURE_CHANGE": 1,
    },
    "PARTICIPATION": {
        "HEAVYWEIGHTS": 1,
        "SECTORS": 1,
        "INSTITUTIONAL_CASH": 0,
    },
    "MACRO_CATALYSTS": {
        "GLOBAL_RISK": -1,
        "INDIA_MACRO_RATES": -1,
        "CRUDE_GEOPOLITICS": -1,
        "SCHEDULED_CATALYST": 0,
    },
}

AUDIT_REASONS = {
    "PRICE_STRUCTURE": {
        "DAILY_1H_STRUCTURE": "Daily remains LH/LL bearish while 1H is mixed/transition; the higher-timeframe pair is net bearish but not uniformly so.",
        "KEY_LEVEL_ACCEPTANCE": "Intraday 15m/30m/1h closes remain inside the observed prior ranges, so there is no accepted directional range break.",
        "VOLUME_CONFIRMATION": "Spot/futures and approved constituent participation support the rebound, while futures OI is slightly below prior OI, so confirmation is positive but incomplete.",
        "30M_15M_PERSISTENCE": "30m is HH/HL bullish but 15m is LH/HL transition; persistence is mixed and therefore neutral on the frozen scale.",
    },
    "PVPO": {
        "PRICE_FUTURES_BASIS": "NIFTY is positive versus previous close and the nearest future retains a positive basis.",
        "VOLUME_PARTICIPATION": "Derivative turnover is strong but nearest-future OI is slightly below previous OI; no strong fresh-position confirmation is assigned.",
        "PREMIUM_BEHAVIOUR": "Near-ATM sampled calls are up roughly 13-15% while puts are down roughly 22-27%, with IV/theta and tight spreads preserved in evidence.",
        "OI_STRUCTURE_CHANGE": "Top put OI is 23200, top call OI is 23500, PCR is near 0.99 and max pain is 23300, giving mild bullish support/supply asymmetry rather than a strong directional signal.",
    },
    "PARTICIPATION": {
        "HEAVYWEIGHTS": "Six of the approved eight heavyweight observations are positive; Infosys and L&T are negative exceptions.",
        "SECTORS": "Three of four approved sector indices are positive; IT is the material negative exception.",
        "INSTITUTIONAL_CASH": "FII cash selling is substantially offset by DII buying, leaving cash participation conflicted rather than directional.",
    },
    "MACRO_CATALYSTS": {
        "GLOBAL_RISK": "Dow, S&P 500 and US Tech 100 are negative while Asia/Europe are mixed-positive; the major US risk signal is adverse but not globally unanimous.",
        "INDIA_MACRO_RATES": "Official Fed H.15 shows the US 10Y at 4.97%; USD/INR is around 95.97 and RBI repo is 5.25%, an adverse rates/currency backdrop for India without an extreme classification rule.",
        "CRUDE_GEOPOLITICS": "Brent is about 108.4 and WTI about 104.9 in the frozen evidence, an adverse India transmission risk; the governed geopolitics source remains reference-only so no extra directional fact is invented.",
        "SCHEDULED_CATALYST": "Official Fed calendar confirms Sep 15-16 and today as FOMC decision day. Direction is unknown, so the scheduled-catalyst directional raw score remains neutral while Event Shock is handled separately.",
    },
}

MARKET_TRUST_INPUTS = {
    "price_confirmation": 55.0,
    "pvpo_confirmation": 75.0,
    "participation_confirmation": 70.0,
    "cross_engine_consistency": 45.0,
    "closing_confirmation": 50.0,
    "evidence_freshness_completeness": 98.0,
}

EXECUTION_INPUTS = {
    "rr_score": 50.0,
    "premium_iv_theta_score": 70.0,
    "strike_expiry_fit_score": 70.0,
    "liquidity_spread_score": 90.0,
    "entry_invalidation_score": 55.0,
}


def _component_scores():
    return {
        "PRICE_STRUCTURE": weighted_component(RAW_SCORES["PRICE_STRUCTURE"], PVS_WEIGHTS),
        "PVPO": weighted_component(RAW_SCORES["PVPO"], PVPO_WEIGHTS),
        "PARTICIPATION": weighted_component(RAW_SCORES["PARTICIPATION"], PARTICIPATION_WEIGHTS),
        "MACRO_CATALYSTS": weighted_component(RAW_SCORES["MACRO_CATALYSTS"], MACRO_WEIGHTS),
    }


def build_macro_enriched_judgment(bundle_sha256=EXPECTED_BUNDLE_SHA256):
    if bundle_sha256 != EXPECTED_BUNDLE_SHA256:
        raise ValueError("macro-enriched governed judgment is valid only for the exact frozen bundle")
    horizons = {
        f"D+{day}": {"status": "SHADOW_ONLY_NON_RELEASED", "zone_low": None, "zone_high": None}
        for day in range(1, 6)
    }
    normalized = {
        "regime": "EVENT_SHOCK",
        "component_scores": _component_scores(),
        "market_trust_inputs": deepcopy(MARKET_TRUST_INPUTS),
        "event_shock": "HIGH",
        "execution_inputs": deepcopy(EXECUTION_INPUTS),
        "data_adequate": True,
        "event_kill_switch": False,
        "expected_rr": 1.8,
        "horizon_slots": horizons,
    }
    return {
        "schema": JUDGMENT_SCHEMA,
        "source": JUDGMENT_SOURCE,
        "bundle_sha256": EXPECTED_BUNDLE_SHA256,
        "methodology_changed": False,
        "release_complete": False,
        "shadow_only": True,
        "normalized_engine_inputs": normalized,
        "judgment_audit": {
            "raw_scale": [-2, -1, 0, 1, 2],
            "raw_scores": deepcopy(RAW_SCORES),
            "internal_weights": {
                "PRICE_STRUCTURE": deepcopy(PVS_WEIGHTS),
                "PVPO": deepcopy(PVPO_WEIGHTS),
                "PARTICIPATION": deepcopy(PARTICIPATION_WEIGHTS),
                "MACRO_CATALYSTS": deepcopy(MACRO_WEIGHTS),
            },
            "reasons": deepcopy(AUDIT_REASONS),
            "regime_reason": "Same-day FOMC decision creates a material event-driven transmission regime. This is a one-off intelligence judgment, not a new automatic regime-selection rule.",
            "macro_fact_quality": {
                "FED_H15": "FACT_EXTRACTED",
                "FOMC_CALENDAR": "FACT_EXTRACTED",
                "RBI": "FACT_EXTRACTED",
                "DXY_OWNER": "REFERENCE_ONLY",
                "GEOPOLITICS": "REFERENCE_ONLY",
            },
            "horizon_release_complete": False,
            "production_methodology_source": "5DR_V2_1_FROZEN",
        },
    }
