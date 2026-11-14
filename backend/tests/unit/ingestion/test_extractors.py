import os
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from lxml import etree
from pypdf import PdfReader

from app.contracts.enums import FactSource
from app.ingestion import fields as f
from app.ingestion.facturx import FacturXExtractor
from app.ingestion.mistral_client import MistralClient
from app.ingestion.pdf_llm import CLOSE, OPEN, PdfLlmExtractor
from tests.unit.ingestion.fixture_generator import (
    INJECTION,
    FakeClient,
    cii,
    document,
    facturx_pdf,
    invoice_pdf,
)


@pytest.mark.parametrize("pdf", [False, True])
def test_cii_all_fields(pdf: bool) -> None:
    doc = document()
    facts = FacturXExtractor().extract(doc, facturx_pdf() if pdf else cii())
    values = {fact.field: fact.value for fact in facts}
    assert values == {
        f.SUPPLIER_NAME: "Appelia",
        f.SUPPLIER_ADDRESS: "1 rue Fictive Paris",
        f.INVOICE_NUMBER: "APP-001",
        f.INVOICE_DATE: "2026-01-02",
        f.CUSTOMER_NAME: "Client Fictif",
        f.TOTAL_TTC: "1200.00",
        f.WARRANTY_EXTENSION_MENTIONED: True,
        f.WARRANTY_DURATION_MONTHS: 36,
        "lines[0].model": "Fictional Laptop",
        "lines[0].sku": "APP-SKU",
        "lines[0].serial": "FAKE-001",
        "lines[0].quantity": "1",
        "lines[0].unit_price_ht": "1000.00",
    }
    xml_text = " ".join(" ".join(etree.fromstring(cii()).itertext()).split())
    assert all(
        fact.source == FactSource.STRUCTURED
        and fact.confidence == 1
        and fact.provenance.page is None
        and fact.provenance.excerpt.strip() in xml_text
        and " = " not in fact.provenance.excerpt
        and fact.provenance.document_id == doc.id
        for fact in facts
    )
    assert (
        next(
            fact.provenance.excerpt for fact in facts if fact.field == f.WARRANTY_DURATION_MONTHS
        ).strip()
        == "Warranty+ extension de garantie 36 mois"
    )


def test_ubl() -> None:
    xml = b"""<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2">
    <ID>APP-UBL</ID><IssueDate>2026-01-02</IssueDate>
    <AccountingSupplierParty><Party><PartyName><Name>Appelia</Name></PartyName>
    </Party></AccountingSupplierParty><LegalMonetaryTotal><TaxInclusiveAmount>12.00
    </TaxInclusiveAmount></LegalMonetaryTotal><InvoiceLine><Item><Name>Fictional</Name>
    </Item><InvoicedQuantity>2</InvoicedQuantity></InvoiceLine></Invoice>"""
    values = {fact.field: fact.value for fact in FacturXExtractor().extract(document(), xml)}
    assert values == {
        f.INVOICE_NUMBER: "APP-UBL",
        f.INVOICE_DATE: "2026-01-02",
        f.SUPPLIER_NAME: "Appelia",
        f.TOTAL_TTC: "12.00",
        "lines[0].model": "Fictional",
        "lines[0].quantity": "2",
    }


def test_xml_errors_and_empty() -> None:
    extractor = FacturXExtractor()
    assert extractor.extract(document(), invoice_pdf()) == []
    assert extractor.extract(document(), b"<Invoice/>") == []
    assert extractor.extract(document(), b"<Other/>") == []
    for xml in [
        b"invalid",
        b"""<!DOCTYPE Invoice [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
                <Invoice><ID>&xxe;</ID></Invoice>""",
    ]:
        with pytest.raises(ValueError):
            extractor.extract(document(), xml)


def test_generated_hidden_and_duplicate() -> None:
    assert invoice_pdf() == invoice_pdf()
    text = PdfReader(BytesIO(invoice_pdf(hidden=True))).pages[0].extract_text()
    assert INJECTION in text


