import unittest

from experiments.bound_live_shadow_judgment import (
    EXPECTED_BUNDLE_SHA256,
    build_bound_judgment,
)


class BoundLiveShadowJudgmentTests(unittest.TestCase):
    def test_judgment_is_exact_bundle_bound_and_methodology_frozen(self):
        judgment = build_bound_judgment(EXPECTED_BUNDLE_SHA256)
        self.assertEqual(judgment["bundle_sha256"], EXPECTED_BUNDLE_SHA256)
        self.assertFalse(judgment["methodology_changed"])
        self.assertTrue(judgment["shadow_only"])
        self.assertFalse(judgment["release_complete"])
        with self.assertRaises(ValueError):
            build_bound_judgment("0" * 64)

    def test_component_scores_are_derived_from_existing_five_point_scale(self):
        judgment = build_bound_judgment()
        scores = judgment["normalized_engine_inputs"]["component_scores"]
        self.assertEqual(scores, {
            "PRICE_STRUCTURE": -2.5,
            "PVPO": 52.5,
            "PARTICIPATION": 40.0,
            "MACRO_CATALYSTS": -12.5,
        })
        raw = judgment["judgment_audit"]["raw_scores"]
        self.assertTrue(all(
            score in {-2, -1, 0, 1, 2}
            for engine in raw.values()
            for score in engine.values()
        ))

    def test_engine_inputs_retain_high_event_and_nonrelease_horizons(self):
        normalized = build_bound_judgment()["normalized_engine_inputs"]
        self.assertEqual(normalized["regime"], "TRANSITION")
        self.assertEqual(normalized["event_shock"], "HIGH")
        self.assertFalse(normalized["event_kill_switch"])
        self.assertTrue(normalized["data_adequate"])
        self.assertEqual(normalized["expected_rr"], 1.8)
        self.assertEqual(set(normalized["horizon_slots"]), {f"D+{i}" for i in range(1, 6)})
        self.assertTrue(all(
            slot["status"] == "SHADOW_ONLY_NON_RELEASED"
            and slot["zone_low"] is None
            and slot["zone_high"] is None
            for slot in normalized["horizon_slots"].values()
        ))


if __name__ == "__main__":
    unittest.main()
