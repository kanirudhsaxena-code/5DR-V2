import pytest

from src.core_zone_shadow import CoreZoneShadowError, build_nifty_core_shadow


def rows(horizons=("D", "D+1", "D+2", "D+3", "D+4")):
    return [
        {"horizon": h, "target_session": f"session-{i}", "expected_centre": 100+i,
         "core_low": 99+i, "core_high": 101+i, "outer_low": 98+i,
         "outer_high": 102+i, "verification_state": "VERIFIED"}
        for i, h in enumerate(horizons)
    ]


def build(**overrides):
    args = dict(run_id="run-1", issuance_id="issue-1", calibration_version="cal-v1",
                evidence_refs=["evidence://1"], horizons=rows())
    args.update(overrides)
    return build_nifty_core_shadow(**args)


def test_build_is_deterministic_and_exactly_d_through_d4():
    first = build()
    second = build()
    assert first == second
    assert [r["horizon"] for r in first["horizons"]] == ["D", "D+1", "D+2", "D+3", "D+4"]
    assert first["engine"] == "EDGE_NIFTY" and first["mode"] == "SHADOW"
    assert len(first["report_hash"]) == 64


@pytest.mark.parametrize("bad", [
    ("D+1", "D+2", "D+3", "D+4", "D+5"),
    ("D", "D+1", "D+2", "D+3"),
    ("D", "D+2", "D+1", "D+3", "D+4"),
])
def test_horizon_deviation_fails_closed(bad):
    with pytest.raises(ValueError):
        build(horizons=rows(bad))


def test_missing_evidence_and_unverified_rows_fail_closed():
    with pytest.raises(CoreZoneShadowError):
        build(evidence_refs=[])
    bad = rows()
    bad[0]["verification_state"] = "SYNTHETIC"
    with pytest.raises(CoreZoneShadowError):
        build(horizons=bad)


def test_core_must_be_nested_inside_outer_around_centre():
    bad = rows()
    bad[0]["core_low"] = 97
    with pytest.raises(CoreZoneShadowError):
        build(horizons=bad)
