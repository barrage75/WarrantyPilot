"""Local idempotency ledger: one portal case per WarrantyPilot case, at most.

Two layers guarantee that a repeated action never opens a second Dell case:

* this ledger replays the stored proof once a submission succeeded;
* the ``requestToken`` sent to the portal is derived from the case id, so a
  retry after an unknown outcome (timeout, crash) is deduplicated by the portal.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

TOKEN_NAMESPACE = uuid5(NAMESPACE_URL, "https://warrantypilot.local/actions/browser_portal")


def request_token_for(case_id: UUID) -> str:
    return str(uuid5(TOKEN_NAMESPACE, str(case_id)))


@dataclass(frozen=True)
class StoredSubmission:
    idempotency_key: str
    case_id: str
    request_token: str
    status: str
    proof: str | None


class IdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS submissions ("
                " idempotency_key TEXT PRIMARY KEY, case_id TEXT NOT NULL,"
                " request_token TEXT NOT NULL, status TEXT NOT NULL,"
                " proof TEXT, updated_at TEXT NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS ix_case ON submissions(case_id)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row(row: sqlite3.Row | None) -> StoredSubmission | None:
        if row is None:
            return None
        return StoredSubmission(
            idempotency_key=row["idempotency_key"],
            case_id=row["case_id"],
            request_token=row["request_token"],
            status=row["status"],
            proof=row["proof"],
        )

    def reserve(self, key: str, case_id: UUID, token: str) -> StoredSubmission | None:
        """Return a prior successful submission to replay, or record a pending one."""
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                done = conn.execute(
                    "SELECT * FROM submissions WHERE status='submitted'"
                    " AND (idempotency_key=? OR case_id=?) ORDER BY updated_at LIMIT 1",
                    (key, str(case_id)),
                ).fetchone()
                if done is None:
                    conn.execute(
                        "INSERT INTO submissions VALUES (?, ?, ?, 'pending', NULL, ?)"
                        " ON CONFLICT(idempotency_key)"
                        " DO UPDATE SET updated_at=excluded.updated_at",
                        (key, str(case_id), token, now),
                    )
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
        return self._row(done)

    def complete(self, key: str, proof: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE submissions SET status='submitted', proof=?, updated_at=?"
                " WHERE idempotency_key=?",
                (proof, datetime.now(UTC).isoformat(), key),
            )

    def get(self, key: str) -> StoredSubmission | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM submissions WHERE idempotency_key=?", (key,)
            ).fetchone()
        return self._row(row)

    def clear(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM submissions")
