from __future__ import annotations

import asyncio
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.contracts.enums import (
    DocumentKind,
    DocumentSource,
    IncidentKind,
    IncidentReportedVia,
    PurchaseGuardState,
    RealityBadge,
    RightType,
)
from app.contracts.models import Fact, Incident
from app.core.tables import purchase_requests
from app.ingestion.registry import ExtractorRegistry
from app.rules import DeterministicRulesEngine

router = APIRouter(prefix="/scan", tags=["scan"])


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.title() for part in rest)


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class ExpiringRight(APIModel):
    equipment: str
    right: RightType
    ends_at: str


class ScanSummary(APIModel):
    scan_id: str
    status: str
    company: str
    invoices: int
    covered_equipment_eur: float
    possible_savings_eur: float
    realized_savings_eur: float
    expiring: list[ExpiringRight]
    progress: int
    documents_total: int
    documents_done: int
    badge: RealityBadge = RealityBadge.REPRODUCTION
    error: str | None = None


class ScanStartResponse(BaseModel):
    scan_id: str


def _rule_facts(facts: list[Fact]) -> list[Fact]:
    aliases = {
        "supplier_name": "reseller_name",
        "supplier_address": "reseller_address",
        "customer_name": "buyer_name",
        "warranty_duration_months": "warranty_term_months",
    }
    line_aliases = {
        "model": ("model_number", "product_type"),
        "serial": ("serial_number",),
        "warranty_duration_months": ("warranty_term_months",),
    }
    normalized: list[Fact] = []
    for fact in facts:
        line_field = re.fullmatch(r"lines\[\d+\]\.([a-z_]+)", fact.field)
        fields = (
            line_aliases.get(line_field[1], (fact.field,))
            if line_field
            else (aliases.get(fact.field, fact.field),)
        )
        normalized.extend(fact.model_copy(update={"field": field}) for field in fields)
    return normalized


async def _run_scan(application: Any, scan_id: str) -> None:
    state: dict[str, Any] = application.state.scans[scan_id]
    try:
        repository_root = Path(__file__).resolve().parents[4]
        if str(repository_root) not in sys.path:
            sys.path.insert(0, str(repository_root))
        from data.appelia.load import load_dataset

        dataset = load_dataset()
        data_directory = repository_root / "data" / "appelia"
        state["documents_total"] = len(dataset.documents)
        extractor = application.state.services.get("extractor") or ExtractorRegistry()
        extracted_facts = list(dataset.facts)
        for index, document in enumerate(dataset.documents, start=1):
            if document.source == DocumentSource.FACTURX:
                content = (data_directory / document.filename).read_bytes()
                extracted_facts.extend(
                    await asyncio.to_thread(extractor.extract, document, content)
                )
            state["documents_done"] = index
            state["progress"] = round(index * 100 / max(1, len(dataset.documents)))

        engine = application.state.services.get("rules_engine")
        if engine is None:
            engine = DeterministicRulesEngine(application.state.app_settings.demo_today)
        rules = application.state.services.get("rules", [])
        facts_by_equipment: dict[UUID, list[Any]] = {}
        for fact in _rule_facts(extracted_facts):
            if fact.equipment_id is not None:
                facts_by_equipment.setdefault(fact.equipment_id, []).append(fact)
        rights_by_equipment: dict[UUID, list[Any]] = {}
        for right in dataset.rights:
            rights_by_equipment.setdefault(right.equipment_id, []).append(right)

        covered_value = 0.0
        expiring: list[ExpiringRight] = []
        fallback_reporter = dataset.people[0].id
        today = application.state.app_settings.demo_today
        for item in dataset.equipment:
            incident = Incident(
                kind=IncidentKind.FAILURE,
                reporter_id=item.assigned_to or fallback_reporter,
                equipment_id=item.id,
                description="Panne matérielle à vérifier",
                reported_via=IncidentReportedVia.CHAT,
            )
            verdict = engine.evaluate(
                item,
                facts_by_equipment.get(item.id, []),
                incident,
                rules,
                rights_by_equipment.get(item.id, []),
            )
            if verdict.value.value in {"covered", "likely_covered"} and item.purchase_price:
                covered_value += float(item.purchase_price)
            for right in rights_by_equipment.get(item.id, []):
                if today <= right.end_date <= today + timedelta(days=30):
                    expiring.append(
                        ExpiringRight(
                            equipment=f"{item.brand} {item.model}",
                            right=right.right_type.value,
                            ends_at=right.end_date.isoformat(),
                        )
                    )

        possible_savings = 0.0
        realized_savings = 0.0
        with application.state.session_factory() as session:
            requests = session.execute(select(purchase_requests)).mappings().all()
        for purchase in requests:
            amount = float(purchase["amount"])
            if purchase["state"] == PurchaseGuardState.SAVING_REALIZED.value:
                realized_savings += amount
            elif purchase["state"] != PurchaseGuardState.PURCHASE_KEPT.value:
                possible_savings += amount

        state.update(
            {
                "status": "completed",
                "company": "Appelia",
                "invoices": sum(
                    document.kind == DocumentKind.INVOICE for document in dataset.documents
                ),
                "covered_equipment_eur": round(covered_value, 2),
                "possible_savings_eur": round(possible_savings, 2),
                "realized_savings_eur": round(realized_savings, 2),
                "expiring": expiring,
                "badge": RealityBadge.REPRODUCTION,
            }
        )
    except Exception as error:
        state.update({"status": "failed", "error": type(error).__name__})


@router.post("", response_model=ScanStartResponse, status_code=202)
async def start_scan(request: Request) -> ScanStartResponse:
    scan_id = str(uuid4())
    request.app.state.scans[scan_id] = {
        "scan_id": scan_id,
        "status": "running",
        "company": "Appelia",
        "invoices": 0,
        "covered_equipment_eur": 0,
        "possible_savings_eur": 0,
        "realized_savings_eur": 0,
        "expiring": [],
        "progress": 0,
        "documents_total": 0,
        "documents_done": 0,
        "badge": RealityBadge.REPRODUCTION,
        "error": None,
    }
    asyncio.create_task(_run_scan(request.app, scan_id))
    return ScanStartResponse(scan_id=scan_id)


@router.get("/{scan_id}", response_model=ScanSummary)
def get_scan(scan_id: str, request: Request) -> ScanSummary:
    state = request.app.state.scans.get(scan_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanSummary.model_validate(state)
