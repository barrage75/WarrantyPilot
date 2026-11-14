from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_orchestrator, get_session
from app.contracts.enums import (
    CaseStatus,
    Channel,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    RealityBadge,
)
from app.contracts.models import Case, DataChecklist, utc_now
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.preflight import preflight_payload, run_checks
from app.core.reset import reset_demo
from app.core.settings import AppSettings
from app.core.tables import cases, data_checklists, equipment, incidents, people

router = APIRouter()


class FakeCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(default="Le casque ne fonctionne plus.")
    equipment_id: UUID | None = None
    reporter_id: UUID | None = None


@router.post("/demo/reset")
def demo_reset(
    request: Request,
    settings: AppSettings = Depends(get_app_settings),
) -> dict[str, str]:
    reset_demo(request.app.state.engine, settings)
    return {"status": "reset"}


@router.get("/demo/preflight")
def demo_preflight(
    request: Request,
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> dict[str, object]:
    results = run_checks(request.app.state.engine, session, settings)
    return preflight_payload(results)


@router.post("/dev/fake-case", response_model=Case, status_code=201)
async def create_fake_case(
    request_body: FakeCaseRequest,
    request: Request,
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> Case:
    if settings.environment != "dev":
        raise HTTPException(status_code=404, detail="Not found")
    equipment_id = request_body.equipment_id
    equipment_category: str | None = None
    if equipment_id is None:
        equipment_row = session.execute(
            select(equipment.c.id, equipment.c.category).order_by(equipment.c.brand).limit(1)
        ).first()
        if equipment_row is None:
            raise HTTPException(status_code=409, detail="Run /demo/reset first")
        equipment_id = UUID(equipment_row.id)
        equipment_category = equipment_row.category
    else:
        equipment_row = session.execute(
            select(equipment.c.category).where(equipment.c.id == str(equipment_id))
        ).first()
        if equipment_row is None:
            raise HTTPException(status_code=404, detail="Equipment not found")
        equipment_category = equipment_row.category
    reporter_id = request_body.reporter_id
    if reporter_id is None:
        reporter_row = session.execute(select(people.c.id).limit(1)).first()
        if reporter_row is None:
            raise HTTPException(status_code=409, detail="Run /demo/reset first")
        reporter_id = UUID(reporter_row.id)
    incident_id = uuid4()
    case_id = uuid4()
    now = utc_now()
    incident = {
        "id": str(incident_id),
        "kind": IncidentKind.FAILURE.value,
        "reporter_id": str(reporter_id),
        "equipment_id": str(equipment_id),
        "description": request_body.description,
        "reported_via": IncidentReportedVia.CHAT.value,
        "created_at": now.isoformat(),
    }
    session.execute(insert(incidents).values(**incident))
    services = request.app.state.services
    adapter = services["action_adapters"].get(Channel.EMAIL_RESELLER)
    session.execute(
        insert(cases).values(
            id=str(case_id),
            incident_id=str(incident_id),
            equipment_id=str(equipment_id),
            status=CaseStatus.PREPARED.value,
            verdict_id=None,
            policy_id=None,
            channel=Channel.EMAIL_RESELLER.value,
            badge=adapter.badge.value if adapter is not None else RealityBadge.SIMULATED.value,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        )
    )
    if equipment_category and equipment_category.casefold() in {"computer", "laptop", "notebook"}:
        checklist = DataChecklist(case_id=case_id)
        session.execute(
            insert(data_checklists).values(
                id=str(checklist.id),
                case_id=str(case_id),
                steps=checklist.model_dump(mode="json")["steps"],
            )
        )
    append_event(
        session,
        EventType.CASE_CREATED,
        case_id=str(case_id),
        payload={"incident_id": str(incident_id), "equipment_id": str(equipment_id)},
    )
    session.commit()
    return await orchestrator.run(case_id)
