"""Local extraction of labelled invoice text, without OCR or external services.

Only literal labels and item rows are accepted. Unknown layouts and image-only
PDFs yield no purchase facts; missing warranty terms are never inferred here.
"""

import re
from datetime import datetime
from io import BytesIO

from pypdf import PdfReader

from app.contracts.enums import FactSource
from app.contracts.models import Document, Fact, Provenance
from app.ingestion import fields as f
from app.ingestion.controls.suspicious import detect_suspicious, security_fact

_ARTICLE = re.compile(
    r"Article\s*:\s*(?P<model>[^\n]+?)\s*—\s*SKU\s+(?P<sku>\S+)\s*—\s*"
    r"numéro de série\s+(?P<serial>[^\s—]+)"
    r"(?:\s*—\s*Garantie\s*:\s*(?P<years>\d+)\s+ans?\b[^\n]*)?"
)


class TextInvoiceExtractor:
    def extract(self, document: Document, content: bytes) -> list[Fact]:
        facts = security_fact(document, detect_suspicious(content))
        line_index = 0
        for page_number, page in enumerate(PdfReader(BytesIO(content)).pages, 1):
            text = page.extract_text() or ""
            # This layout places the supplier and its address below FACTURE.
            header = re.search(r"^FACTURE[^\n]*\n([^\n]+)\n([^\n]+)", text, re.M)
            if header is None:
                continue

            def emit(
                field: str, value: object, match: re.Match[str], *, page: int = page_number
            ) -> None:
                facts.append(
                    Fact(
                        document_id=document.id,
                        field=field,
                        value=value,
                        provenance=Provenance(
                            document_id=document.id,
                            page=page,
                            excerpt=match[0],
                            char_span=match.span(),
                        ),
                        confidence=1,
                        source=FactSource.STRUCTURED,
                    )
                )

            emit(f.SUPPLIER_NAME, header[1].strip(), header)
            emit(f.SUPPLIER_ADDRESS, header[2].strip(), header)
            for field, pattern in (
                (f.INVOICE_NUMBER, r"^N°\s*:\s*(\S+)"),
                (f.CUSTOMER_NAME, r"^Client\s*:\s*\n?([^\n]+)"),
                (f.INVOICE_DATE, r"^Date\s*:\s*(\d{2}/\d{2}/\d{4})"),
            ):
                match = re.search(pattern, text, re.M)
                if match is None:
                    continue
                value = match[1].strip()
                if field == f.INVOICE_DATE:
                    try:
                        value = datetime.strptime(value, "%d/%m/%Y").date().isoformat()
                    except ValueError:
                        continue
                emit(field, value, match)
            for match in _ARTICLE.finditer(text):
                for name in (f.MODEL, f.SKU, f.SERIAL):
                    emit(f.line_field(line_index, name), match[name], match)
                if match["years"]:
                    emit(
                        f.line_field(line_index, f.WARRANTY_DURATION_MONTHS),
                        int(match["years"]) * 12,
                        match,
                    )
                line_index += 1
        return facts
