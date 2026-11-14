from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_session
from app.core.journal import anchor, verify
from app.core.settings import AppSettings

router = APIRouter()


@router.get("/journal/verify")
def verify_journal(
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> dict[str, object]:
    return verify(session, settings)


@router.post("/journal/anchor")
def anchor_journal(
    request: Request,
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> dict[str, object]:
    result = anchor(session, settings)
    session.commit()
    return result
