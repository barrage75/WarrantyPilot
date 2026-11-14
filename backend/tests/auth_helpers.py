from typing import Literal
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update

from app.core.auth import Operator, open_session
from app.core.tables import people

KARIM_ID = "97225c38-d686-5d99-a6cf-53e18aa92e8d"


def login(
    client: TestClient,
    *,
    role: Literal["admin", "operator"] = "admin",
    person_id: str | None = None,
    name: str | None = None,
) -> Operator:
    app = client.app
    assert isinstance(app, FastAPI)
    operator, token = open_test_session(app, role=role, person_id=person_id, name=name)
    client.headers["Authorization"] = f"Bearer {token}"
    return operator


def open_test_session(
    app: FastAPI,
    *,
    role: Literal["admin", "operator"] = "admin",
    person_id: str | None = None,
    name: str | None = None,
) -> tuple[Operator, str]:
    factory = app.state.session_factory
    settings = app.state.app_settings
    identifier = person_id or str(uuid4())
    with factory.begin() as session:
        exists = session.execute(select(people.c.id).where(people.c.id == identifier)).first()
        if exists is None:
            session.execute(
                insert(people).values(
                    id=identifier,
                    name=name or f"Test {role}",
                    email=None,
                    role="test",
                    access_role=role,
                )
            )
        else:
            session.execute(
                update(people).where(people.c.id == identifier).values(access_role=role)
            )
        operator = Operator(person_id=identifier, name=name or f"Test {role}", role=role)
        token, _ = open_session(session, operator, settings)
    return operator, token
