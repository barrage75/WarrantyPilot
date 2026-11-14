import os
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from app.ingestion.controls.suspicious import scan_text

MailKind = Literal["failure", "invoice", "other"]


class IntakeLLM(Protocol):
    def classify(self, *, untrusted_text: str) -> MailKind: ...


@dataclass(frozen=True)
class Classification:
    kind: MailKind
    suspicious: bool = False


def suspicious_text(text: str) -> bool:
    return scan_text(text).suspicious or bool(
        re.search(
            r"\bsystem\s*:|send (?:an? )?email to|envoie[rz]? (?:un |cet )?e.?mail|"
            r"classify this as|marque comme accept|ignore.*instructions|"
            r"execute|exécute|curl\s+https?://",
            text,
            re.I,
        )
    )


class Classifier:
    def __init__(self, llm: IntakeLLM | None = None) -> None:
        self.llm = llm

    def classify(self, text: str, *, has_invoice: bool) -> Classification:
        if suspicious_text(text):
            return Classification("other", suspicious=True)
        if has_invoice:
            return Classification("invoice")
        if re.search(
            r"\bpanne\b|ne (?:s['’]allume|démarre|fonctionne|marche) (?:plus|pas)|"
            r"\b(?:cassé|défectueux|hs|broken|failure)\b|no longer works",
            text,
            re.I,
        ):
            return Classification("failure")
        if self.llm is not None and os.getenv("MISTRAL_API_KEY"):
            try:
                kind = self.llm.classify(untrusted_text=text)
                # A model may suggest a type, never an address, command or action.
                if kind in {"failure", "other"}:
                    return Classification(kind)
            except Exception:
                pass
        return Classification("other")
