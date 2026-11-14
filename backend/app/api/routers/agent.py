from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_session, require_session
from app.contracts.enums import EventType
from app.core.auth import Operator
from app.core.journal import append_event
from app.core.settings_store import read_settings, write_settings

router = APIRouter()


@router.get("/agent/status")
def agent_status(session: Session = Depends(get_session)) -> dict[str, bool]:
    settings = read_settings(session)
    return {"paused": settings.agent_paused}


@router.post("/agent/pause")
def pause_agent(
    session: Session = Depends(get_session),
    operator: Operator = Depends(require_session),
) -> dict[str, bool]:
    settings = read_settings(session).model_copy(update={"agent_paused": True})
    write_settings(session, settings)
    append_event(session, EventType.AGENT_PAUSED, actor=operator.actor)
    session.commit()
    return {"paused": True}


@router.post("/agent/resume")
def resume_agent(
    session: Session = Depends(get_session),
    operator: Operator = Depends(require_session),
) -> dict[str, bool]:
    settings = read_settings(session).model_copy(update={"agent_paused": False})
    write_settings(session, settings)
    append_event(session, EventType.AGENT_RESUMED, actor=operator.actor)
    session.commit()
    return {"paused": False}
