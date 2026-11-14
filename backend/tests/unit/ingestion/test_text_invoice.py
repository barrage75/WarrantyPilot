from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from app.contracts.models import Document
from app.ingestion.text_invoice import TextInvoiceExtractor

DATA = Path(__file__).resolve().parents[4] / "data" / "appelia"


def extract(filename):
    content = (DATA / "invoices" / filename).read_bytes()
    document = Document(
        id=uuid4(),
        kind="invoice",
        filename=filename,
        sha256="0" * 64,
        mime="application/pdf",
        source="upload",
    )
    return TextInvoiceExtractor().extract(document, content)


def test_text_invoice_facts_are_literal_and_page_sourced():
    facts = extract("invoice-002.pdf")
    assert {f.value for f in facts if f.field == "invoice_date"} == {"2025-03-10"}
    assert {f.value for f in facts if f.field == "lines[0].serial"} == {"JBR0000000003"}
    assert not any("warranty_duration" in f.field for f in facts)
    page_text = [
        page.extract_text() or "" for page in PdfReader(DATA / "invoices/invoice-002.pdf").pages
    ]
    for fact in facts:
        proof = fact.provenance
        assert proof.page == 1
        assert proof.excerpt in page_text[proof.page - 1]
        assert proof.char_span is not None
        start, end = proof.char_span
        assert page_text[proof.page - 1][start:end] == proof.excerpt


def test_text_invoice_extracts_only_explicit_dell_warranty_terms():
    from data.appelia.load import load_dataset

    dataset = load_dataset()
    missing_term = next(e for e in dataset.equipment if e.serial == "000255W")
    facts = [f for f in dataset.facts if f.equipment_id == missing_term.id]
    assert any(f.field == "invoice_date" for f in facts)
    assert not any("warranty_duration_months" in f.field for f in facts)
    facts = extract("invoice-043.pdf")
    terms = [f for f in facts if f.field.endswith("warranty_duration_months")]
    assert terms and all(
        f.value == 36 and "Garantie : 3 ans" in f.provenance.excerpt for f in terms
    )
