"""Read-only mailbox boundaries, compatible with the local SMTP Maildir."""

import mailbox
from collections.abc import Callable
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from app.actions.email.transports import (
    SCOPES,
    Http,
    http_json,
    parse_message,
)
from app.actions.email.transports import (
    GmailTransport as ActionGmailTransport,
)
from app.contracts.enums import RealityBadge

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class Inbox(Protocol):
    badge: RealityBadge

    def fetch_replies(self) -> list[EmailMessage]: ...


class MaildirInbox:
    badge = RealityBadge.REPRODUCTION

    def __init__(self, path: Path = Path("runtime/inbox")) -> None:
        for folder in ("cur", "new", "tmp"):
            (path / folder).mkdir(parents=True, exist_ok=True)
        self.maildir = mailbox.Maildir(str(path), create=True)

    def fetch_replies(self) -> list[EmailMessage]:
        # Only the inbox, never the .sent folder used by LocalSmtpTransport.
        return [parse_message(message.as_bytes()) for message in self.maildir]


class GmailTransport:
    """Expose only GET operations of the existing Gmail transport.

    OAuth consent/token provisioning is external; callers supply a token granted
    gmail.readonly. No send scope is requested and no mutation is exposed here.
    """

    badge = RealityBadge.REAL

    def __init__(
        self,
        token_provider: Callable[[], str],
        label_id: str,
        *,
        scopes: tuple[str, ...] = (READONLY_SCOPE,),
        http: Http = http_json,
    ) -> None:
        if scopes != (READONLY_SCOPE,):
            raise ValueError("Intake requires gmail.readonly only")
        # Existing transport insists on its two-scope configuration even for GET.
        # This argument is validation metadata; it does not request OAuth consent.
        self._reader = ActionGmailTransport(token_provider, label_id, scopes=SCOPES, http=http)

    def fetch_replies(self) -> list[EmailMessage]:
        return self._reader.fetch_replies()
