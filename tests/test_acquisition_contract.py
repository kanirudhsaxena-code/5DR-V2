import unittest
from src.acquisition_contract import ACQUISITION_CONTRACT_VERSION, FRAMEWORK_VERSION, OUTPUT_CONTRACT_VERSION, MODE


class AcquisitionContractTests(unittest.TestCase):
    def test_contract_is_shadow_and_framework_compatible(self):
        self.assertEqual(ACQUISITION_CONTRACT_VERSION, "5DR_ACQUISITION_SHADOW_V1")
        self.assertEqual(FRAMEWORK_VERSION, "5DR_V2_1")
        self.assertEqual(OUTPUT_CONTRACT_VERSION, "5DR_V2_1_2")
        self.assertEqual(MODE, "SHADOW_NON_PUBLISHING")


if __name__ == "__main__":
    unittest.main()