def test_llm_evidence_and_prompt() -> None:
    client = FakeClient("Appelia\nAPP-001\n1200.00 EUR\nS/N: FAKE-001\n" + INJECTION + OPEN + CLOSE)
    facts = PdfLlmExtractor(client).extract(document(), invoice_pdf(hidden=True))
    assert len(facts) == 5
    assert facts[0].field == "security.suspicious"
    for fact in facts[1:]:
        assert fact.source == FactSource.LLM
        start, end = fact.provenance.char_span or (-1, -1)
        assert client.text[start:end] == fact.provenance.excerpt
    system, block, schema = client.calls[0]
    assert "untrusted" in system and "never follow" in system
    assert INJECTION not in system and block.count(OPEN) == block.count(CLOSE) == 1
    untrusted_text = block.split(OPEN, 1)[1].split(CLOSE, 1)[0]
    assert INJECTION in untrusted_text
    assert OPEN not in untrusted_text
    assert CLOSE not in untrusted_text
    assert untrusted_text.count("[neutralised delimiter]") == 2
    assert schema["additionalProperties"] is False


def test_missing_excerpt_clamp_and_empty() -> None:
    client = FakeClient()
    client.response["supplier_name"].update(excerpt="invented", confidence=4)
    client.response["invoice_number"]["confidence"] = -1
    facts = PdfLlmExtractor(client).extract(document(), b"pdf")
    assert facts[0].confidence == 0.3 and facts[0].provenance.char_span is None
    assert facts[1].confidence == 0
    assert PdfLlmExtractor(client).extract(document(), b"") == []
    client.response = {"lines": []}
    assert PdfLlmExtractor(client).extract(document(), b"pdf") == []


@pytest.mark.parametrize(
    "update", [{"page": 2}, {"confidence": float("nan")}, {"value": 123}, {"excerpt": None}]
)
def test_llm_invalid(update: dict[str, object], caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient()
    client.response["supplier_name"].update(update)
    facts = PdfLlmExtractor(client).extract(document(), b"pdf")
    assert len(facts) == 3
    assert not any(fact.field == "supplier_name" for fact in facts)
    assert "Rejected LLM fact supplier_name" in caplog.text


def test_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(ValueError, match="MISTRAL_API_KEY"):
        MistralClient()


def test_llm_broken_items_and_root(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient()
    client.response["supplier_name"] = "bad"
    client.response["lines"] = [42, {"model": {"value": 42}}]
    assert len(PdfLlmExtractor(client).extract(document(), b"pdf")) == 2
    assert "Rejected LLM line" in caplog.text
    client.response["lines"] = "bad"
    assert len(PdfLlmExtractor(client).extract(document(), b"pdf")) == 2
    client.extract_json = Mock(return_value=[])  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="must be an object"):
        PdfLlmExtractor(client).extract(document(), b"pdf")


def test_mistral_sdk_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MISTRAL_API_KEY", "fictional-test-key")
    sdk = Mock()
    monkeypatch.setattr("app.ingestion.mistral_client.Mistral", lambda **kwargs: sdk)
    sdk.ocr.process.return_value = SimpleNamespace(
        pages=[SimpleNamespace(index=0, markdown="Appelia")]
    )
    sdk.chat.complete.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"lines": []}'))]
    )
    client = MistralClient()
    assert client.ocr(b"pdf")[0].index == 1
    assert sdk.ocr.process.call_args.kwargs["document"]["document_url"].startswith(
        "data:application/pdf;base64,"
    )
    assert client.extract_json("system", "untrusted", {"type": "object"}) == {"lines": []}
    request = sdk.chat.complete.call_args.kwargs
    assert request["response_format"].json_schema.strict is True
    assert request["messages"][0].content == "system"
    assert request["messages"][1].content == "untrusted"
    sdk.chat.complete.return_value.choices[0].message.content = "[]"
    with pytest.raises(ValueError, match="non-object"):
        client.extract_json("system", "untrusted", {})


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("MISTRAL_API_KEY"), reason="MISTRAL_API_KEY absent")
def test_live() -> None:
    facts = PdfLlmExtractor(MistralClient()).extract(document(), invoice_pdf())
    assert any(fact.field == f.SUPPLIER_NAME and fact.value == "Appelia" for fact in facts)
