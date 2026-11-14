"""report.suspicious feeds suspicious_signal of app/core/policy.py; heuristics, not proof."""

import re
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any

import pdfplumber

from app.contracts.enums import FactField, FactSource
from app.contracts.models import Document, Fact, Provenance
from app.ingestion.mistral_client import OcrPage

INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?previous\s+instructions|ignore[rz]?\s+les\s+instructions|"
    r"system\s+prompt|you\s+are\s+now|approve\s+this\s+claim|disregard|"
    r"oublie[rz]?\s+les\s+instructions|approuve[rz]?\s+cette\s+demande|"
    r"(?:tu\s+es|vous\s+[êe]tes)\s+maintenant|prompt\s+syst[èe]me",
    re.I,
)


@dataclass(frozen=True)
class Signal:
    kind: str
    page: int | None
    evidence: str


@dataclass(frozen=True)
class SuspicionReport:
    suspicious: bool
    signals: list[Signal]


def scan_text(text: str, page: int | None = None) -> SuspicionReport:
    signals = [Signal("injection", page, match[0]) for match in INJECTION.finditer(text)]
    return SuspicionReport(bool(signals), signals)


def _white(colour: Any) -> bool:
    if isinstance(colour, (int, float)):
        return colour >= 0.95
    if isinstance(colour, (tuple, list)):
        if len(colour) == 4:
            return all(component <= 0.05 for component in colour)
        if len(colour) in {1, 3}:
            return all(component >= 0.95 for component in colour)
    return False


def _words(text: str) -> set[str]:
    return {word for word in re.findall(r"[^\W\d_]+", text.casefold()) if len(word) >= 4}


def _strip_markdown(text: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]*>", "", text)
    return re.sub(r"[`*_~#>|]", " ", text)


def detect_suspicious(
    pdf: bytes,
    ocr_pages: list[OcrPage] | None = None,
    *,
    min_missing_words: int = 3,
    min_missing_ratio: float = 0.2,
) -> SuspicionReport:
    signals: list[Signal] = []
    ocr = {page.index: page.markdown for page in ocr_pages or []}
    for ocr_page in ocr_pages or []:
        signals.extend(scan_text(ocr_page.markdown, ocr_page.index).signals)
    if not pdf.lstrip().startswith(b"%PDF"):
        return SuspicionReport(bool(signals), signals)
    with pdfplumber.open(BytesIO(pdf)) as document:
        for index, page in enumerate(document.pages, 1):
            text = page.extract_text() or ""
            signals.extend(scan_text(text, index).signals)
            hidden: list[str] = []
            for char in page.chars:
                if _white(char.get("non_stroking_color")) or char.get("size", 0) < 2:
                    hidden.append(char["text"])
                elif hidden:
                    signals.append(Signal("hidden_text", index, "".join(hidden)))
                    hidden = []
            if hidden:
                signals.append(Signal("hidden_text", index, "".join(hidden)))
            if ocr_pages is not None:
                words = _words(text)
                missing = sorted(words - _words(_strip_markdown(ocr.get(index, ""))))
                if (
                    words
                    and len(missing) >= min_missing_words
                    and len(missing) / len(words) >= min_missing_ratio
                ):
                    signals.append(Signal("text_absent_from_ocr", index, " ".join(missing)))
    unique = list(dict.fromkeys(signals))
    return SuspicionReport(bool(unique), unique)


def security_fact(document: Document, report: SuspicionReport) -> list[Fact]:
    if not report.suspicious:
        return []
    return [
        Fact(
            document_id=document.id,
            field=FactField.SECURITY_SUSPICIOUS.value,
            value=[asdict(signal) for signal in report.signals],
            source=FactSource.STRUCTURED,
            confidence=1.0,
            provenance=Provenance(
                document_id=document.id,
                excerpt="; ".join(signal.evidence for signal in report.signals),
            ),
        )
    ]
