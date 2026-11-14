import base64
import json
import mailbox
import smtplib
from collections.abc import Callable
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.contracts.enums import RealityBadge


class MailTransport(Protocol):
    badge: RealityBadge
    name: str

    def send(self, msg: EmailMessage) -> None: ...
    def find_sent(self, message_id: str) -> bool: ...
    def fetch_replies(self) -> list[EmailMessage]: ...


def parse_message(raw: bytes) -> EmailMessage:
    return BytesParser(policy=policy.default).parsebytes(raw)


class LocalSmtpTransport:
    badge = RealityBadge.REPRODUCTION
    name = "smtp-local"

    def __init__(self, port: int, maildir_path: str | Path, host: str = "127.0.0.1") -> None:
        if host != "127.0.0.1":
            raise ValueError("SMTP local uniquement")
        self.host, self.port = host, port
        self.maildir = mailbox.Maildir(str(maildir_path), create=True)
        self.sent = self.maildir.add_folder("sent")

    def send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=10) as client:
            client.send_message(msg)
        self.sent.add(msg.as_bytes())
        self.sent.flush()

    def find_sent(self, message_id: str) -> bool:
        return any(m.get("Message-ID") == message_id for m in self.sent)

    def fetch_replies(self) -> list[EmailMessage]:
        return [parse_message(m.as_bytes()) for m in self.maildir]


SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
)
Http = Callable[[Request], dict[str, Any]]


def http_json(request: Request) -> dict[str, Any]:
    with urlopen(request, timeout=20) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError("Réponse HTTP invalide")
    return value


def refresh_token_provider(
    client_id: str, client_secret: str, refresh_token: str, http: Http = http_json
) -> Callable[[], str]:
    def provide() -> str:
        data = urlencode(
            dict(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                grant_type="refresh_token",
            )
        ).encode()
        result = http(Request("https://oauth2.googleapis.com/token", data=data))
        token = result.get("access_token")
        if not isinstance(token, str) or not token:
            raise ValueError("Jeton OAuth absent")
        return token

    return provide


class GmailTransport:
    badge = RealityBadge.REAL
    name = "gmail"
    base = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

    def __init__(
        self,
        token_provider: Callable[[], str],
        label_id: str,
        scopes: tuple[str, ...] = SCOPES,
        http: Http = http_json,
    ) -> None:
        if scopes != SCOPES or not label_id:
            raise ValueError("Deux scopes Gmail et un libellé sont requis")
        self.token_provider, self.label_id, self.http = token_provider, label_id, http

    def _request(self, suffix: str, data: dict[str, str] | None = None) -> dict[str, Any]:
        return self.http(
            Request(
                self.base + suffix,
                data=json.dumps(data).encode() if data else None,
                headers={
                    "Authorization": "Bearer " + self.token_provider(),
                    "Content-Type": "application/json",
                },
            )
        )

    def send(self, msg: EmailMessage) -> None:
        self._request("/send", {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()})

    def find_sent(self, message_id: str) -> bool:
        return bool(
            self._request("?" + urlencode({"q": f"rfc822msgid:{message_id} in:sent"})).get(
                "messages"
            )
        )

    def fetch_replies(self) -> list[EmailMessage]:
        replies = []
        page = ""
        while True:
            query = {"labelIds": self.label_id}
            if page:
                query["pageToken"] = page
            result = self._request("?" + urlencode(query))
            for item in result.get("messages", []):
                value = self._request("/" + str(item["id"]) + "?format=raw")
                if self.label_id in value.get("labelIds", []):
                    raw = str(value["raw"])
                    replies.append(
                        parse_message(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
                    )
            page = result.get("nextPageToken", "")
            if not page:
                return replies
