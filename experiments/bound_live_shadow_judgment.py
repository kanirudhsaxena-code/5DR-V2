"""One-off governed judgment bound to the enriched 2026-09-16 V2.2.3 live bundle.

This module does not create reusable scoring thresholds or modify frozen 5DR
methodology. It records the auditable intelligence-layer interpretation of one exact
frozen evidence snapshot using only the existing five-point raw scale, existing
internal weights, and existing engine input contract.
"""
from copy import deepcopy

from experiments.engine_handoff import JUDGMENT_SCHEMA, JUDGMENT_SOURCE
from src.scoring import weighted_component

EXPECTED_BUNDLE_SHA256 = "675bed4af880a3bad01ab69bfae045ba00f1de9a3ba1f5d614da1d36f1b33617"

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
        "30M_15M_PERSISTENCE": 1,
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
        "GLOBAL_RISK": 0,
        "INDIA_MACRO_RATES": 0,
        "CRUDE_GEOPOLITICS": -1,
        "SCHEDULED_CATALYST": 0,
    },
}

AUDIT_REASONS = {
    "PRICE_STRUCTURE": {
        "DAILY_1H_STRUCTURE": "Daily structure bearish while 1H is mixed/transition; not a clean trend confirmation.",
        "KEY_LEVEL_ACCEPTANCE": "Intraday price remains inside the observed prior ranges without a clean accepted breakout/breakdown.",
        "VOLUME_CONFIRMATION": "Futures/constituent participation supports the rebound, but futures OI is slightly lower, consistent with incomplete fresh-position confirmation.",
        "30M_15M_PERSISTENCE": "Both 30m and 15m show HH/HL uptrend structure in the frozen snapshot.",
    },
    "PVPO": {
        "PRICE_FUTURES_BASIS": "NIFTY is positive versus previous close and the nearest future holds a positive basis.",
        "VOLUME_PARTICIPATION": "Derivative turnover is strong but futures OI is slightly lower; confirmation is mixed rather than strongly directional.",
        "PREMIUM_BEHAVIOUR": "Sampled near-ATM calls expanded while puts contracted materially, with IV/theta evidence preserved.",
        "OI_STRUCTURE_CHANGE": "Put concentration at 23200, call concentration at 23500 and PCR near 1 indicate support/supply structure with a mild bullish tilt, not standalone direction.",
    },
    "PARTICIPATION": {
        "HEAVYWEIGHTS": "Six of the approved eight heavyweight observations are positive in the frozen snapshot.",
        "SECTORS": "Three of four approved sector indices are positive; IT is the material negative exception.",
        "INSTITUTIONAL_CASH": "FII cash selling is broadly offset by DII buying, leaving institutional cash confirmation balanced/conflicted.",
    },
    "MACRO_CATALYSTS": {
        "GLOBAL_RISK": "US risk indices are negative while several Asian/European indices and GIFT Nifty are positive; global signal is mixed.",
        "INDIA_MACRO_RATES": "Frozen evidence does not establish a directional India rates/RBI impulse strong enough for a non-neutral raw score.",
        "CRUDE_GEOPOLITICS": "Brent/WTI are above 100 in the frozen evidence, a mild adverse India transmission risk without a verified same-snapshot trend signal.",
        "SCHEDULED_CATALYST": "The September FOMC decision is pending; event risk is high but its directional outcome is unknown and is therefore not guessed into the macro direction score.",
    },
}

MARKET_TRUST_INPUTS = {
    "price_confirmation": 55.0,
    "pvpo_confirmation": 75.0,
    "participation_confirmation": 70.0,
    "cross_engine_consistency": 45.0,
    "closing_confirmation": 50.0,
    "evidence_freshness_completeness": 95.0,
}

EXECUTION_INPUTS = {
    "rr_score": 50.0,
    "premium_iv_theta_score": 65.0,
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


def build_bound_judgment(bundle_sha256=EXPECTED_BUNDLE_SHA256):
    if bundle_sha256 != EXPECTED_BUNDLE_SHA256:
        raise ValueError("this governed judgment is valid only for the exact frozen live bundle")
    horizons = {
        f"D+{day}": {
            "status": "SHADOW_ONLY_NON_RELEASED",
            "zone_low": None,
            "zone_high": None,
        }
        for day in range(1, 6)
    }
    normalized = {
        "regime": "TRANSITION",
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
            "execution_expression_observed": "NIFTY 23250 CE 22 SEP 26",
            "execution_expression_role": "DIAGNOSTIC_ONLY_NOT_A_RECOMMENDATION",
            "horizon_release_complete": False,
            "production_methodology_source": "5DR_V2_1_FROZEN",
        },
    }
