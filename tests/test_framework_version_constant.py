import unittest
from src.acquisition_contract import FRAMEWORK_VERSION


class FrameworkVersionTests(unittest.TestCase):
    def test_existing_framework_version_retained(self):
        self.assertEqual(FRAMEWORK_VERSION, "5DR_V2_1")


if __name__ == "__main__":
    unittest.main()
