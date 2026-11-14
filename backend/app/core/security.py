from urllib.parse import urlsplit

from app.contracts.models import Settings


class SecurityViolation(PermissionError):
    pass


def assert_email_allowed(addr: str, settings: Settings) -> None:
    candidate = addr.strip().casefold()
    allowed = {item.strip().casefold() for item in settings.email_allowlist}
    if not candidate or candidate not in allowed:
        raise SecurityViolation("email address is not on the allowlist")


def _matches_origin(url: str, allowed_origin: str) -> bool:
    candidate = urlsplit(url)
    allowed = urlsplit(allowed_origin)
    if candidate.scheme != "http" or allowed.scheme != "http":
        return False
    if candidate.username or candidate.password or not candidate.hostname:
        return False
    if allowed.path not in {"", "/"} or allowed.query or allowed.fragment:
        return False
    if candidate.hostname.casefold() != (allowed.hostname or "").casefold():
        return False
    if allowed.netloc.endswith(":*"):
        return candidate.hostname in {"localhost", "127.0.0.1"}
    try:
        return candidate.port == allowed.port
    except ValueError:
        return False


def assert_url_allowed(url: str, settings: Settings) -> None:
    try:
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError as error:
        raise SecurityViolation("URL is malformed or has an invalid port") from error
    if not parsed.hostname or not any(
        _matches_origin(url, origin) for origin in settings.browser_allowed_origins
    ):
        raise SecurityViolation("URL origin is not on the allowlist")
