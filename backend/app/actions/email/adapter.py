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
        string_fields = (
            "language",
            "equipment_label",
            "serial_number",
            "purchase_date",
            "invoice_number",
            "issue_description",
            "company_name",
            "purchase_country",
            "contract_reference",
            "case_id",
            "incident_id",
        )
        documents = payload.get("documents", [])
        if any(key in payload and not isinstance(payload[key], str) for key in string_fields):
            return self._failure(action, "invalid_payload")
        if not isinstance(documents, list) or any(
            not isinstance(doc, dict) or any(not isinstance(v, str) for v in doc.values())
            for doc in documents
        ):
            return self._failure(action, "invalid_payload")
        recipient = payload.get("to")
        if recipient is not None and not isinstance(recipient, str):
            return self._failure(action, "invalid_payload")
        if not isinstance(recipient, str) or not re.fullmatch(
            r"[^\s@<>;,]+@[^\s@<>;,]+", recipient
        ):
            return self._failure(action, "missing_recipient")
        cc = payload.get("cc", [])
        cc = [cc] if isinstance(cc, str) else cc
        if not isinstance(cc, list) or any(not isinstance(address, str) for address in cc):
            return self._failure(action, "invalid_payload")
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
            sent_at = datetime.now(UTC).replace(microsecond=0)
            msg = self._render(action, recipient, cc, documents, message_id, sent_at)
            proof = {
                "message_id": message_id,
                "sent_at": sent_at.isoformat(),
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
        sent_at: datetime,
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
            "Date": format_datetime(sent_at),
            "From": self.sender,
            "To": recipient,
            "Subject": f"[WP-{str(action.case_id)[:8]}] {title}",
            "X-WarrantyPilot-Case": str(action.case_id),
            "X-WarrantyPilot-Action": action.idempotency_key,
        }.items():
            msg[key] = value
        if cc:
            msg["Cc"] = ", ".join(cc)
        company = p.get("company_name", "Appelia")
        certificate_refs = ", ".join(
            doc.get("id", "—") for doc in documents if doc.get("kind") == "warranty_certificate"
        )
        country = p.get("purchase_country", "not specified" if english else "non précisé")
        contract = p.get("contract_reference", "not specified" if english else "non précisée")
        requests = {
            Channel.EMAIL_RESELLER: (
                "Nous sollicitons une prise en charge au titre de la garantie standard Jabra. "
                "Veuillez trouver les références de la facture ci-dessous et nous indiquer "
                "les modalités de retour ou de remplacement.",
                "We request service under the Jabra standard warranty. Please find the invoice "
                "references below and advise on return or replacement arrangements.",
            ),
            Channel.EMAIL_MANUFACTURER_SUPPORT: (
                f"Nous sollicitons une prise en charge Jabra Warranty+ au titre du certificat "
                f"{certificate_refs}. Pays d'achat : {country}. Merci de confirmer la procédure.",
                "We request Jabra Warranty+ service under warranty certificate "
                f"{certificate_refs}. "
                f"Purchase country: {country}. Please confirm the service procedure.",
            ),
            Channel.EMAIL_LESSOR: (
                f"Nous demandons une intervention au titre du contrat de location, référence : "
                f"{contract}. Merci de nous indiquer les modalités de réparation ou d'échange.",
                f"We request service under our lease contract, reference: {contract}. "
                "Please advise on repair or exchange arrangements.",
            ),
        }
        lines = [
            "Dear Sir or Madam," if english else "Madame, Monsieur,",
            "",
            requests[self.channel][int(english)],
            "",
        ]
        fields = (
            ("equipment_label", "Équipement", "Equipment"),
            ("serial_number", "Numéro de série", "Serial number"),
            ("purchase_date", "Date d'achat", "Purchase date"),
            ("invoice_number", "Facture", "Invoice"),
            ("issue_description", "Incident", "Issue"),
        )
        for field, fr, en in fields:
            lines.append(f"{en if english else fr}: {p.get(field, '—')}")
        lines.extend(["", "Document references:" if english else "Références des documents :"])
        if not documents:
            lines.append("None provided." if english else "Aucune référence fournie.")
        for doc in documents:
            reference = ";".join(str(doc.get(k, "—")) for k in ("kind", "id", "sha256"))
            msg["X-WarrantyPilot-Document"] = reference
            lines.append(f"Document: {doc.get('filename', '—')} ({reference})")
        lines.extend(["", "Kind regards," if english else "Cordialement,", company])
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
