from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.enums import (
    DocumentKind,
    RealityBadge,
    RightType,
)
from app.contracts.interfaces import RulesEngine
from app.contracts.models import Equipment, Fact, Incident, Right, Rule, Verdict
from app.core import tables
from app.core.warranty import evaluate_equipment, savings_totals
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
    days_left: int


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


def _evaluate_equipment(
    engine: RulesEngine,
    equipment: Equipment,
    facts: list[Fact],
    incident: Incident,
    rules: list[Rule],
    rights: list[Right],
) -> Verdict:
    return evaluate_equipment(
        engine,
        equipment,
        facts,
        incident,
        rules,
        rights,
    )


def _persist_scan_facts(session: Session, extracted: list[Fact]) -> None:
    """Fill missing seed facts, keeping stable IDs and user edits across scans."""
    if not extracted:
        return
    existing: set[str] = set(session.execute(select(tables.facts.c.id)).scalars())
    equipment_ids: set[str] = set(session.execute(select(tables.equipment.c.id)).scalars())
    document_ids: set[str] = set(session.execute(select(tables.documents.c.id)).scalars())
    missing = [
        fact.model_dump(mode="json")
        for fact in extracted
        if str(fact.id) not in existing
        and str(fact.equipment_id) in equipment_ids
        and str(fact.document_id) in document_ids
    ]
    if missing:
        session.execute(tables.facts.insert(), missing)


async def _run_scan(application: Any, scan_id: str) -> None:
    state: dict[str, Any] = application.state.scans[scan_id]
    try:
        repository_root = Path(__file__).resolve().parents[4]
        if str(repository_root) not in sys.path:
            sys.path.insert(0, str(repository_root))
        from data.appelia.load import load_dataset_async

        def document_loaded(done: int, total: int) -> None:
            state.update(
                {
                    "documents_total": total,
                    "documents_done": done,
                    "progress": round(done * 100 / max(1, total)),
                }
            )

        dataset = await load_dataset_async(
            facturx_extractor=application.state.services.get("extractor"),
            on_document=document_loaded,
        )
        state["documents_total"] = len(dataset.documents)

        engine = application.state.services.get("rules_engine")
        if engine is None:
            engine = DeterministicRulesEngine(application.state.app_settings.demo_today)
        rules = application.state.services.get("rules", [])
        rights_by_equipment: dict[UUID, list[Any]] = {}
        for right in dataset.rights:
            rights_by_equipment.setdefault(right.equipment_id, []).append(right)

        expiring: list[ExpiringRight] = []
        today = application.state.app_settings.demo_today
        for item in dataset.equipment:
            for right in rights_by_equipment.get(item.id, []):
                if today <= right.end_date <= today + timedelta(days=30):
                    expiring.append(
                        ExpiringRight(
                            equipment=f"{item.brand} {item.model}",
                            right=right.right_type.value,
                            ends_at=right.end_date.isoformat(),
                            days_left=(right.end_date - today).days,
                        )
                    )

        def load_totals() -> dict[str, float]:
            with application.state.session_factory() as session, session.begin():
                _persist_scan_facts(session, list(dataset.facts))
                return savings_totals(session, engine, rules)

        totals = await asyncio.to_thread(load_totals)

        state.update(
            {
                "status": "completed",
                "company": "Appelia",
                "invoices": sum(
                    document.kind == DocumentKind.INVOICE for document in dataset.documents
                ),
                **totals,
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
    task = asyncio.create_task(_run_scan(request.app, scan_id))
    request.app.state.scan_tasks.add(task)
    task.add_done_callback(request.app.state.scan_tasks.discard)
    return ScanStartResponse(scan_id=scan_id)


@router.get("/{scan_id}", response_model=ScanSummary)
def get_scan(scan_id: str, request: Request) -> ScanSummary:
    state = request.app.state.scans.get(scan_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanSummary.model_validate(state)
