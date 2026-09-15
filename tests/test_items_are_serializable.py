import json
import unittest
from datetime import datetime, timezone
from src.autonomous_acquisition import SourceObservation, build_evidence_envelope

class SerializationTests(unittest.TestCase):
    def test_envelope_json_serializable(self):
        now = datetime.now(timezone.utc)
        e = build_evidence_envelope("5drreq_json", [SourceObservation(c, f"source:{c}", now.isoformat()) for c in ("MARKET_TRUST", "EVENT_SHOCK", "EXECUTION_RISK")], now=now)
        json.dumps(e)

if __name__ == "__main__":
    unittest.main()
