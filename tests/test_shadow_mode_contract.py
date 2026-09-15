import unittest
from src.acquisition_contract import MODE


class ShadowModeContractTests(unittest.TestCase):
    def test_mode_is_non_publishing(self):
        self.assertEqual(MODE, "SHADOW_NON_PUBLISHING")


if __name__ == "__main__":
    unittest.main()
