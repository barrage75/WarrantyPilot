import re
from email.utils import parseaddr
from typing import Any, Protocol

from app.actions.email.ledger import SentLedger
from app.actions.email.transports import MailTransport
from app.contracts.models import Case


class ReplyClassifier(Protocol):
    def classify(self, data: dict[str, str]) -> str: ...


class KeywordReplyClassifier:
    def classify(self, data: dict[str, str]) -> str:
        text = data["untrusted_text"].casefold()
        groups = {
            "rejected": (
                "refusé",
                "rejeté",
                "hors garantie",
                "denied",
                "rejected",
                "not covered",
                "not accepted",
                "non accepté",
                "pas accepté",
                "ne peut pas être accepté",
                "cannot be accepted",
            ),
            "info_requested": (
                "merci de fournir",
                "pourriez-vous",
                "please provide",
                "additional information",
            ),
            "accepted": ("accepté", "approuvé", "numéro de retour", "rma", "approved", "accepted"),
        }
        return next(
            (
                outcome
                for outcome, words in groups.items()
                if any(re.search(r"\b" + re.escape(word) + r"\b", text) for word in words)
            ),
            "unknown",
        )


class EmailReplyChecker:
    def __init__(
        self,
        transport: MailTransport,
        ledger: SentLedger,
        classifier: ReplyClassifier | None = None,
        sender: str = "garanties@appelia.example",
    ) -> None:
        self.transport, self.ledger = transport, ledger
        self.classifier = classifier or KeywordReplyClassifier()
        self.sender = parseaddr(sender)[1].casefold()

    def check(self, case: Case) -> list[dict[str, Any]]:
        ids = {e["message_id"] for e in self.ledger.for_case(str(case.id))}
        results = []
        for msg in self.transport.fetch_replies():
            if str(msg.get("Message-ID", "")) in ids or (
                self.sender and parseaddr(str(msg.get("From", "")))[1].casefold() == self.sender
            ):
                continue
            matched = ""
            for header in ("In-Reply-To", "References"):
                if ids.intersection(re.findall(r"<[^<>]+>", str(msg.get(header, "")))):
                    matched = header
                    break
            if not matched and str(msg.get("X-WarrantyPilot-Case", "")) == str(case.id):
                matched = "X-WarrantyPilot-Case"
            if not matched:
                continue
            part = msg.get_body(preferencelist=("plain",))
            content = part.get_content() if part else ""
            text = content if isinstance(content, str) else ""
            subject = str(msg.get("Subject", ""))
            data = subject + "\n" + text
            injection = bool(
                re.search(
                    r"ignore (previous|les instructions)|system:|you are now|send an email to|"
                    r"marque comme accepté|classify this as",
                    data,
                    re.I,
                )
            )
            try:
                outcome = self.classifier.classify({"untrusted_text": data})
            except Exception:
                outcome = "unknown"
            if injection or outcome not in {"accepted", "info_requested", "rejected", "unknown"}:
                outcome = "unknown"
            result = {
                "case_id": str(case.id),
                "message_id": str(msg.get("Message-ID", "")),
                "in_reply_to": str(msg.get("In-Reply-To", "")),
                "from": str(msg.get("From", "")),
                "received_at": str(msg.get("Date", "")),
                "subject": subject,
                "outcome": outcome,
                "matched_by": matched,
                "excerpt": text[:1000],
                "untrusted": True,
                "injection_suspected": injection,
            }
            rma = re.search(r"\bRMA\s*[:#-]?\s*([A-Z0-9][A-Z0-9-]*\d[A-Z0-9-]*)", data, re.I)
            if rma:
                result["rma_number"] = rma.group(1)
            results.append(result)
        return results
