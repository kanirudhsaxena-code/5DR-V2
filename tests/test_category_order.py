import unittest
from src.autonomous_acquisition import SYSTEM_CATEGORIES

class CategoryOrderTests(unittest.TestCase):
    def test_order_stable(self):
        self.assertEqual(SYSTEM_CATEGORIES[0], "MARKET_TRUST")
        self.assertEqual(SYSTEM_CATEGORIES[-1], "EXECUTION_RISK")

if __name__ == "__main__":
    unittest.main()
