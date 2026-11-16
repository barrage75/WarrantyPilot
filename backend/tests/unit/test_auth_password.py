from app.core.auth import password_matches
from app.core.settings import AppSettings


def test_demo_any_password_setting_defaults_to_enabled_and_reads_environment(
    monkeypatch,
) -> None:
    monkeypatch.delenv("WP_DEMO_ANY_PASSWORD", raising=False)
    assert AppSettings(_env_file=None).demo_any_password is True

    monkeypatch.setenv("WP_DEMO_ANY_PASSWORD", "false")
    assert AppSettings(_env_file=None).demo_any_password is False


def test_development_demo_accepts_any_password_including_empty() -> None:
    settings = AppSettings(environment="dev", demo_any_password=True)

    assert password_matches("wrong", settings)
    assert password_matches("", settings)


def test_development_demo_flag_can_disable_any_password() -> None:
    settings = AppSettings(
        environment="dev",
        demo_any_password=False,
        demo_password="configured-secret",
    )

    assert password_matches("configured-secret", settings)
    assert not password_matches("wrong", settings)
    assert not password_matches("", settings)


def test_any_password_flag_has_no_effect_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("WP_ENV", "production")
    settings = AppSettings(
        _env_file=None,
        demo_any_password=True,
        demo_password="configured-secret",
    )

    assert settings.environment == "production"
    assert password_matches("configured-secret", settings)
    assert not password_matches("wrong", settings)
    assert not password_matches("", settings)
