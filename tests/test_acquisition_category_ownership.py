import unittest
from src.autonomous_acquisition import SYSTEM_CATEGORIES


class AcquisitionOwnershipTests(unittest.TestCase):
    def test_user_screenshot_categories_are_not_system_categories(self):
        self.assertEqual(set(SYSTEM_CATEGORIES), {"MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK"})
        self.assertNotIn("PRICE_TECHNICALS", SYSTEM_CATEGORIES)
        self.assertNotIn("DERIVATIVES_OI", SYSTEM_CATEGORIES)


if __name__ == "__main__":
    unittest.main()
