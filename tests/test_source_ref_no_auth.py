import unittest
from src.upstox_evidence import _source_ref


class SourceRefSecretTests(unittest.TestCase):
    def test_ref_has_no_authorization_material(self):
        ref = _source_ref({"source_path": "/v2/option/chain", "sha256": "f" * 64})
        self.assertNotIn("bearer", ref.lower())
        self.assertNotIn("authorization", ref.lower())
        self.assertNotIn("token", ref.lower())


if __name__ == "__main__":
    unittest.main()
