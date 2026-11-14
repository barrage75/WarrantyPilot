from collections.abc import Callable

from app.contracts.enums import DocumentSource
from app.contracts.interfaces import DocumentExtractor
from app.contracts.models import Document, Fact
from app.ingestion.facturx import FacturXExtractor
from app.ingestion.mistral_client import MistralClient
from app.ingestion.pdf_llm import PdfLlmExtractor


class ExtractorRegistry:
    def __init__(
        self,
        *,
        facturx: DocumentExtractor | None = None,
        pdf_llm_factory: Callable[[], DocumentExtractor] | None = None,
    ) -> None:
        self.facturx = facturx or FacturXExtractor()
        self.pdf_llm_factory = pdf_llm_factory or (lambda: PdfLlmExtractor(MistralClient()))
        self._pdf_llm: DocumentExtractor | None = None

    def extract(self, document: Document, content: bytes) -> list[Fact]:
        if document.source == DocumentSource.FACTURX:
            return self.facturx.extract(document, content)
        if document.source in {DocumentSource.UPLOAD, DocumentSource.GMAIL}:
            if self._pdf_llm is None:
                self._pdf_llm = self.pdf_llm_factory()
            return self._pdf_llm.extract(document, content)
        raise ValueError(f"unsupported document source: {document.source.value}")
