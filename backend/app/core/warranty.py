from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.enums import IncidentKind, IncidentReportedVia, PurchaseGuardState
from app.contracts.interfaces import RulesEngine
from app.contracts.models import Equipment, Fact, Incident, Right, Rule, Verdict
from app.core import tables
from app.ingestion.normalize import normalize_facts
from app.rules import DeterministicRulesEngine


def evaluate_equipment(
    engine: RulesEngine,
    equipment: Equipment,
    facts: list[Fact],
    incident: Incident,
    rules: list[Rule],
    rights: list[Right],
    *,
    dates: dict[str, date] | None = None,
) -> Verdict:
    scoped = [
        fact.model_copy(update={"equipment_id": equipment.id})
        if fact.equipment_id is None and fact.incident_id == incident.id
        else fact
        for fact in facts
    ]
    normalized = normalize_facts(scoped, equipment)
    if isinstance(engine, DeterministicRulesEngine):
        return engine.evaluate(equipment, normalized, incident, rules, rights, dates=dates)
    return engine.evaluate(equipment, normalized, incident, rules, rights)


def stored_inventory(session: Session) -> tuple[list[Equipment], list[Fact], list[Right]]:
    document_owners: dict[str, list[str]] = {}
    for link in session.execute(select(tables.equipment_documents)):
        document_owners.setdefault(link.document_id, []).append(link.equipment_id)
    scoped_facts = []
    for row in session.execute(select(tables.facts)).mappings():
        fact = Fact.model_validate(dict(row))
        if fact.equipment_id is not None:
            scoped_facts.append(fact)
        else:
            document_id = fact.document_id or fact.provenance.document_id
            for owner in document_owners.get(str(document_id), []):
                scoped_facts.append(
                    Fact.model_validate({**fact.model_dump(), "equipment_id": owner})
                )
    return (
        [
            Equipment.model_validate(dict(row))
            for row in session.execute(select(tables.equipment)).mappings()
        ],
        scoped_facts,
        [
            Right.model_validate(dict(row))
            for row in session.execute(select(tables.rights)).mappings()
        ],
    )


def inventory_verdict(
    engine: RulesEngine, item: Equipment, facts: list[Fact], rules: list[Rule], rights: list[Right]
) -> tuple[Verdict, dict[str, date]]:
    dates: dict[str, date] = {}
    incident = Incident(
        kind=IncidentKind.FAILURE,
        reporter_id=item.assigned_to or item.id,
        equipment_id=item.id,
        description="Panne matérielle à vérifier",
        reported_via=IncidentReportedVia.CHAT,
    )
    verdict = evaluate_equipment(engine, item, facts, incident, rules, rights, dates=dates)
    return verdict, dates


def savings_totals(session: Session, engine: RulesEngine, rules: list[Rule]) -> dict[str, float]:
    equipment, facts, rights = stored_inventory(session)
    covered = sum(
        float(item.purchase_price or 0)
        for item in equipment
        if inventory_verdict(engine, item, facts, rules, rights)[0].value.value
        in {"covered", "likely_covered"}
    )
    possible = realized = 0.0
    for purchase in session.execute(select(tables.purchase_requests)).mappings():
        amount = float(purchase["amount"])
        if purchase["state"] == PurchaseGuardState.SAVING_REALIZED.value:
            realized += amount
        elif purchase["state"] != PurchaseGuardState.PURCHASE_KEPT.value:
            possible += amount
    return {
        "covered_equipment_eur": round(covered, 2),
        "possible_savings_eur": round(possible, 2),
        "realized_savings_eur": round(realized, 2),
    }


def rules_engine(application: Any) -> RulesEngine:
    engine: RulesEngine = application.state.services.get(
        "rules_engine"
    ) or DeterministicRulesEngine(application.state.app_settings.demo_today)
    return engine
