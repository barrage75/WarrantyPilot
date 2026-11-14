import hashlib
import hmac
import json
import re
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.enums import EventType
from app.contracts.models import Event, utc_now
from app.core.db import SessionLocal
from app.core.settings import AppSettings, get_settings
from app.core.tables import events

ZERO_HASH = "0" * 64
_SECRET_KEY_PARTS = ("key", "token", "secret", "password", "authorization", "cookie")
_PUBLIC_KEYS = frozenset({"idempotency_key"})
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
)
_ANCHOR_TRIGGER_STATUSES = frozenset({"sent", "resolved"})
_APPEND_LOCK = RLock()
_EVENT_KEY: SecretStr | None = None


def configure_journal_key(key: SecretStr) -> None:
    global _EVENT_KEY
    _EVENT_KEY = key


def _event_key() -> bytes:
    key = _EVENT_KEY or get_settings().journal_anchor_key
    return key.get_secret_value().encode("utf-8")


def _event_hash(previous_hash: str, canonical: str) -> str:
    return hmac.new(
        _event_key(), (previous_hash + canonical).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _redact_text(value: str) -> str:
    for pattern in _SECRET_VALUE_PATTERNS:
        value = pattern.sub("***", value)
    return value


def _is_secret_key(key: object) -> bool:
    name = str(key).casefold()
    return name not in _PUBLIC_KEYS and any(part in name for part in _SECRET_KEY_PARTS)


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "***" if _is_secret_key(key) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
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
    with _APPEND_LOCK:
        return _append_event_locked(
            session,
            event_type,
            actor=actor,
            case_id=case_id,
            payload=payload,
            at=at,
        )


def _append_event_locked(
    session: Session,
    event_type: EventType,
    *,
    actor: str,
    case_id: str | None,
    payload: dict[str, Any] | None,
    at: datetime | None,
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
    current_hash = _event_hash(previous_hash, canonical)
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
    with _APPEND_LOCK:
        return _anchor_locked(session, settings or get_settings())


def _anchor_locked(session: Session, active_settings: AppSettings) -> dict[str, Any]:
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
        expected_hash = _event_hash(previous_hash, canonical)
        if row["prev_hash"] != previous_hash or row["hash"] != expected_hash:
            first_bad_seq = seq
            break
        previous_hash = str(row["hash"])

    anchors_ok = True
    anchor_file = active_settings.anchor_file
    anchor_events = [row for row in rows if row["type"] == EventType.JOURNAL_ANCHORED.value]
    if not anchor_file.exists() and anchor_events:
        anchors_ok = False
        if first_bad_seq is None:
            first_bad_seq = int(anchor_events[0]["payload"].get("seq", anchor_events[0]["seq"]))
    elif anchor_file.exists():
        rows_by_seq = {int(row["seq"]): row for row in rows}
        known_hashes = {seq: str(row["hash"]) for seq, row in rows_by_seq.items()}
        known_hashes[0] = ZERO_HASH
        valid_anchor_count = 0
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
                anchor_event = rows_by_seq.get(seq + 1)
                anchor_event_ok = (
                    anchor_event is not None
                    and anchor_event["type"] == EventType.JOURNAL_ANCHORED.value
                    and anchor_event["payload"].get("seq") == seq
                )
                if (
                    known_hashes.get(seq) != event_hash
                    or not anchor_event_ok
                    or not hmac.compare_digest(str(anchor_row["hmac"]), expected_hmac)
                ):
                    anchors_ok = False
                    if first_bad_seq is None:
                        first_bad_seq = seq
                    break
                valid_anchor_count += 1
        except (OSError, ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
            anchors_ok = False
        if anchors_ok and valid_anchor_count < len(anchor_events):
            anchors_ok = False
            if first_bad_seq is None:
                missing = anchor_events[valid_anchor_count]
                first_bad_seq = int(missing["payload"].get("seq", missing["seq"]))

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


def anchor_due(session: Session, settings: AppSettings) -> bool:
    last_anchor_seq = session.execute(
        select(func.max(events.c.seq)).where(events.c.type == EventType.JOURNAL_ANCHORED.value)
    ).scalar()
    pending = (
        session.execute(
            select(events.c.type, events.c.payload)
            .where(events.c.seq > (last_anchor_seq or 0))
            .order_by(events.c.seq)
        )
        .mappings()
        .all()
    )
    if not pending:
        return False
    if len(pending) >= settings.auto_anchor_every:
        return True
    return any(
        row["type"] in {EventType.DEMO_RESET.value, EventType.SETTINGS_CHANGED.value}
        or (
            row["type"] == EventType.STATUS_CHANGED.value
            and str((row["payload"] or {}).get("to")) in _ANCHOR_TRIGGER_STATUSES
        )
        for row in pending
    )


def auto_anchor(session_factory: sessionmaker[Session], settings: AppSettings) -> bool:
    with _APPEND_LOCK, session_factory() as session:
        if not anchor_due(session, settings):
            return False
        _anchor_locked(session, settings)
        session.commit()
        return True
