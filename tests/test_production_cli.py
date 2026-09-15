from src.production_cli import _enabled


def test_enabled_only_accepts_true():
    assert _enabled('true') is True
    assert _enabled(' TRUE ') is True
    assert _enabled('false') is False
    assert _enabled('1') is False
    assert _enabled(None) is False
