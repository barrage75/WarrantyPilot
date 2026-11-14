import subprocess
import sys
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.contracts.models import Equipment, Fact, Incident, Provenance, Right
from app.rules import (
    DEFAULT_RULES_DIR,
    DEMO_REFERENCE_DATE,
    DeterministicRulesEngine,
    KeywordIncidentClassifier,
    load_rules,
)
from app.rules.engine import CHECK_NAMES

TODAY = DEMO_REFERENCE_DATE
RULES = load_rules(DEFAULT_RULES_DIR)


def equipment(brand: str = "Jabra", model: str = "Evolve2 65") -> Equipment:
    return Equipment(brand=brand, model=model, serial="ABC", category="headset")


def incident() -> Incident:
    return Incident(kind="failure", reporter_id=uuid4(), description="Panne", reported_via="chat")


def fact(field: str, value: Any, confidence: float = 0.95, page: int | None = 1) -> Fact:
    document_id = uuid4()
    return Fact(
        document_id=document_id,
        field=field,
        value=value,
        confidence=confidence,
        source="structured",
        provenance=Provenance(document_id=document_id, page=page, excerpt=f"{field}: {value}"),
    )


# Identifiant, marque, modèle, faits, verdict, canal, date de référence.
CASES = [
    ("evolve", "Jabra", "Evolve2 65", {}, "covered", "email_reseller", TODAY),
    ("engage55", "Jabra", "Engage 55", {}, "not_covered", "email_reseller", TODAY),
    ("engage55se", "Jabra", "Engage 55 SE", {}, "covered", "email_reseller", TODAY),
    ("engage50", "Jabra", "Engage 50 II", {}, "covered", "email_reseller", TODAY),
    ("biz", "Jabra", "BIZ 2400 II", {}, "covered", "email_reseller", TODAY),
    ("unknown-model", "Jabra", "Inconnu", {}, "to_verify", "manual", TODAY),
    ("unknown-brand", "Inconnue", "Inconnu", {}, "to_verify", "manual", TODAY),
    (
        "refurb-in",
        "Jabra",
        "Evolve2 65",
        {"condition": "refurbished", "purchase_date": "2026-10-01"},
        "covered",
        "email_reseller",
        TODAY,
    ),
    (
        "refurb-out",
        "Jabra",
        "Evolve2 65",
        {"condition": "refurbished"},
        "not_covered",
        "email_reseller",
        TODAY,
    ),
    (
        "plus",
        "Jabra",
        "Evolve2 65",
        {
            "purchase_date": "2024-01-01",
            "warranty_plus_certificate": True,
            "extension_months": "24",
        },
        "covered",
        "email_manufacturer_support",
        TODAY,
    ),
    (
        "no-plus",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": "2024-01-01"},
        "not_covered",
        "email_reseller",
        TODAY,
    ),
    (
        "plus-no-term",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": "2024-01-01", "warranty_plus_certificate": True},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "dell",
        "Dell",
        "Latitude 5440",
        {"warranty_term_months": 36},
        "covered",
        "browser_portal",
        TODAY,
    ),
    ("dell-no-term", "Dell", "Latitude 5440", {}, "to_verify", "browser_portal", TODAY),
    (
        "dell-near",
        "Dell",
        "Latitude 5440",
        {"warranty_term_months": 24, "purchase_date": "2024-12-01"},
        "likely_covered",
        "browser_portal",
        TODAY,
    ),
    (
        "dell-far",
        "Dell",
        "Latitude 5440",
        {"warranty_term_months": "36", "invoice_date": "2025-03-12"},
        "covered",
        "browser_portal",
        TODAY,
    ),
    (
        "prosupport",
        "Dell",
        "Latitude 5440",
        {
            "purchase_date": "2024-01-01",
            "warranty_term_months": 12,
            "extension_months": 36,
            "service_contract": "true",
        },
        "covered",
        "browser_portal",
        TODAY,
    ),
    (
        "lease",
        "HP",
        "LaserJet 500",
        {"lease_contract": "true"},
        "out_of_manufacturer",
        "email_lessor",
        TODAY,
    ),
    (
        "liquid",
        "Jabra",
        "Evolve2 65",
        {"incident_category": "liquid_damage"},
        "not_covered",
        "email_reseller",
        TODAY,
    ),
    (
        "wear",
        "Jabra",
        "Evolve2 65",
        {"incident_category": "consumable_wear"},
        "not_covered",
        "email_reseller",
        TODAY,
    ),
    (
        "wear-early",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": "2026-11-10", "incident_category": "consumable_wear"},
        "likely_covered",
        "email_reseller",
        TODAY,
    ),
    (
        "contact",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": TODAY - timedelta(days=400)},
        "covered",
        "email_reseller",
        TODAY,
    ),
    ("suspect", "Jabra", "Evolve2 65", {"suspicious": True}, "to_verify", "email_reseller", TODAY),
    (
        "ambiguous",
        "Jabra",
        "Evolve2 65",
        {"equipment_ambiguous": "true"},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "serial",
        "Jabra",
        "Evolve2 65",
        {"serial_number": "OTHER"},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "buyer",
        "Jabra",
        "Evolve2 65",
        {"buyer_name": "Autre SA"},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "buyer-ok",
        "Jabra",
        "Evolve2 65",
        {"buyer_name": "APPELIA SAS"},
        "covered",
        "email_reseller",
        TODAY,
    ),
    (
        "brand-conflict",
        "Jabra",
        "Evolve2 65",
        {"brand": "Dell"},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "model-conflict",
        "Jabra",
        "Evolve2 65",
        {"model_number": "Speak 510"},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "normalized",
        "jabra",
        "EVOLVE2 65",
        {"serial_number": "a b c"},
        "covered",
        "email_reseller",
        TODAY,
    ),
    (
        "fr-date",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": "12/03/2025"},
        "covered",
        "email_reseller",
        TODAY,
    ),
    (
        "invoice",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": None, "invoice_date": "2025-03-12"},
        "covered",
        "email_reseller",
        TODAY,
    ),
    (
        "no-proof",
        "Jabra",
        "Evolve2 65",
        {"purchase_date": None},
        "to_verify",
        "email_reseller",
        TODAY,
    ),
    (
        "delivery-inventory",
        "Dell",
        "Latitude",
        {"warranty_term_months": 36, "ship_date": "2025-03-13"},
        "covered",
        "browser_portal",
        TODAY,
    ),
    ("no-lease", "HP", "LaserJet", {}, "to_verify", "manual", TODAY),
]
for offset, expected in ((-1, "covered"), (0, "covered"), (1, "not_covered")):
    CASES.append(
        (
            f"month-edge-{offset}",
            "Jabra",
            "Evolve2 65",
            {"purchase_date": "2024-11-21"},
            expected,
            "email_reseller",
            TODAY + timedelta(days=offset),
        )
    )
    CASES.append(
        (
            f"days-edge-{offset}",
            "Jabra",
            "Evolve2 65",
            {"condition": "refurbished", "purchase_date": TODAY - timedelta(days=179)},
            expected,
            "email_reseller",
            TODAY + timedelta(days=offset),
        )
    )


