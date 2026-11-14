from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.api import security


def test_submit_failure_releases_pending_and_logs(monkeypatch, caplog) -> None:
    monkeypatch.setattr(security.logger, "disabled", False)
    pending = Lock()
    executor = MagicMock()
    executor.submit.side_effect = RuntimeError("executor shut down")
    monkeypatch.setattr(security, "_anchor_pending", pending)
    monkeypatch.setattr(security, "_ANCHOR_EXECUTOR", executor)
    engine = SimpleNamespace(url=SimpleNamespace(database="file.db"))
    security.schedule_auto_anchor(engine, None, None)
    assert not pending.locked()
    assert "journal auto-anchor submission failed" in caplog.text
    assert "executor shut down" in caplog.text
    executor.submit.side_effect = None
    security.schedule_auto_anchor(engine, None, None)
    assert pending.locked()
    assert executor.submit.call_count == 2


@pytest.mark.parametrize(
    "error", [None, RuntimeError("unexpected"), OperationalError("sql", {}, Exception("busy"))]
)
def test_worker_releases_pending_and_logs_errors(monkeypatch, caplog, error) -> None:
    monkeypatch.setattr(security.logger, "disabled", False)
    pending = Lock()
    pending.acquire()
    worker = MagicMock(side_effect=error)
    monkeypatch.setattr(security, "_anchor_pending", pending)
    monkeypatch.setattr(security, "auto_anchor", worker)
    security._safe_auto_anchor(None, None)
    assert not pending.locked()
    worker.assert_called_once_with(None, None)
    if isinstance(error, OperationalError):
        assert "journal auto-anchor deferred: database busy" in caplog.text
    elif error is not None:
        assert "journal auto-anchor failed" in caplog.text
        assert "RuntimeError: unexpected" in caplog.text
    else:
        assert not caplog.text


def test_in_memory_and_pending_work_are_not_submitted(monkeypatch) -> None:
    pending = Lock()
    executor = MagicMock()
    monkeypatch.setattr(security, "_anchor_pending", pending)
    monkeypatch.setattr(security, "_ANCHOR_EXECUTOR", executor)
    security.schedule_auto_anchor(
        SimpleNamespace(url=SimpleNamespace(database=":memory:")), None, None
    )
    pending.acquire()
    security.schedule_auto_anchor(
        SimpleNamespace(url=SimpleNamespace(database="file.db")), None, None
    )
    executor.submit.assert_not_called()
