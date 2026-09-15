import unittest
from src.autonomous_acquisition import SYSTEM_CATEGORIES


class OwnershipMixTests(unittest.TestCase):
    def test_screenshot_categories_not_accepted_as_system_evidence(self):
        self.assertTrue(set(SYSTEM_CATEGORIES).isdisjoint({"PRICE_TECHNICALS", "DERIVATIVES_OI"}))


if __name__ == "__main__":
    unittest.main()
