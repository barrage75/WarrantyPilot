"""Hard-coded navigation allowlist for the browser portal adapter.

Only the local Dell reproduction may ever be opened. Extra loopback origins are
accepted solely in test mode, so an integration test can start the
reproduction on a free port without widening the production allowlist.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from app.actions.browser.errors import PortalError, PortalErrorCode

PRODUCTION_ORIGINS: frozenset[str] = frozenset({"127.0.0.1:8100", "localhost:8100"})
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost"})
INERT_URLS: frozenset[str] = frozenset({"about:blank"})


def origin_of(url: str) -> str | None:
    """Return ``host:port`` for a plain ``http`` URL, or ``None`` if it is not one."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme != "http" or not parts.hostname or parts.username or parts.password:
        return None
    return f"{parts.hostname.lower()}:{port or 80}"


class UrlAllowlist:
    def __init__(self, *, test_origins: Iterable[str] = (), test_mode: bool = False) -> None:
        extra = frozenset(origin.strip().lower() for origin in test_origins if origin.strip())
        if extra and not test_mode:
            raise ValueError("extra allowlist origins are only accepted in test mode")
        for origin in extra:
            host, _, port = origin.rpartition(":")
            if host not in LOOPBACK_HOSTS or not port.isdigit():
                raise ValueError(f"test origin must be a loopback host:port, got {origin!r}")
        self.origins: frozenset[str] = PRODUCTION_ORIGINS | extra

    @classmethod
    def for_test_port(cls, port: int) -> UrlAllowlist:
        return cls(test_origins=(f"127.0.0.1:{port}", f"localhost:{port}"), test_mode=True)

    def allows(self, url: str) -> bool:
        return origin_of(url) in self.origins

    def allows_navigation(self, url: str) -> bool:
        return url in INERT_URLS or self.allows(url)

    def require(self, url: str) -> str:
        if not self.allows(url):
            raise PortalError(PortalErrorCode.URL_NOT_ALLOWED, url)
        return url

    def browser_use_domains(self) -> list[str]:
        return sorted(self.origins)
