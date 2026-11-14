"""Regression tests for docs/audit/AUDIT_SECURITE.md (lot SEC1): one test per finding."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, select, text

from app.api.main import create_app
from app.contracts.enums import ChecklistStepName, EventType, FactSource, PolicyOutcome
from app.contracts.models import Fact, Provenance
from app.core.journal import anchor, append_event, redact_secrets, verify
from app.core.policy import decide, purchase_proof_is_llm_only
from app.core.settings import (
    AppSettings,
    InsecureConfigurationError,
    assert_secure_configuration,
)
from app.core.settings_store import read_settings
from app.core.tables import events
from tests.auth_helpers import KARIM_ID, login
from tests.integration.helpers import create_case
from tests.unit.test_policy import make_inputs


@pytest.fixture
def client(db_engine, app_settings):
    with TestClient(create_app(app_settings=app_settings, app_engine=db_engine)) as api:
        yield api


def _settings_body(client: TestClient, **changes: object) -> dict[str, object]:
    body = client.get("/api/settings").json()
    body.update(changes)
    return body


# C2 — no authentication on mutating routes.
def test_c2_mutating_route_without_session_is_401(client) -> None:
    assert client.post("/api/agent/pause").status_code == 401
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_c2_login_sets_httponly_strict_cookie_and_me(client, session_factory) -> None:
    operator = login(client, role="operator")
    client.headers.pop("Authorization")
    wrong = client.post(
        "/api/auth/login", json={"person_id": operator.person_id, "password": "nope"}
    )
    assert wrong.status_code == 401
    response = client.post(
        "/api/auth/login",
        json={"person_id": operator.person_id, "password": "appelia-demo"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "token" not in response.json()
    me = client.get("/api/auth/me")
    assert me.json()["person_id"] == operator.person_id
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_c2_people_route_is_public_and_minimal(client) -> None:
    login(client, role="admin", name="Admin Example")
    client.headers.pop("Authorization")
    people = client.get("/api/auth/people")
    assert people.status_code == 200
    assert set(people.json()[0]) == {"id", "name", "role"}


def test_c2_spoofed_person_id_is_403(client, session_factory) -> None:
    case, other_person = create_case(session_factory)
    login(client, role="operator")
    response = client.post(
        f"/api/cases/{case.id}/manual-takeover", json={"person_id": str(other_person)}
    )
    assert response.status_code == 403


# C1 — settings editable by anyone, no journal, no caps.
def test_c1_operator_cannot_change_settings(client) -> None:
    login(client, role="operator")
    body = _settings_body(client, auto_send_threshold_eur="900")
    assert client.put("/api/settings", json=body).status_code == 403


def test_c1_admin_settings_are_capped_journaled_and_restricted(client, session_factory) -> None:
    admin = login(client, role="admin")
    too_high = _settings_body(client, auto_send_threshold_eur="1000000")
    assert client.put("/api/settings", json=too_high).status_code == 422
    foreign_mail = _settings_body(client, email_allowlist=["attacker.com"])
    assert client.put("/api/settings", json=foreign_mail).status_code == 422
    foreign_origin = _settings_body(client, browser_allowed_origins=["https://evil.example"])
    assert client.put("/api/settings", json=foreign_origin).status_code == 422
    accepted = client.put(
        "/api/settings", json=_settings_body(client, auto_send_threshold_eur="250")
    )
    assert accepted.status_code == 200, accepted.text
    with session_factory() as session:
        assert read_settings(session).auto_send_threshold_eur == Decimal("250")
        event = (
            session.execute(select(events).where(events.c.type == EventType.SETTINGS_CHANGED.value))
            .mappings()
            .one()
        )
    assert event["actor"] == admin.actor
    assert event["payload"]["before"]["auto_send_threshold_eur"] != "250"
    assert event["payload"]["after"]["auto_send_threshold_eur"] == "250"


# H1 — destructive reset without confirmation.
def test_h1_reset_requires_admin_and_confirmation(client, app_settings) -> None:
    login(client, role="operator")
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 403
    login(client, person_id=KARIM_ID)
    assert client.post("/api/demo/reset").status_code == 400
    assert client.post("/api/demo/reset", json={"confirm": "yes"}).status_code == 400
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
    assert list(app_settings.journal_archive_dir.iterdir())
    assert client.get("/api/auth/me").status_code == 200


def test_h1_reset_is_hidden_outside_dev(db_engine, app_settings) -> None:
    prod = app_settings.model_copy(
        update={
            "environment": "prod",
            "demo_password": SecretStr("prod-demo-secret"),
            "journal_anchor_key": SecretStr("prod-journal-secret"),
        }
    )
    application = create_app(app_settings=prod, app_engine=db_engine)
    api = TestClient(application)
    login(api, role="admin")
    assert api.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 404


# H2 — DNS rebinding / CSRF from a foreign origin.
def test_h2_foreign_host_is_400(db_engine, app_settings) -> None:
    application = create_app(app_settings=app_settings, app_engine=db_engine)
    with TestClient(application, base_url="http://evil.example") as api:
        assert api.get("/api/health").status_code == 400


def test_h2_foreign_origin_is_403(client) -> None:
    login(client, role="admin")
    response = client.post("/api/agent/pause", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    referer = client.post("/api/agent/pause", headers={"Referer": "https://evil.example/x"})
    assert referer.status_code == 403
    allowed = client.post("/api/agent/pause", headers={"Origin": "http://127.0.0.1:5173"})
    assert allowed.status_code == 200


# H3 — purchase decision attributed to a free-form person.
def test_h3_purchase_decision_actor_comes_from_session(client, session_factory) -> None:
    login(client, person_id=KARIM_ID)
    assert client.post("/api/demo/reset", json={"confirm": "RESET"}).status_code == 200
    operator = login(client, role="operator")
    purchase = client.get("/api/purchase-requests").json()[0]
    decision = client.post(
        f"/api/purchase-requests/{purchase['id']}/decision",
        json={"choice": "suspend", "person_id": str(uuid4())},
    )
    assert decision.status_code in {403, 422}
    decision = client.post(
        f"/api/purchase-requests/{purchase['id']}/decision", json={"choice": "suspend"}
    )
    assert decision.status_code == 200, decision.text
    with session_factory() as session:
        actors = session.execute(
            select(events.c.actor).where(events.c.type.like("purchase_guard%"))
        ).scalars()
        assert operator.actor in set(actors)


# H4 — journal hash chain without secret, truncation undetected.
def test_h4_modified_event_is_detected(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        for index in range(3):
            append_event(session, EventType.CASE_CREATED, payload={"n": index})
    with session_factory.begin() as session:
        session.execute(text("DROP TRIGGER IF EXISTS events_no_update"))
        session.execute(text("UPDATE events SET payload = '{\"n\": 9}' WHERE seq = 2"))
    with session_factory() as session:
        result = verify(session, app_settings)
    assert result["ok"] is False
    assert result["first_bad_seq"] == 2


def test_h4_recomputed_chain_without_key_is_detected(session_factory, app_settings) -> None:
    import hashlib

    with session_factory.begin() as session:
        append_event(session, EventType.CASE_CREATED, payload={"n": 1})
        event = session.execute(select(events)).mappings().one()
    forged = hashlib.sha256(f"{event['prev_hash']}forged".encode()).hexdigest()
    with session_factory.begin() as session:
        session.execute(text("DROP TRIGGER IF EXISTS events_no_update"))
        session.execute(text("UPDATE events SET hash = :hash"), {"hash": forged})
    with session_factory() as session:
        assert verify(session, app_settings)["ok"] is False


def test_h4_truncation_after_anchor_is_detected(session_factory, app_settings) -> None:
    with session_factory.begin() as session:
        append_event(session, EventType.CASE_CREATED, payload={"n": 1})
        anchor(session, app_settings)
    with session_factory.begin() as session:
        session.execute(text("DROP TRIGGER IF EXISTS events_no_delete"))
        session.execute(delete(events).where(events.c.type == EventType.JOURNAL_ANCHORED.value))
    with session_factory() as session:
        assert verify(session, app_settings)["ok"] is False


def test_h4_default_key_refused_outside_dev() -> None:
    base = AppSettings(_env_file=None)
    insecure_key = base.model_copy(
        update={"environment": "prod", "demo_password": SecretStr("demo-secret")}
    )
    with pytest.raises(InsecureConfigurationError):
        assert_secure_configuration(insecure_key)
    no_password = base.model_copy(
        update={"environment": "prod", "journal_anchor_key": SecretStr("a-real-secret")}
    )
    with pytest.raises(InsecureConfigurationError):
        assert_secure_configuration(no_password)
    assert_secure_configuration(
        no_password.model_copy(update={"demo_password": SecretStr("demo-secret")})
    )


# M1 — manual proof was free text.
def test_m1_manual_proof_is_structured(client, session_factory) -> None:
    from sqlalchemy import update

    from app.contracts.enums import CaseStatus
    from app.core.tables import cases

    case, _ = create_case(session_factory)
    with session_factory.begin() as session:
        session.execute(
            update(cases)
            .where(cases.c.id == str(case.id))
            .values(status=CaseStatus.MANUAL_TAKEOVER.value)
        )
    login(client, role="operator")
    free_text = client.post(f"/api/cases/{case.id}/manual-proof", json={"proof": "ok"})
    assert free_text.status_code == 422
    bad_reference = client.post(
        f"/api/cases/{case.id}/manual-proof",
        json={"proof_type": "case_number", "reference": "<script>", "proof_date": "2026-11-14"},
    )
    assert bad_reference.status_code == 422
    too_long = client.post(
        f"/api/cases/{case.id}/manual-proof",
        json={
            "proof_type": "case_number",
            "reference": "CASE-1234",
            "proof_date": "2026-11-14",
            "note": "x" * 501,
        },
    )
    assert too_long.status_code == 422


# M2 — browser origins defaulted to any localhost port.
def test_m2_default_browser_origins_are_the_repro_portal_only() -> None:
    from app.contracts.models import Settings

    assert Settings().browser_allowed_origins == [
        "http://127.0.0.1:8100",
        "http://localhost:8100",
    ]


# M3 — purchase proof extracted only by the LLM could auto-send.
def test_m3_llm_only_purchase_proof_never_auto_sends() -> None:
    case, verdict, equipment, settings = make_inputs()
    facts = [
        Fact(
            field="purchase_date",
            value="2026-01-02",
            provenance=Provenance(excerpt="acheté le 2 janvier"),
            confidence=0.9,
            source=FactSource.LLM,
        )
    ]
    assert purchase_proof_is_llm_only(facts)
    result = decide(
        case,
        verdict,
        equipment,
        "warranty_claim_email",
        settings,
        equipment_unambiguous=True,
        purchase_proof_llm_only=purchase_proof_is_llm_only(facts),
    )
    assert result.outcome == PolicyOutcome.NEEDS_VALIDATION
    assert "purchase_proof_llm_only" in result.reasons


# M4 — redaction only by key name.
def test_m4_secret_values_are_redacted_but_idempotency_key_kept() -> None:
    redacted = redact_secrets(
        {
            "note": "token ghp_" + "a" * 36 + " and sk-" + "b" * 24,
            "header": "Bearer abc.def-ghi",
            "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
            "idempotency_key": "case:1:email:SN-1",
        }
    )
    serialized = str(redacted)
    assert "ghp_aaaa" not in serialized
    assert "sk-bbbb" not in serialized
    assert "abc.def-ghi" not in serialized
    assert "eyJhbGciOiJIUzI1NiJ9" not in serialized
    assert redacted["idempotency_key"] == "case:1:email:SN-1"


# M5 — checklist steps could be completed in any order by anyone.
def test_m5_checklist_order_and_roles(client, session_factory) -> None:
    case, _ = create_case(session_factory)
    login(client, role="operator")
    skipped = client.post(f"/api/cases/{case.id}/checklist/backup_verified", json={})
    assert skipped.status_code == 409
    assert client.post(f"/api/cases/{case.id}/checklist/repair_type", json={}).status_code == 200
    assert (
        client.post(f"/api/cases/{case.id}/checklist/backup_verified", json={}).status_code == 200
    )
    admin_only = client.post(f"/api/cases/{case.id}/checklist/disk_encryption", json={})
    assert admin_only.status_code == 403
    login(client, role="admin")
    early_label = client.post(
        f"/api/cases/{case.id}/checklist/{ChecklistStepName.SHIPPING_LABEL.value}", json={}
    )
    assert early_label.status_code == 409


# B4 — vulnerable pytest version.
def test_b4_pytest_is_patched() -> None:
    from importlib.metadata import version

    major, minor, patch = (int(part) for part in version("pytest").split(".")[:3])
    assert (major, minor, patch) >= (9, 0, 3)
