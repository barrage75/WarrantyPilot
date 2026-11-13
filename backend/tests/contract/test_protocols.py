from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.contracts.enums import (
    DocumentKind,
    DocumentSource,
    IncidentKind,
    IncidentReportedVia,
)
from app.contracts.models import (
    Case,
    ChecklistStep,
    DataChecklist,
    Document,
    Equipment,
    Event,
    Incident,
    utc_now,
)
from app.testing.fakes import FakeActionAdapter, FakeExtractor, FakeFollowUp, FakeRulesEngine
from tests.contract.helpers import (
    assert_action_adapter_contract,
    assert_extractor_contract,
    assert_follow_up_contract,
    assert_rules_engine_contract,
)


def make_document() -> Document:
    return Document(
        kind=DocumentKind.INVOICE,
        filename="invoice-demo.xml",
        sha256="0" * 64,
        mime="application/xml",
        source=DocumentSource.FACTURX,
    )


@pytest.mark.parametrize("result_kind", ["success", "failure"])
async def test_action_adapter_contract(result_kind: str) -> None:
    adapter = FakeActionAdapter(result=result_kind)
    await assert_action_adapter_contract(adapter)


def test_extractor_contract_emits_provenance() -> None:
    document = make_document()
    facts = assert_extractor_contract(FakeExtractor(), document, b"demo invoice")
    assert facts


def test_rules_engine_contract_returns_verdict_with_trace() -> None:
    equipment = Equipment(
        brand="Jabra",
        model="Evolve2 65",
        serial="DEMO-001",
        category="headset",
    )
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=uuid4(),
        description="Le casque ne marche plus.",
        reported_via=IncidentReportedVia.CHAT,
    )
    assert_rules_engine_contract(FakeRulesEngine(), equipment, incident)


def test_follow_up_contract_returns_event_payloads() -> None:
    case = Case(incident_id=uuid4())
    assert_follow_up_contract(FakeFollowUp(), case)


def test_document_cannot_be_trusted_and_contracts_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Document(
            kind="invoice",
            filename="invoice.pdf",
            sha256="0" * 64,
            mime="application/pdf",
            source="upload",
            untrusted=False,
        )
    with pytest.raises(ValidationError):
        Document(
            kind="invoice",
            filename="invoice.pdf",
            sha256="0" * 64,
            mime="application/pdf",
            source="upload",
            not_a_contract_field=True,
        )


def test_contract_timestamps_are_utc_and_document_hash_is_sha256() -> None:
    with pytest.raises(ValidationError):
        Document(
            kind="invoice",
            filename="invoice.pdf",
            sha256="not-a-hash",
            mime="application/pdf",
            source="upload",
        )
    with pytest.raises(ValidationError):
        ChecklistStep(done=True, at=utc_now().replace(tzinfo=None))
    with pytest.raises(ValidationError):
        Incident(
            kind=IncidentKind.FAILURE,
            reporter_id=uuid4(),
            description="Panne",
            reported_via=IncidentReportedVia.CHAT,
            created_at=utc_now().replace(tzinfo=None),
        )
    with pytest.raises(ValidationError):
        Event(seq=1, actor="agent", type="not_a_catalogued_event")


def test_data_checklist_requires_all_seven_steps_and_human_signoff() -> None:
    checklist = DataChecklist(case_id=uuid4())
    assert checklist.complete() is False
    human_id = uuid4()
    checklist.steps = {
        name: ChecklistStep(
            done=True,
            by_person_id=human_id,
            at=utc_now(),
        )
        for name in checklist.steps
    }
    assert checklist.complete() is True
