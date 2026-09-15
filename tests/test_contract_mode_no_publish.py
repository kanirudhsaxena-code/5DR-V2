import unittest
from src.acquisition_contract import MODE


class ContractPublishGuardTests(unittest.TestCase):
    def test_contract_does_not_claim_production(self):
        self.assertNotIn("PRODUCTION", MODE)
        self.assertIn("NON_PUBLISHING", MODE)


if __name__ == "__main__":
    unittest.main()
