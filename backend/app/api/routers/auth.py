from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_session, require_session, session_token
from app.core.auth import (
    SESSION_COOKIE,
    AccessRole,
    Operator,
    close_session,
    find_loginable,
    open_session,
    password_matches,
)
from app.core.settings import AppSettings
from app.core.tables import people

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    person_id: UUID
    password: str = Field(min_length=1, max_length=256)


class LoginPerson(BaseModel):
    id: UUID
    name: str
    role: AccessRole


class SessionInfo(BaseModel):
    person_id: UUID
    name: str
    role: AccessRole
    expires_at: datetime | None = None


@router.get("/people", response_model=list[LoginPerson])
def login_people(session: Session = Depends(get_session)) -> list[LoginPerson]:
    rows = session.execute(
        select(people.c.id, people.c.name, people.c.access_role)
        .where(people.c.access_role.is_not(None))
        .order_by(people.c.name)
    ).all()
    return [LoginPerson(id=UUID(row.id), name=row.name, role=row.access_role) for row in rows]


@router.post("/login", response_model=SessionInfo)
def login(
    request_body: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
    settings: AppSettings = Depends(get_app_settings),
) -> SessionInfo:
    operator = find_loginable(session, str(request_body.person_id))
    valid_password = password_matches(request_body.password, settings)
    if operator is None or not valid_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, expires = open_session(session, operator, settings)
    session.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="strict",
        secure=settings.environment != "dev",
        path="/api",
    )
    return SessionInfo(
        person_id=UUID(operator.person_id),
        name=operator.name,
        role=operator.role,
        expires_at=expires,
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> Response:
    token = session_token(request)
    if token:
        close_session(session, token)
        session.commit()
    response.status_code = 204
    response.delete_cookie(SESSION_COOKIE, path="/api", httponly=True, samesite="strict")
    return response


@router.get("/me", response_model=SessionInfo)
def me(operator: Operator = Depends(require_session)) -> SessionInfo:
    return SessionInfo(person_id=UUID(operator.person_id), name=operator.name, role=operator.role)
