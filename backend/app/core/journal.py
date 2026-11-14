import hashlib
import hmac
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.contracts.enums import EventType
from app.contracts.models import Event, utc_now
from app.core.db import SessionLocal
from app.core.settings import AppSettings, get_settings
from app.core.tables import events

ZERO_HASH = "0" * 64
_SECRET_KEY_PARTS = ("key", "token", "secret", "password")


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "***"
                if any(part in str(key).casefold() for part in _SECRET_KEY_PARTS)
                else redact_secrets(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]
    return value


def _canonical_payload(
    seq: int,
    at: str,
    actor: str,
    event_type: str,
    case_id: str | None,
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        {
            "seq": seq,
            "at": at,
            "actor": actor,
            "type": event_type,
            "case_id": case_id,
            "payload": payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def append_event(
    session: Session,
    event_type: EventType,
    *,
    actor: str = "system",
    case_id: str | None = None,
    payload: dict[str, Any] | None = None,
    at: datetime | None = None,
) -> Event:
    previous = session.execute(
        select(events.c.seq, events.c.hash).order_by(events.c.seq.desc()).limit(1)
    ).first()
    previous_hash = str(previous.hash) if previous is not None else ZERO_HASH
    next_seq = int(previous.seq) + 1 if previous is not None else 1
    timestamp = (at or utc_now()).isoformat()
    safe_payload = redact_secrets(payload or {})
    case_id_string = str(case_id) if case_id is not None else None
    canonical = _canonical_payload(
        next_seq, timestamp, actor, event_type.value, case_id_string, safe_payload
    )
    current_hash = hashlib.sha256((previous_hash + canonical).encode("utf-8")).hexdigest()
    event_id = uuid4()
    session.execute(
        events.insert().values(
            id=str(event_id),
            at=timestamp,
            actor=actor,
            type=event_type.value,
            case_id=case_id_string,
            payload=safe_payload,
            prev_hash=previous_hash,
            hash=current_hash,
        )
    )
    return Event(
        id=event_id,
        seq=next_seq,
        at=datetime.fromisoformat(timestamp),
        actor=actor,
        type=event_type,
        case_id=case_id,
        payload=safe_payload,
        prev_hash=previous_hash,
        hash=current_hash,
    )


def _anchor_hmac(key: str, event_hash: str) -> str:
    return hmac.new(key.encode("utf-8"), event_hash.encode("ascii"), hashlib.sha256).hexdigest()


def anchor(
    session: Session,
    settings: AppSettings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    last = session.execute(
        select(events.c.seq, events.c.hash).order_by(events.c.seq.desc()).limit(1)
    ).first()
    seq = int(last.seq) if last is not None else 0
    event_hash = str(last.hash) if last is not None else ZERO_HASH
    anchor_row = {
        "seq": seq,
        "hash": event_hash,
        "hmac": _anchor_hmac(active_settings.journal_anchor_key.get_secret_value(), event_hash),
        "at": utc_now().isoformat(),
    }
    anchor_file = active_settings.anchor_file
    anchor_file.parent.mkdir(parents=True, exist_ok=True)
    with anchor_file.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(anchor_row, sort_keys=True, separators=(",", ":")) + "\n")
    append_event(
        session,
        EventType.JOURNAL_ANCHORED,
        payload={"seq": seq, "hash": event_hash},
    )
    return anchor_row


def verify(
    session: Session,
    settings: AppSettings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    rows = session.execute(select(events).order_by(events.c.seq)).mappings().all()
    previous_hash = ZERO_HASH
    first_bad_seq: int | None = None
    checked_count = 0
    for row in rows:
        seq = int(row["seq"])
        checked_count += 1
        canonical = _canonical_payload(
            seq,
            str(row["at"]),
            str(row["actor"]),
            str(row["type"]),
            str(row["case_id"]) if row["case_id"] is not None else None,
            row["payload"],
        )
        expected_hash = hashlib.sha256((previous_hash + canonical).encode("utf-8")).hexdigest()
        if row["prev_hash"] != previous_hash or row["hash"] != expected_hash:
            first_bad_seq = seq
            break
        previous_hash = str(row["hash"])

    anchors_ok = True
    anchor_file = active_settings.anchor_file
    if anchor_file.exists():
        known_hashes = {int(row["seq"]): str(row["hash"]) for row in rows}
        known_hashes[0] = ZERO_HASH
        try:
            for line in anchor_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                anchor_row = json.loads(line)
                seq = int(anchor_row["seq"])
                event_hash = str(anchor_row["hash"])
                expected_hmac = _anchor_hmac(
                    active_settings.journal_anchor_key.get_secret_value(), event_hash
                )
                if known_hashes.get(seq) != event_hash or not hmac.compare_digest(
                    str(anchor_row["hmac"]), expected_hmac
                ):
                    anchors_ok = False
                    if first_bad_seq is None:
                        first_bad_seq = seq
                    break
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            anchors_ok = False

    return {
        "ok": first_bad_seq is None and anchors_ok,
        "checked": checked_count,
        "first_bad_seq": first_bad_seq,
        "anchors_ok": anchors_ok,
    }


def verify_with_session_factory(
    settings: AppSettings | None = None,
) -> dict[str, Any]:
    with SessionLocal() as session:
        return verify(session, settings)


def verify_with_engine(engine: Engine, settings: AppSettings | None = None) -> dict[str, Any]:
    from sqlalchemy.orm import Session as OrmSession

    with OrmSession(engine) as session:
        return verify(session, settings)


def anchor_path(settings: AppSettings | None = None) -> Path:
    return (settings or get_settings()).anchor_file
