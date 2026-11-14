from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.contracts.models import Settings
from app.core.settings_store import read_settings, write_settings

router = APIRouter()


@router.get("/settings", response_model=Settings)
def get_settings(session: Session = Depends(get_session)) -> Settings:
    return read_settings(session)


@router.put("/settings", response_model=Settings)
def update_settings(
    settings: Settings,
    session: Session = Depends(get_session),
) -> Settings:
    current = read_settings(session)
    result = write_settings(
        session,
        settings.model_copy(update={"agent_paused": current.agent_paused}),
    )
    session.commit()
    return result
