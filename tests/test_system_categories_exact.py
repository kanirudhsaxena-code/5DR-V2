import unittest
from src.autonomous_acquisition import SYSTEM_CATEGORIES


class SystemCategorySetTests(unittest.TestCase):
    def test_exact_system_categories(self):
        self.assertTupleEqual(SYSTEM_CATEGORIES, ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK"))


if __name__ == "__main__":
    unittest.main()
