import copy
import unittest

from experiments.upstox_5dr_coverage import ROWS, coverage_matrix, validate_coverage_matrix
from phase1.upstox import PipelineError


class CoverageTests(unittest.TestCase):
    def test_matrix_is_complete_and_unique(self):
        self.assertGreaterEqual(validate_coverage_matrix(), 30)
        matrix = coverage_matrix()
        self.assertEqual(matrix["schema"], "5dr-upstox-coverage-v1")
        ids = [row["id"] for row in matrix["rows"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_required_web_only_context_is_not_faked_as_upstox(self):
        by_id = {row["id"]: row for row in ROWS}
        for key in ("dxy", "rates", "scheduled_macro", "geopolitics"):
            self.assertEqual(by_id[key]["validation_state"], "WEB_REQUIRED")
            self.assertNotEqual(by_id[key]["availability"], "PROVEN")

    def test_global_latency_is_dynamic_not_invented(self):
        globals_ = [row for row in ROWS if row["id"] in {
            "gift_nifty", "sp500", "dow_jones", "us_tech_100", "nikkei_225",
            "hang_seng", "dax", "ftse_100", "brent", "wti", "usd_inr",
        }]
        self.assertEqual(len(globals_), 11)
        self.assertTrue(all(row["latency"] == "PROVIDER_DECLARED_FROM_GLOBAL_MASTER" for row in globals_))

    def test_duplicate_id_fails_closed(self):
        broken = copy.deepcopy(ROWS)
        broken.append(copy.deepcopy(broken[0]))
        with self.assertRaises(PipelineError):
            validate_coverage_matrix(broken)


if __name__ == "__main__":
    unittest.main()
