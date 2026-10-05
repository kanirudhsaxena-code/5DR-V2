import unittest

from bt100.as_of import LeakageError, freeze_manifest


class Bt100AsOfTests(unittest.TestCase):
    def record(self, **overrides):
        row = {
            "role": "PVPO",
            "observed_at": "2026-06-01T08:55:00+05:30",
            "available_at": "2026-06-01T08:56:00+05:30",
            "source_ref": "upstox:test",
            "content_sha256": "a" * 64,
        }
        row.update(overrides)
        return row

    def test_point_in_time_manifest_freezes(self):
        manifest = freeze_manifest(
            [self.record()],
            "2026-06-01T09:14:59+05:30",
        )
        self.assertEqual(manifest["schema"], "bt100-evidence-manifest-v1")
        self.assertEqual(len(manifest["manifest_sha256"]), 64)

    def test_observed_after_cutoff_fails(self):
        with self.assertRaises(LeakageError):
            freeze_manifest(
                [self.record(observed_at="2026-06-01T09:15:00+05:30")],
                "2026-06-01T09:14:59+05:30",
            )

    def test_late_publication_fails_even_if_event_was_earlier(self):
        with self.assertRaises(LeakageError):
            freeze_manifest(
                [self.record(
                    observed_at="2026-06-01T08:00:00+05:30",
                    available_at="2026-06-01T10:00:00+05:30",
                )],
                "2026-06-01T09:14:59+05:30",
            )

    def test_outcome_evidence_is_forbidden_in_forecast_manifest(self):
        with self.assertRaises(LeakageError):
            freeze_manifest(
                [self.record(role="OUTCOME")],
                "2026-06-01T09:14:59+05:30",
            )

    def test_naive_timestamp_fails(self):
        with self.assertRaises(LeakageError):
            freeze_manifest(
                [self.record(available_at="2026-06-01T08:56:00")],
                "2026-06-01T09:14:59+05:30",
            )


if __name__ == "__main__":
    unittest.main()
