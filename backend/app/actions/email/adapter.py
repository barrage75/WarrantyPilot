import asyncio
import hashlib
import json
import re
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Any

from app.actions.email.ledger import SentLedger
from app.actions.email.transports import MailTransport
from app.contracts.enums import ActionResultStatus, Channel
from app.contracts.models import Action, ActionResult, Settings
from app.core.security import assert_email_allowed

CHANNELS = (Channel.EMAIL_RESELLER, Channel.EMAIL_MANUFACTURER_SUPPORT, Channel.EMAIL_LESSOR)
_SEND_LOCK = threading.Lock()


class EmailActionAdapter:
    def __init__(
        self,
        channel: Channel,
        transport: MailTransport,
        settings_provider: Callable[[], Settings],
        sender: str,
        ledger: SentLedger,
        ai_disclosure: bool = True,
    ) -> None:
        if channel not in CHANNELS:
            raise ValueError("Canal e-mail requis")
        self.channel, self.transport = channel, transport
        self.badge = transport.badge
        self.settings_provider, self.sender = settings_provider, sender
        self.ledger, self.ai_disclosure = ledger, ai_disclosure

    async def execute(self, action: Action) -> ActionResult:
        try:
            return await asyncio.to_thread(self._execute, action)
        except Exception as error:
            return self._failure(action, "transport_error:" + type(error).__name__)

    def _failure(self, action: Action, error: str) -> ActionResult:
        return ActionResult(
            action_id=action.id, badge=self.badge, status=ActionResultStatus.FAILURE, error=error
        )

    def _execute(self, action: Action) -> ActionResult:
        payload = action.payload
        recipient = payload.get("to")
        if not isinstance(recipient, str) or not re.fullmatch(
            r"[^\s@<>;,]+@[^\s@<>;,]+", recipient
        ):
            return self._failure(action, "missing_recipient")
        cc = payload.get("cc", [])
        cc = [cc] if isinstance(cc, str) else cc
        try:
            if not isinstance(cc, list):
                raise ValueError("cc")
            settings = self.settings_provider()
            for address in [recipient, *cc]:
                if (
                    not isinstance(address, str)
                    or not re.fullmatch(r"[^\s@<>;,]+@[^\s@<>;,]+", address)
                    or not address.rsplit("@", 1)[1].casefold().endswith(".example")
                ):
                    raise ValueError("recipient")
                assert_email_allowed(address, settings)
        except Exception:
            return self._failure(action, "recipient_not_allowed")
        documents = payload.get("documents", [])
        if self.channel == Channel.EMAIL_MANUFACTURER_SUPPORT and not any(
            d.get("kind") == "warranty_certificate" for d in documents
        ):
            return self._failure(action, "missing_certificate")
        message_id = (
            "<wp-"
            + hashlib.sha256(action.idempotency_key.encode()).hexdigest()[:32]
            + "@warrantypilot.local>"
        )
        with _SEND_LOCK:
            prior = self.ledger.get(action.idempotency_key)
            already_sent = bool(prior and prior.get("state") == "sent")
            found = False if already_sent else self.transport.find_sent(message_id)
            if (prior and prior.get("state") == "sent") or found:
                proof = (
                    dict(prior["proof"])
                    if prior and prior.get("proof")
                    else {
                        "message_id": message_id,
                        "recipient": recipient,
                        "transport": self.transport.name,
                        "channel": self.channel.value,
                        "sent_at": None,
                        "content_sha256": None,
                    }
                )
                proof["duplicate_suppressed"] = True
                if prior and prior.get("state") != "sent" and found:
                    self.ledger.record(
                        action.idempotency_key, dict(prior, state="sent", proof=proof)
                    )
                return ActionResult(
                    action_id=action.id,
                    badge=self.badge,
                    status=ActionResultStatus.SUCCESS,
                    proof=json.dumps(proof),
                )
            if prior:
                return self._failure(action, "unknown_outcome_manual_check")
            msg = self._render(action, recipient, cc, documents, message_id)
            proof = {
                "message_id": message_id,
                "sent_at": datetime.now(UTC).isoformat(),
                "recipient": recipient,
                "content_sha256": hashlib.sha256(msg.as_bytes()).hexdigest(),
                "transport": self.transport.name,
                "channel": self.channel.value,
            }
            entry = {"case_id": str(action.case_id), "message_id": message_id, "proof": proof}
            self.ledger.record(action.idempotency_key, dict(entry, state="sending"))
            self.transport.send(msg)
            self.ledger.record(action.idempotency_key, dict(entry, state="sent"))
            return ActionResult(
                action_id=action.id,
                badge=self.badge,
                status=ActionResultStatus.SUCCESS,
                proof=json.dumps(proof),
            )

    def _render(
        self,
        action: Action,
        recipient: str,
        cc: list[str],
        documents: list[dict[str, Any]],
        message_id: str,
    ) -> EmailMessage:
        p = action.payload
        english = p.get("language") == "en"
        titles = {
            Channel.EMAIL_RESELLER: ("Garantie standard Jabra", "Jabra standard warranty claim"),
            Channel.EMAIL_MANUFACTURER_SUPPORT: (
                "Garantie Jabra Warranty+",
                "Jabra Warranty+ claim",
            ),
            Channel.EMAIL_LESSOR: ("Demande de prise en charge location", "Lease service request"),
        }
        title = titles[self.channel][int(english)]
        msg = EmailMessage()
        for key, value in {
            "Message-ID": message_id,
            "Date": format_datetime(datetime.now(UTC)),
            "From": self.sender,
            "To": recipient,
            "Subject": title,
            "X-WarrantyPilot-Case": str(action.case_id),
            "X-WarrantyPilot-Action": action.idempotency_key,
        }.items():
            msg[key] = value
        if cc:
            msg["Cc"] = ", ".join(cc)
        lines = [title, str(p.get("company_name", "Appelia"))]
        fields = (
            ("equipment_label", "Équipement", "Equipment"),
            ("serial_number", "Numéro de série", "Serial number"),
            ("purchase_date", "Date d'achat", "Purchase date"),
            ("invoice_number", "Facture", "Invoice"),
            ("issue_description", "Incident", "Issue"),
        )
        for field, fr, en in fields:
            lines.append(f"{en if english else fr}: {p.get(field, '—')}")
        for doc in documents:
            reference = ";".join(str(doc.get(k, "—")) for k in ("kind", "id", "sha256"))
            msg["X-WarrantyPilot-Document"] = reference
            lines.append(f"Document: {doc.get('filename', '—')} ({reference})")
        if self.ai_disclosure:
            msg["X-WarrantyPilot-AI"] = "generated"
            lines.append(
                "Prepared with AI assistance (WarrantyPilot) on behalf of Appelia"
                if english
                else "Préparé avec l'assistance d'une IA (WarrantyPilot) pour le compte d'Appelia"
            )
        msg.set_content("\n".join(lines))
        return msg


def build_email_adapters(
    transport: MailTransport,
    settings_provider: Callable[[], Settings],
    sender: str,
    ledger: SentLedger,
    ai_disclosure: bool = True,
) -> dict[Channel, EmailActionAdapter]:
    return {
        c: EmailActionAdapter(c, transport, settings_provider, sender, ledger, ai_disclosure)
        for c in CHANNELS
    }
