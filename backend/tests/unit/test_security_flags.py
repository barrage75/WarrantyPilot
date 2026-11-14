from pathlib import Path

import pytest

from app.contracts.models import Settings
from app.core.flags import is_enabled, load_features
from app.core.security import SecurityViolation, assert_email_allowed, assert_url_allowed


def test_email_allowlist_is_exact() -> None:
    settings = Settings(email_allowlist=["demo@example.test"])
    assert_email_allowed("demo@example.test", settings)
    assert_email_allowed("DEMO@example.test", settings)
    with pytest.raises(SecurityViolation):
        assert_email_allowed("outside@example.test", settings)


def test_url_allowlist_defaults_to_local_repro_portal_only() -> None:
    settings = Settings()
    assert_url_allowed("http://localhost:8100/forms/claim", settings)
    assert_url_allowed("http://127.0.0.1:8100/support", settings)
    with pytest.raises(SecurityViolation):
        assert_url_allowed("http://127.0.0.1:8001/api/settings", settings)
    with pytest.raises(SecurityViolation):
        assert_url_allowed("https://localhost:8100/", settings)
    with pytest.raises(SecurityViolation):
        assert_url_allowed("http://example.com/", settings)


def test_feature_configuration_is_valid_and_p0_cannot_be_disabled() -> None:
    features = load_features()
    p0_name = next(name for name, item in features.items() if item["priority"] == "P0")
    assert is_enabled(p0_name, Settings(feature_flags={p0_name: False}))
    assert is_enabled("purchase_guard") is False
    assert is_enabled("purchase_guard", Settings(feature_flags={"purchase_guard": True}))


def test_invalid_feature_configuration_is_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "features.yaml"
    invalid.write_text("features: {x: {priority: P9, default_enabled: false}}")
    with pytest.raises(ValueError):
        load_features(invalid)
