from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_session, require_admin
from app.contracts.enums import EventType
from app.contracts.models import Settings
from app.core.auth import Operator
from app.core.journal import append_event
from app.core.settings import AppSettings
from app.core.settings_guard import settings_violations
from app.core.settings_store import read_settings, write_settings

router = APIRouter()


@router.get("/settings", response_model=Settings)
def get_settings(session: Session = Depends(get_session)) -> Settings:
    return read_settings(session)


@router.put("/settings", response_model=Settings)
def update_settings(
    settings: Settings,
    session: Session = Depends(get_session),
    app_settings: AppSettings = Depends(get_app_settings),
    operator: Operator = Depends(require_admin),
) -> Settings:
    current = read_settings(session)
    candidate = settings.model_copy(update={"agent_paused": current.agent_paused})
    violations = settings_violations(candidate, app_settings)
    if violations:
        raise HTTPException(status_code=422, detail=violations)
    result = write_settings(session, candidate)
    append_event(
        session,
        EventType.SETTINGS_CHANGED,
        actor=operator.actor,
        payload={
            "before": current.model_dump(mode="json", exclude={"id"}),
            "after": result.model_dump(mode="json", exclude={"id"}),
        },
    )
    session.commit()
    return result
