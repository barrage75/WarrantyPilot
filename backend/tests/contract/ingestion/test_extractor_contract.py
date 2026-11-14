from app.ingestion.facturx import FacturXExtractor
from app.ingestion.pdf_llm import PdfLlmExtractor
from tests.contract.helpers import assert_extractor_contract
from tests.unit.ingestion.fixture_generator import FakeClient, cii, document, invoice_pdf


def test_structured_contract() -> None:
    assert assert_extractor_contract(FacturXExtractor(), document(), cii())


def test_llm_contract() -> None:
    assert assert_extractor_contract(PdfLlmExtractor(FakeClient()), document(), invoice_pdf())
