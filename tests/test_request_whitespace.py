import unittest
from src.autonomous_acquisition import AcquisitionBlocked, build_evidence_envelope

class RequestWhitespaceTests(unittest.TestCase):
    def test_whitespace_request_id_blocks(self):
        with self.assertRaisesRegex(AcquisitionBlocked, "REQUEST_ID_REQUIRED"):
            build_evidence_envelope("   ", [])

if __name__ == "__main__":
    unittest.main()