@pytest.mark.parametrize(
    "case_id,brand,model,values,expected,channel,today", CASES, ids=[c[0] for c in CASES]
)
def test_reference_cases(
    case_id: str,
    brand: str,
    model: str,
    values: dict[str, Any],
    expected: str,
    channel: str,
    today: date,
) -> None:
    data = {"purchase_date": "2025-03-12", **values}
    facts = [fact(k, v) for k, v in data.items() if v is not None]
    item = equipment(brand, model)
    item.purchase_date = date(2025, 1, 1)
    result = DeterministicRulesEngine(today).evaluate(item, facts, incident(), RULES, [])
    assert result.value == expected
    assert result.channel == channel
    if case_id in {"unknown-model", "unknown-brand", "no-lease"}:
        assert result.rule_id is None
        assert result.rule_version is None
        assert result.target_url is None
    assert tuple(c.name for c in result.checks) == CHECK_NAMES
    assert all(c.detail for c in result.checks)
    assert result.value != "covered" or any(
        f.field in {"purchase_date", "invoice_date"} for f in facts
    )
    assert (result.target_url is not None) == (channel == "browser_portal")


def test_explanation_omits_unknown_invoice_page() -> None:
    result = DeterministicRulesEngine(TODAY).evaluate(
        equipment(),
        [fact("purchase_date", "2025-03-12", page=None)],
        incident(),
        RULES,
        [],
    )

    assert result.value == "covered"
    assert "facture p. None" not in result.explanation_fr
    assert "invoice p. None" not in result.explanation_en
    assert "facture" in result.explanation_fr
    assert "invoice" in result.explanation_en


