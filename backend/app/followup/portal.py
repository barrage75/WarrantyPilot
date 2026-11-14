from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from http.client import HTTPException
from typing import Any
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.actions.browser.allowlist import UrlAllowlist
from app.actions.browser.errors import PortalError
from app.contracts.enums import CaseStatus
from app.contracts.models import Case
from app.followup.clock import Clock, FollowUpClock, utc_now

ORIGIN = "http://127.0.0.1:8100"
STATUS_MAP = {
    "received": CaseStatus.TRACKED,
    "in_progress": CaseStatus.TRACKED,
    "part_shipped": CaseStatus.TRACKED,
    "closed": CaseStatus.RESOLVED,
}
ACTIVE_STATUSES = frozenset({CaseStatus.SENT, CaseStatus.TRACKED})


@dataclass(frozen=True)
class PortalReference:
    case_number: str
    url: str

    @classmethod
    def from_number(cls, number: str) -> "PortalReference":
        return cls(number, f"{ORIGIN}/support/status/{number}")

    def validate(self) -> None:
        if (
            len(self.case_number) != 10
            or not self.case_number.isascii()
            or not self.case_number.isdigit()
        ):
            raise ValueError("Numéro de dossier Dell invalide")
        UrlAllowlist().require(self.url)
        if self.url != f"{ORIGIN}/support/status/{self.case_number}":
            raise ValueError("Seule la page de statut Dell sur 127.0.0.1:8100 est autorisée")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise ValueError("Redirection du portail refusée")


def fetch_status_page(url: str) -> str:
    number = url.rsplit("/", 1)[-1]
    PortalReference(number, url).validate()
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(Request(url, headers={"Accept": "text/html"}), timeout=10) as response:
        if response.status != 200 or response.headers.get_content_type() != "text/html":
            raise ValueError("Réponse du portail invalide")
        content: bytes = response.read(1_000_001)
    if len(content) > 1_000_000:
        raise ValueError("Page de statut trop volumineuse")
    return content.decode("utf-8")


class _StatusParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.numbers: list[str | None] = []
        self.statuses: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id") == "case-number":
            self.numbers.append(values.get("data-case-number"))
        if values.get("id") == "case-status":
            self.statuses.append(values.get("data-status"))


class DellPortalFollowUp:
    def __init__(
        self,
        resolve_reference: Callable[[Case], PortalReference | None],
        *,
        clock: Clock = utc_now,
        demo_today: date | None = None,
        fetch_page: Callable[[str], str] = fetch_status_page,
    ) -> None:
        self.resolve_reference, self.fetch_page = resolve_reference, fetch_page
        self.clock = FollowUpClock(clock, demo_today)

    def check(self, case: Case) -> list[dict[str, Any]]:
        if case.status not in ACTIVE_STATUSES:
            return []
        reference = self.resolve_reference(case)
        if reference is None:
            return []
        observed = self.clock.now().isoformat()
        try:
            reference.validate()
            parser = _StatusParser()
            parser.feed(self.fetch_page(reference.url))
            if parser.numbers != [reference.case_number] or len(parser.statuses) != 1:
                raise ValueError("Page de statut absente, ambiguë ou associée à un autre dossier")
            portal_status = parser.statuses[0]
            if portal_status not in STATUS_MAP:
                raise ValueError("Statut Dell inconnu")
        except (ValueError, OSError, URLError, HTTPException, PortalError) as exc:
            return [
                {
                    "kind": "followup_error",
                    "case_id": str(case.id),
                    "code": "portal_unavailable_or_invalid",
                    "error_type": type(exc).__name__,
                    "observed_at": observed,
                    "reality": "reproduction",
                }
            ]
        return [
            {
                "kind": "portal_status",
                "case_id": str(case.id),
                "status": STATUS_MAP[portal_status].value,
                "proof": {
                    "url": reference.url,
                    "case_number": reference.case_number,
                    "portal_status": portal_status,
                    "observed_at": observed,
                },
                "reality": "reproduction",
                "untrusted": True,
            }
        ]
