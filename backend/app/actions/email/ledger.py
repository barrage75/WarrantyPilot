import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tables import action_results, actions


class SentLedger(Protocol):
    def get(self, key: str) -> dict[str, Any] | None: ...
    def record(self, key: str, entry: dict[str, Any]) -> None: ...
    def for_case(self, case_id: str) -> list[dict[str, Any]]: ...


class JsonlSentLedger:
    def __init__(self, path: str | Path, read_ledger: SentLedger | None = None) -> None:
        self.path = Path(path)
        self.read_ledger = read_ledger

    def _entries(self) -> dict[str, dict[str, Any]]:
        entries: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                entries[entry["key"]] = entry
        return entries

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._entries().get(key)
        stored = self.read_ledger.get(key) if self.read_ledger else None
        if stored is not None and stored.get("state") == "sent":
            return stored
        return entry if entry is not None else stored

    def record(self, key: str, entry: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({**entry, "key": key}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def for_case(self, case_id: str) -> list[dict[str, Any]]:
        entries = self._entries()
        if self.read_ledger is not None:
            for entry in self.read_ledger.for_case(case_id):
                if entry.get("state") == "sent":
                    entries[entry["key"]] = entry
                else:
                    entries.setdefault(entry["key"], entry)
        return [entry for entry in entries.values() if entry.get("case_id") == case_id]


class ActionResultsLedger:
    """Lecture seule des preuves déjà persistées par le cœur."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def _entries(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(actions.c.idempotency_key, actions.c.case_id, action_results.c.proof)
                .join(action_results, actions.c.id == action_results.c.action_id)
                .where(action_results.c.status == "success")
            ).all()
        entries = []
        for row in rows:
            try:
                proof = json.loads(row.proof)
                if not isinstance(proof, dict) or not proof.get("message_id"):
                    continue
            except (ValueError, TypeError):
                continue
            entries.append(
                dict(proof, key=row.idempotency_key, case_id=row.case_id, state="sent", proof=proof)
            )
        return entries

    def get(self, key: str) -> dict[str, Any] | None:
        return next((e for e in self._entries() if e["key"] == key), None)

    def record(self, key: str, entry: dict[str, Any]) -> None:
        raise PermissionError("Utiliser un journal JSONL pour les écritures")

    def for_case(self, case_id: str) -> list[dict[str, Any]]:
        return [e for e in self._entries() if e["case_id"] == case_id]
