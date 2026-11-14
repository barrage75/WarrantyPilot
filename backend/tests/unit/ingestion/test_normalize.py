from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from data.appelia.load import load_dataset

from app.api.routers.scan import _evaluate_equipment
from app.contracts.enums import (
    CaseStatus,
    Channel,
    FactField,
    FactSource,
    IncidentKind,
    IncidentReportedVia,
    PolicyOutcome,
    RealityBadge,
    VerdictValue,
)
from app.contracts.models import Case, Equipment, Fact, Incident, Provenance, Settings
from app.core.orchestrator import Orchestrator
from app.core.policy import decide
from app.ingestion import fields as invoice_fields
from app.ingestion.normalize import normalize_facts
from app.rules import DEFAULT_RULES_DIR, DEMO_REFERENCE_DATE, DeterministicRulesEngine, load_rules


def _fact(document_id: UUID, field: str, value: object) -> Fact:
    return Fact(
        document_id=document_id,
        field=field,
        value=value,
        provenance=Provenance(document_id=document_id, excerpt=f"{field}: {value}"),
        confidence=1,
        source=FactSource.STRUCTURED,
    )


def _invoice_facts(annotation: dict[str, Any], document_id: UUID) -> list[Fact]:
    facts = [
        _fact(document_id, invoice_fields.SUPPLIER_NAME, annotation["supplier_name"]),
        _fact(document_id, invoice_fields.SUPPLIER_ADDRESS, annotation["supplier_address"]),
        _fact(document_id, invoice_fields.INVOICE_DATE, annotation["invoice_date"]),
        _fact(document_id, invoice_fields.CUSTOMER_NAME, annotation["client_name"]),
    ]
    for index, line in enumerate(annotation["lines"]):
        facts.append(
            _fact(
                document_id,
                invoice_fields.line_field(index, invoice_fields.MODEL),
                line["model"],
            )
        )
        facts.append(
            _fact(document_id, invoice_fields.line_field(index, invoice_fields.SKU), line["sku"])
        )
        facts.extend(
            _fact(document_id, invoice_fields.line_field(index, invoice_fields.SERIAL), serial)
            for serial in line["serials"]
        )
        if line.get("warranty_term_months") is not None:
            facts.append(
                _fact(
                    document_id,
                    invoice_fields.line_field(index, invoice_fields.WARRANTY_DURATION_MONTHS),
                    line["warranty_term_months"],
                )
            )
    return facts


def _evaluate(facts: list[Fact], equipment: Equipment, incident: Incident):
    return DeterministicRulesEngine(DEMO_REFERENCE_DATE).evaluate(
        equipment,
        facts,
        incident,
        load_rules(DEFAULT_RULES_DIR),
        [],
    )


def test_five_line_invoice_only_uses_the_equipment_serial() -> None:
    document_id = uuid4()
    serials = [f"JBR000000000{i}" for i in range(1, 6)]
    annotation: dict[str, object] = {
        "supplier_name": "AudioPro Démonstration",
        "supplier_address": "12 rue des Ateliers, 69007 Lyon, France",
        "invoice_date": "2025-01-01",
        "client_name": "Appelia SAS",
        "lines": [
            {
                "model": "Evolve2 65",
                "sku": "26599-999-899",
                "serials": [serial],
                "warranty_term_months": None,
            }
            for serial in serials
        ],
    }
    equipment = Equipment(
        brand="Jabra",
        model="Evolve2 65",
        serial=serials[0],
        category="headset",
        purchase_date=date(2025, 1, 1),
    )
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=uuid4(),
        equipment_id=equipment.id,
        description="Le casque ne s'allume plus.",
        reported_via=IncidentReportedVia.CHAT,
    )
    facts = _invoice_facts(annotation, document_id)
    normalized = normalize_facts(facts, equipment)

    verdict = _evaluate(normalized, equipment, incident)

    assert verdict.value == VerdictValue.COVERED
    assert [fact.value for fact in normalized if fact.field == FactField.SERIAL_NUMBER.value] == [
        serials[0]
    ]
    other_equipment = equipment.model_copy(update={"serial": "JBR9999999999"})
    assert normalize_facts(facts, other_equipment) == []


def test_line_without_serial_matches_by_model() -> None:
    document_id = uuid4()
    equipment = Equipment(
        brand="Jabra",
        model="Evolve2 65",
        serial="JBR0000000001",
        category="headset",
        purchase_date=date(2025, 1, 1),
    )
    facts = [
        _fact(document_id, invoice_fields.SUPPLIER_NAME, "AudioPro Démonstration"),
        _fact(document_id, invoice_fields.SUPPLIER_ADDRESS, "12 rue des Ateliers, Lyon"),
        _fact(document_id, invoice_fields.INVOICE_DATE, "2025-01-01"),
        _fact(document_id, invoice_fields.CUSTOMER_NAME, "Appelia SAS"),
        _fact(document_id, invoice_fields.line_field(0, invoice_fields.MODEL), "Evolve2 65"),
    ]

    normalized = normalize_facts(facts, equipment)
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=uuid4(),
        equipment_id=equipment.id,
        description="Le casque ne s'allume plus.",
        reported_via=IncidentReportedVia.CHAT,
    )

    assert any(fact.field == FactField.MODEL_NUMBER.value for fact in normalized)
    assert not any(fact.field == FactField.SERIAL_NUMBER.value for fact in normalized)
    assert _evaluate(normalized, equipment, incident).value == VerdictValue.COVERED


def test_demo_paul_scan_and_orchestrator_agree_on_covered_auto_send() -> None:
    dataset = load_dataset()
    demo_case = next(item for item in dataset.demo_cases if item["id"] == "demo-paul-martin")
    equipment = next(
        item for item in dataset.equipment if str(item.id) == demo_case["equipment_id"]
    )
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=equipment.assigned_to or dataset.people[0].id,
        equipment_id=equipment.id,
        description=demo_case["description"],
        reported_via=IncidentReportedVia.CHAT,
    )
    engine = DeterministicRulesEngine(DEMO_REFERENCE_DATE)
    rules = load_rules(DEFAULT_RULES_DIR)
    rights = [right for right in dataset.rights if right.equipment_id == equipment.id]

    orchestrator_verdict = Orchestrator._evaluate_verdict(
        engine, equipment, list(dataset.facts), incident, rules, rights
    )
    scan_verdict = _evaluate_equipment(
        engine, equipment, list(dataset.facts), incident, rules, rights
    )

    assert orchestrator_verdict.value == scan_verdict.value == VerdictValue.COVERED
    assert orchestrator_verdict.channel == scan_verdict.channel == Channel.EMAIL_RESELLER
    case = Case(
        incident_id=incident.id,
        equipment_id=equipment.id,
        status=CaseStatus.PREPARED,
        channel=Channel.EMAIL_RESELLER,
        badge=RealityBadge.REPRODUCTION,
    )
    policy = decide(
        case,
        orchestrator_verdict,
        equipment,
        "warranty_claim_email",
        Settings(auto_send_threshold_eur=Decimal("500")),
    )
    assert policy.outcome == PolicyOutcome.AUTO_SEND
