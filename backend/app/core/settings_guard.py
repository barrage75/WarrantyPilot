from app.contracts.models import Settings
from app.core.settings import AppSettings

DEMO_BROWSER_ORIGINS = frozenset({"http://127.0.0.1:8100", "http://localhost:8100"})


def _email_domain(entry: str) -> str:
    return entry.rsplit("@", 1)[-1].strip().casefold()


def settings_violations(candidate: Settings, app_settings: AppSettings) -> list[str]:
    violations: list[str] = []
    if candidate.auto_send_threshold_eur > app_settings.max_auto_threshold_eur:
        violations.append(
            f"auto_send_threshold_eur exceeds the maximum of {app_settings.max_auto_threshold_eur}"
        )
    if app_settings.demo_mode:
        for entry in candidate.email_allowlist:
            domain = _email_domain(entry)
            if not domain.endswith(".example") or domain.startswith("*") or "*" in domain:
                violations.append(f"email_allowlist entry {entry!r} is not a *.example domain")
        for origin in candidate.browser_allowed_origins:
            if origin.rstrip("/").casefold() not in DEMO_BROWSER_ORIGINS:
                violations.append(f"browser origin {origin!r} is not allowed in demo")
    return violations
