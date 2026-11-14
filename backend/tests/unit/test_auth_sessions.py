from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select

from app.core.auth import Operator, hash_token, open_session, resolve_session
from app.core.tables import auth_sessions, people


@pytest.fixture
def operator(session_factory):
    operator = Operator(person_id=str(uuid4()), name="Operator", role="operator")
    with session_factory.begin() as session:
        session.execute(
            insert(people).values(
                id=operator.person_id, name=operator.name, role="test", access_role=operator.role
            )
        )
    return operator


@pytest.mark.parametrize("commit", [True, False])
def test_open_session_purges_expired_rows_transactionally(
    session_factory, app_settings, operator, commit
) -> None:
    now = datetime(2026, 1, 15, tzinfo=UTC)
    with session_factory.begin() as session:
        for token, delta in [("expired", -1), ("boundary", 0), ("active", 1)]:
            session.execute(
                insert(auth_sessions).values(
                    token_hash=hash_token(token),
                    person_id=operator.person_id,
                    role=operator.role,
                    created_at=(now - timedelta(hours=1)).isoformat(),
                    expires_at=(now + timedelta(seconds=delta)).isoformat(),
                )
            )
    with session_factory() as session:
        token, _ = open_session(session, operator, app_settings, now=now)
        assert set(session.execute(select(auth_sessions.c.token_hash)).scalars()) == {
            hash_token("active"),
            hash_token(token),
        }
        if commit:
            session.commit()
        else:
            session.rollback()
    with session_factory() as session:
        hashes = set(session.execute(select(auth_sessions.c.token_hash)).scalars())
        assert hashes == (
            {hash_token("active"), hash_token(token)}
            if commit
            else {hash_token("expired"), hash_token("boundary"), hash_token("active")}
        )


def test_open_session_with_no_expired_rows(session_factory, app_settings, operator) -> None:
    now = datetime(2026, 1, 15, tzinfo=UTC)
    with session_factory.begin() as session:
        token, expires = open_session(session, operator, app_settings, now=now)
    with session_factory() as session:
        assert resolve_session(session, token, now=now) == operator
        assert expires == now + timedelta(hours=app_settings.session_ttl_hours)
