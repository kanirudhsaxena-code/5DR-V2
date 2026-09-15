import unittest
from src.acquisition_contract import OUTPUT_CONTRACT_VERSION


class OutputContractVersionTests(unittest.TestCase):
    def test_existing_output_contract_retained(self):
        self.assertEqual(OUTPUT_CONTRACT_VERSION, "5DR_V2_1_2")


if __name__ == "__main__":
    unittest.main()
