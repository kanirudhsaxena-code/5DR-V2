import unittest

from experiments.macro_enriched_shadow_judgment import (
    EXPECTED_BUNDLE_SHA256,
    build_macro_enriched_judgment,
)


class MacroEnrichedShadowJudgmentTests(unittest.TestCase):
    def test_exact_bundle_binding_and_no_methodology_change(self):
        judgment = build_macro_enriched_judgment()
        self.assertEqual(judgment["bundle_sha256"], EXPECTED_BUNDLE_SHA256)
        self.assertFalse(judgment["methodology_changed"])
        self.assertTrue(judgment["shadow_only"])
        with self.assertRaises(ValueError):
            build_macro_enriched_judgment("0" * 64)

    def test_component_scores_use_existing_five_point_scale(self):
        judgment = build_macro_enriched_judgment()
        self.assertEqual(judgment["normalized_engine_inputs"]["component_scores"], {
            "PRICE_STRUCTURE": -10.0,
            "PVPO": 52.5,
            "PARTICIPATION": 40.0,
            "MACRO_CATALYSTS": -42.5,
        })
        raw = judgment["judgment_audit"]["raw_scores"]
        self.assertTrue(all(
            score in {-2, -1, 0, 1, 2}
            for engine in raw.values()
            for score in engine.values()
        ))

    def test_event_shock_is_high_but_not_kill_switch(self):
        normalized = build_macro_enriched_judgment()["normalized_engine_inputs"]
        self.assertEqual(normalized["regime"], "EVENT_SHOCK")
        self.assertEqual(normalized["event_shock"], "HIGH")
        self.assertFalse(normalized["event_kill_switch"])
        self.assertEqual(normalized["expected_rr"], 1.8)


if __name__ == "__main__":
    unittest.main()
