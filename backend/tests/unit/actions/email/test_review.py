import asyncio
import json
import smtplib
from datetime import datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.actions.email import EmailActionAdapter, EmailReplyChecker, JsonlSentLedger
from app.actions.email.local_smtp_server import LocalSmtpServer
from app.actions.email.replies import KeywordReplyClassifier
from app.actions.email.transports import LocalSmtpTransport
from app.contracts.enums import Channel
from app.contracts.models import Case, Settings
from tests.unit.actions.email.test_email import TO, Transport, action, adapter


async def test_outbound_is_not_reply(tmp_path: Path) -> None:
    sender = "garanties@appelia.example"
    path = tmp_path / "mail"
    async with LocalSmtpServer(str(path)) as server:
        transport = LocalSmtpTransport(server.port, path)
        ledger = JsonlSentLedger(tmp_path / "ledger")
        a = EmailActionAdapter(
            Channel.EMAIL_RESELLER,
            transport,
            lambda: Settings(email_allowlist=[TO]),
            sender,
            ledger,
        )
        act = action()
        result = await a.execute(act)
        assert result.status == "success"
        case = Case(id=act.case_id, incident_id=uuid4())
        checker = EmailReplyChecker(transport, ledger, sender=sender)
        assert checker.check(case) == []
        reply = EmailMessage()
        reply["From"] = TO
        reply["To"] = sender
        reply["Message-ID"] = "<reply@jabra-reseller.example>"
        reply["In-Reply-To"] = json.loads(result.proof or "{}")["message_id"]
        reply.set_content("Approved RMA: AB123")

        def send() -> None:
            with smtplib.SMTP("127.0.0.1", server.port) as client:
                client.send_message(reply)

        await asyncio.to_thread(send)
        replies = checker.check(case)
        assert len(replies) == 1
        assert replies[0]["message_id"] == reply["Message-ID"]
        assert replies[0]["outcome"] == "accepted"


def test_configured_sender_excluded(tmp_path: Path) -> None:
    t = Transport()
    case = Case(incident_id=uuid4())
    msg = EmailMessage()
    msg["From"] = "Warranty <CUSTOM@appelia.example>"
    msg["X-WarrantyPilot-Case"] = str(case.id)
    msg.set_content("accepted")
    t.replies = [msg]
    checker = EmailReplyChecker(
        t, JsonlSentLedger(tmp_path / "ledger"), sender="custom@appelia.example"
    )
    assert checker.check(case) == []


@pytest.mark.parametrize(
    "text,outcome",
    [
        ("informations", "unknown"),
        ("format", "unknown"),
        ("not accepted", "rejected"),
        ("non accepté", "rejected"),
        ("pas accepté", "rejected"),
        ("ne peut pas être accepté", "rejected"),
        ("cannot be accepted", "rejected"),
        ("RMA: AB123", "accepted"),
        ("accepted", "accepted"),
    ],
)
def test_keyword_boundaries(text: str, outcome: str) -> None:
    assert KeywordReplyClassifier().classify({"untrusted_text": text}) == outcome


@pytest.mark.parametrize(
    "payload",
    [
        {"documents": "bad"},
        {"documents": ["bad"]},
        {"documents": [None]},
        {"documents": [{"id": 123}]},
        {"equipment_label": 123},
        {"company_name": None},
        {"purchase_country": []},
        {"contract_reference": {}},
        {"to": 123},
        {"cc": [123]},
    ],
)
async def test_invalid_payload(tmp_path: Path, payload: dict[str, Any]) -> None:
    t = Transport()
    result = await adapter(t, tmp_path / "ledger").execute(action(**payload))
    assert result.error == "invalid_payload"
    assert not t.messages


@pytest.mark.parametrize(
    "channel,fr,en",
    [
        (Channel.EMAIL_RESELLER, "garantie standard Jabra", "Jabra standard warranty"),
        (Channel.EMAIL_MANUFACTURER_SUPPORT, "certificat cert-42", "certificate cert-42"),
        (Channel.EMAIL_LESSOR, "contrat de location", "lease contract"),
    ],
)
@pytest.mark.parametrize("language", ["fr", "en"])
async def test_templates(tmp_path: Path, channel: Channel, fr: str, en: str, language: str) -> None:
    t = Transport()
    a = EmailActionAdapter(
        channel,
        t,
        lambda: Settings(email_allowlist=[TO]),
        "garanties@appelia.example",
        JsonlSentLedger(tmp_path / "ledger"),
    )
    act = action(
        language=language,
        company_name="Entreprise Exemple",
        purchase_country="France",
        contract_reference="LEASE-42",
        invoice_number="INV-42",
        documents=[{"kind": "warranty_certificate", "id": "cert-42", "filename": "cert.pdf"}],
    )
    result = await a.execute(act)
    assert result.status == "success"
    msg = t.messages[0]
    body = str(msg.get_content())
    assert (fr if language == "fr" else en) in body
    assert ("Madame, Monsieur," if language == "fr" else "Dear Sir or Madam,") in body
    assert (
        "Cordialement,\nEntreprise Exemple"
        if language == "fr"
        else "Kind regards,\nEntreprise Exemple"
    ) in body
    assert "cert.pdf" in body and "INV-42" in body
    if channel == Channel.EMAIL_MANUFACTURER_SUPPORT:
        assert "France" in body
    if channel == Channel.EMAIL_LESSOR:
        assert "LEASE-42" in body
    assert f"[WP-{str(act.case_id)[:8]}]" in msg["Subject"]
    proof = json.loads(result.proof or "{}")
    assert parsedate_to_datetime(msg["Date"]) == datetime.fromisoformat(proof["sent_at"])
