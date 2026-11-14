from datetime import date
from enum import StrEnum

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.contracts.enums import VerdictValue
from app.core import tables
from app.core.warranty import inventory_verdict, rules_engine, stored_inventory

router = APIRouter(prefix="/equipment", tags=["equipment"])


class Coverage(StrEnum):
    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    LEASED = "leased"
    UNKNOWN = "unknown"


class Assignee(BaseModel):
    id: str
    name: str


class EquipmentWarrantyOverview(BaseModel):
    equipment_id: str
    label: str
    brand: str
    model: str
    serial: str
    category: str
    assigned_to: Assignee | None
    purchase_date: date | None
    warranty_end: date | None
    days_left: int | None
    coverage: Coverage
    verdict: VerdictValue
    open_case_id: str | None
    invoice_document_id: str | None


@router.get("/overview", response_model=list[EquipmentWarrantyOverview])
def overview(
    request: Request, coverage: Coverage | None = None, q: str | None = None
) -> list[EquipmentWarrantyOverview]:
    application = request.app
    with application.state.session_factory() as session:
        equipment, facts, rights = stored_inventory(session)
        people = {row.id: row.name for row in session.execute(select(tables.people))}
        open_cases = {
            row.equipment_id: row.id
            for row in session.execute(
                select(tables.cases)
                .where(tables.cases.c.status.not_in(["resolved", "cancelled"]))
                .order_by(tables.cases.c.created_at, tables.cases.c.id)
            )
        }
        invoices = {
            row.equipment_id: row.document_id
            for row in session.execute(
                select(tables.equipment_documents)
                .join(tables.documents)
                .where(tables.documents.c.kind == "invoice")
                .order_by(tables.equipment_documents.c.document_id)
            )
        }
    engine = rules_engine(application)
    result = []
    for item in equipment:
        assignee_id = str(item.assigned_to) if item.assigned_to else None
        name = people.get(assignee_id, "")
        label = f"{item.brand} {item.model}"
        if q and q.casefold() not in " ".join([label, item.serial, name]).casefold():
            continue
        verdict, dates = inventory_verdict(
            engine,
            item,
            facts.get(item.id, []),
            application.state.services.get("rules", []),
            rights,
        )
        end = dates.get("warranty_end")
        days = (end - application.state.app_settings.demo_today).days if end else None
        state = Coverage.UNKNOWN
        if verdict.channel and verdict.channel.value == "email_lessor":
            state = Coverage.LEASED
        elif days is not None:
            state = (
                Coverage.EXPIRED
                if days < 0
                else Coverage.EXPIRING_SOON
                if days <= 90
                else Coverage.ACTIVE
            )
        if coverage is not None and state != coverage:
            continue
        result.append(
            EquipmentWarrantyOverview(
                equipment_id=str(item.id),
                label=label,
                brand=item.brand,
                model=item.model,
                serial=item.serial,
                category=item.category,
                assigned_to=Assignee(id=assignee_id, name=name) if assignee_id else None,
                purchase_date=dates.get("purchase_date"),
                warranty_end=end,
                days_left=days,
                coverage=state,
                verdict=verdict.value,
                open_case_id=open_cases.get(str(item.id)),
                invoice_document_id=invoices.get(str(item.id)),
            )
        )
    return result
