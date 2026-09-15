import unittest
from src.upstox_evidence import _source_ref


class ProvenanceDigestTests(unittest.TestCase):
    def test_upstox_ref_contains_sha256(self):
        ref = _source_ref({"source_path": "/v2/option/chain", "sha256": "a" * 64})
        self.assertEqual(ref, "upstox:/v2/option/chain#sha256=" + "a" * 64)


if __name__ == "__main__":
    unittest.main()
