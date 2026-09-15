import unittest
from src.acquisition_contract import MODE

class ModeStringTests(unittest.TestCase):
    def test_shadow_mode(self):
        self.assertEqual(MODE, "SHADOW_NON_PUBLISHING")

if __name__ == "__main__":
    unittest.main()
