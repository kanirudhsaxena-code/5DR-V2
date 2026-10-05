import json
import unittest
from datetime import date, timedelta

from bt100.backfill_plan import build_plan


class Bt100BackfillPlanTests(unittest.TestCase):
    def target_doc(self):
        start = date(2026, 1, 1)
        sessions = []
        for i in range(100):
            target = start + timedelta(days=i)
            sessions.append({
                "target_date": target.isoformat(),
                "horizon_dates": {
                    f"D+{h}": (target + timedelta(days=h-1)).isoformat()
                    for h in range(1, 6)
                },
            })
        return {"sessions": sessions}

    def test_plan_is_read_only_and_hashed(self):
        plan = build_plan(self.target_doc())
        self.assertTrue(plan["read_only_plan"])
        self.assertEqual(plan["production_writes"], 0)
        self.assertEqual(plan["production_neuron_calls"], 0)
        self.assertFalse(plan["trading_enabled"])
        self.assertEqual(len(plan["plan_sha256"]), 64)
        by_id = {row["variable_id"]: row for row in plan["variables"]}
        self.assertIn("NIFTY_PRICE_CANDLES", by_id)
        self.assertIn("INDIA_VIX", by_id)
        self.assertIn("GLOBAL_RISK_INDICES", by_id)
        nifty = by_id["NIFTY_PRICE_CANDLES"]
        by_tf = {row["timeframe"]: row for row in nifty["timeframes"]}
        self.assertEqual(by_tf["5m"]["desired_end"], plan["last_outcome_date"])
        self.assertLess(by_tf["5m"]["desired_start"], plan["first_target_date"])
        self.assertGreater(len(by_tf["5m"]["chunks"]), 1)

    def test_plan_requires_exact_100_sessions(self):
        doc = self.target_doc()
        doc["sessions"].pop()
        with self.assertRaises(ValueError):
            build_plan(doc)


if __name__ == "__main__":
    unittest.main()
