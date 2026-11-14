from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import create_schema, make_engine, make_session_factory
from app.core.settings import AppSettings


@pytest.fixture
def app_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        environment="dev",
        database_url="sqlite:///:memory:",
        journal_anchor_key="unit-test-key",
        anchor_file=tmp_path / "anchors" / "anchors.jsonl",
        maildir_path=tmp_path / "mail",
        email_sent_ledger_path=tmp_path / "email_sent.jsonl",
<<<<<<< HEAD
        followup_interval_s=0,
        followup_outbox_path=tmp_path / "followup.sqlite3",
||||||| parent of 35713b1 (test(securite): tests de régression de l'audit SEC1, pytest 9, reset authentifié)
=======
        journal_archive_dir=tmp_path / "journal-archive",
>>>>>>> 35713b1 (test(securite): tests de régression de l'audit SEC1, pytest 9, reset authentifié)
    )


@pytest.fixture
def db_engine() -> Generator[Engine, None, None]:
    engine = make_engine("sqlite:///:memory:")
    create_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(db_engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(db_engine)