def test_uncertainty_conflicts_determinism_and_rights() -> None:
    engine = DeterministicRulesEngine(TODAY, portal_url="http://localhost/custom")
    item = equipment()
    event = incident()
    proof = fact("purchase_date", "2025-03-12", 0.7)
    uncertain = fact("incident_category", "accidental_damage", 0.6)
    result = engine.evaluate(item, [proof, uncertain], event, RULES, [])
    assert result.value == "likely_covered"
    assert result.possible_exclusions == ["accidental_damage"]
    again = engine.evaluate(item, [proof, uncertain], event, RULES, [])
    exclude = {"id": True, "checks": {"__all__": {"id"}}}
    assert result.model_dump(exclude=exclude) == again.model_dump(exclude=exclude)
    second = fact("purchase_date", "2025-04-01", page=2)
    conflict = engine.evaluate(item, [proof, second], event, RULES, [])
    assert conflict.value == "to_verify"
    assert proof.provenance in conflict.evidence and second.provenance in conflict.evidence
    assert engine.evaluate(item, [proof], event, [], []).value == "to_verify"
    item = equipment("HP", "LaserJet")
    right = Right(
        equipment_id=item.id,
        right_type="lease_contract",
        rule_id="lease-hp-laserjet",
        start_date=TODAY,
        end_date=TODAY,
        evidence=[proof.provenance],
    )
    result = engine.evaluate(item, [], event, RULES, [right])
    assert result.value == "out_of_manufacturer" and proof.provenance in result.evidence
    item = equipment("Dell", "Latitude")
    result = engine.evaluate(item, [proof, fact("warranty_term_months", 36)], event, RULES, [])
    assert result.target_url == "http://localhost/custom"


def test_fact_filtering_and_proof_confidence() -> None:
    item = equipment()
    engine = DeterministicRulesEngine(TODAY)
    proof = fact("purchase_date", "2025-03-12", 0.7)
    assert engine.evaluate(item, [proof], incident(), RULES, []).value == "likely_covered"
    proof.confidence = 0.49
    assert engine.evaluate(item, [proof], incident(), RULES, []).value == "to_verify"
    proof.confidence = 0.95
    proof.equipment_id = uuid4()
    assert engine.evaluate(item, [proof], incident(), RULES, []).value == "to_verify"


def test_extension_right_and_classifier() -> None:
    item = equipment()
    proof = fact("purchase_date", "2024-01-01")
    right = Right(
        equipment_id=item.id,
        right_type="extension",
        rule_id="jabra-warranty-plus",
        start_date=date(2026, 1, 1),
        end_date=date(2027, 1, 1),
        evidence=[proof.provenance],
    )
    engine = DeterministicRulesEngine(TODAY, classifier=KeywordIncidentClassifier())
    event = incident()
    result = engine.evaluate(item, [proof], event, RULES, [right])
    assert result.value == "covered"
    assert result.rule_id == "jabra-warranty-plus"
    assert result.channel == "email_manufacturer_support"
    event.description = "Café renversé"
    result = engine.evaluate(item, [proof], event, RULES, [right])
    assert result.value == "not_covered"


def test_inventory_start_approximation_and_invalid_invoice() -> None:
    item = equipment("Dell", "Latitude")
    item.ship_date = date(2024, 12, 1)
    facts = [fact("purchase_date", "2025-03-12"), fact("warranty_term_months", 24)]
    engine = DeterministicRulesEngine(TODAY)
    result = engine.evaluate(item, facts, incident(), RULES, [])
    assert result.value == "likely_covered"
    assert "inventaire" in next(c.detail for c in result.checks if c.name == "start_date")
    item.ship_date = None
    result = engine.evaluate(
        item, [*facts, fact("invoice_date", "illisible")], incident(), RULES, []
    )
    assert result.value == "covered"


def test_golden_rule_survives_optimization() -> None:
    code = """
from app.contracts.enums import VerdictValue
from app.rules.engine import _guard_coverage
for proof, rule in ((None, None), (object(), None), (None, object())):
    try:
        _guard_coverage(VerdictValue.COVERED, proof, rule)
    except RuntimeError:
        continue
    raise SystemExit("Protection de couverture contournée")
"""
    result = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
