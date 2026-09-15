import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import build_evidence_envelope


class RequestBindingTests(unittest.TestCase):
    def test_request_id_preserved_exactly(self):
        request_id = "5drreq_1234"
        envelope = build_evidence_envelope(request_id, [], now=datetime.now(timezone.utc))
        self.assertEqual(envelope["request_id"], request_id)


if __name__ == "__main__":
    unittest.main()
