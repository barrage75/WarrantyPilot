from __future__ import annotations

import json
import mailbox
from decimal import Decimal
from email.utils import getaddresses
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.actions.browser.drivers._session import GuardedBrowser
from app.actions.email.local_smtp_server import LocalSmtpServer
from app.api.main import create_app
from app.contracts.enums import CaseStatus, EventType
from app.core.settings import AppSettings
from tests.auth_helpers import SAMY_ID, open_test_session


def _json(response: httpx.Response) -> Any:
    assert response.status_code == 200, response.text
    return response.json()


def _status_reached(events: list[dict[str, Any]], status: str) -> bool:
    return any(
        event["type"] == EventType.STATUS_CHANGED.value and event["payload"].get("to") == status
        for event in events
    )


@pytest.mark.p0
@pytest.mark.parametrize("repetition", range(10))
@pytest.mark.asyncio
async def test_p0_gate(
    repetition: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    app_settings: AppSettings,
    db_engine: Engine,
    session_factory: sessionmaker[Session],
) -> None:
    assert 0 <= repetition < 10
    monkeypatch.setenv("WP_BROWSER_ENGINE", "scripted")
    monkeypatch.setenv("WP_BROWSER_PORTAL_URL", "http://127.0.0.1:8100")
    monkeypatch.setenv("WP_BROWSER_RUNTIME_DIR", str(tmp_path / "browser"))

    browser_requests: list[str] = []
    original_on_route = GuardedBrowser.on_route

    async def record_browser_request(browser: GuardedBrowser, route: Any) -> None:
        browser_requests.append(str(route.request.url))
        await original_on_route(browser, route)

    monkeypatch.setattr(GuardedBrowser, "on_route", record_browser_request)

    maildir_path = tmp_path / "mail"
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8100") as repro:
        reset_repro = await repro.post("/__test__/reset")
        assert reset_repro.status_code == 200, reset_repro.text

        async with LocalSmtpServer(str(maildir_path)) as smtp:
            settings = app_settings.model_copy(
                update={
                    "smtp_port": smtp.port,
                    "maildir_path": maildir_path,
                    "anchor_file": tmp_path / "anchors" / "anchors.jsonl",
                    "email_sent_ledger_path": tmp_path / "email_sent.jsonl",
                }
            )
            application = create_app(
                app_settings=settings,
                app_engine=db_engine,
                session_factory=session_factory,
            )
            async with application.router.lifespan_context(application):
                _, token = open_test_session(application, person_id=SAMY_ID)
                transport = httpx.ASGITransport(app=application)
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                    headers={"Authorization": f"Bearer {token}"},
                ) as client:
                    unauthenticated = await client.post(
                        "/api/followup/tick", headers={"Authorization": ""}
                    )
                    assert unauthenticated.status_code == 401
                    reset = await client.post("/api/demo/reset", json={"confirm": "RESET"})
                    assert reset.status_code == 200, reset.text

                    people = _json(await client.get("/api/people"))
                    paul = next(person for person in people if person["name"] == "Paul Martin")
                    operator = next(
                        person for person in people if person["role"] == "responsable informatique"
                    )
                    equipment = _json(await client.get("/api/equipment"))
                    paul_headset = next(
                        item
                        for item in equipment
                        if item["assigned_to"] == paul["id"]
                        and item["brand"] == "Jabra"
                        and item["model"] == "Evolve2 65"
                    )

                    settings_response = _json(await client.get("/api/settings"))
                    allowlist = {
                        address.casefold() for address in settings_response["email_allowlist"]
                    }
                    assert Decimal(settings_response["auto_send_threshold_eur"]) == Decimal("300")

                    paul_conversation = _json(await client.post("/api/chat/conversations"))
                    paul_reply = _json(
                        await client.post(
                            f"/api/chat/conversations/{paul_conversation['id']}/messages",
                            json={
                                "text": (
                                    f"Mon casque Jabra Evolve2 65 {paul_headset['serial']} "
                                    "ne charge plus."
                                ),
                                "reporter_id": paul["id"],
                            },
                        )
                    )
                    paul_case_id = paul_reply["case_id"]
                    paul_case = _json(await client.get(f"/api/cases/{paul_case_id}"))
                    assert paul_case["verdict"]["value"] == "covered"
                    assert paul_case["policy"]["outcome"] == "auto_send"
                    assert paul_case["status"] != CaseStatus.RESOLVED.value
                    paul_events = _json(await client.get(f"/api/cases/{paul_case_id}/events"))
                    assert _status_reached(paul_events, "sent")
                    paul_actions = _json(await client.get(f"/api/cases/{paul_case_id}/actions"))
                    assert len(paul_actions) == 1
                    email_action = paul_actions[0]["action"]
                    assert email_action["channel"] == "email_reseller"
                    assert email_action["payload"]["to"].casefold() in allowlist
                    email_result = paul_actions[0]["results"][0]
                    assert email_result["status"] == "success"
                    email_proof = json.loads(email_result["proof"])
                    email_tick = await client.post("/api/followup/tick")
                    assert email_tick.status_code == 200, email_tick.text
                    assert (
                        _json(await client.get(f"/api/cases/{paul_case_id}"))["status"]
                        == CaseStatus.TRACKED.value
                    )
                    dell_conversation = _json(await client.post("/api/chat/conversations"))
                    dell_reply = _json(
                        await client.post(
                            f"/api/chat/conversations/{dell_conversation['id']}/messages",
                            json={
                                "text": "Le PC 7XK4L93 de Clément ne démarre plus",
                                "reporter_id": SAMY_ID,
                            },
                        )
                    )
                    dell_case_id = dell_reply["case_id"]
                    assert dell_case_id
                    dell_case = _json(await client.get(f"/api/cases/{dell_case_id}"))
                    assert dell_case["verdict"]["value"] in {"covered", "likely_covered"}
                    assert dell_case["verdict"]["channel"] == "browser_portal"
                    assert dell_case["status"] == "awaiting_validation"
                    checklist = _json(await client.get(f"/api/cases/{dell_case_id}/checklist"))
                    assert checklist["steps"]
                    assert all(not step["done"] for step in checklist["steps"].values())

                    validated = _json(
                        await client.post(
                            f"/api/cases/{dell_case_id}/validate",
                            json={"person_id": operator["id"]},
                        )
                    )
                    assert validated["status"] in {"sent", "tracked"}

                    dell_case_events = _json(await client.get(f"/api/cases/{dell_case_id}/events"))
                    assert _status_reached(dell_case_events, "sent")
                    dell_actions = _json(await client.get(f"/api/cases/{dell_case_id}/actions"))
                    assert len(dell_actions) == 1
                    browser_action = dell_actions[0]["action"]
                    assert browser_action["channel"] == "browser_portal"
                    assert browser_action["payload"]["portal_claim"]["service_tag"] == "7XK4L93"
                    browser_result = dell_actions[0]["results"][0]
                    assert browser_result["status"] == "success"
                    browser_proof = json.loads(browser_result["proof"])
                    case_number = browser_proof["case_number"]
                    assert case_number
                    assert any(
                        event["type"] == EventType.ACTION_SUCCEEDED.value
                        and event["payload"].get("case_number") == case_number
                        for event in dell_case_events
                    )
                    screenshot_events = [
                        event
                        for event in dell_case_events
                        if event["type"] == EventType.ACTION_STEP.value
                        and event["payload"].get("screenshot_url")
                    ]
                    assert screenshot_events
                    for event in screenshot_events:
                        screenshot = await client.get(event["payload"]["screenshot_url"])
                        assert screenshot.status_code == 200, screenshot.text
                        assert screenshot.headers["content-type"].startswith("image/png")
                        assert screenshot.content.startswith(b"\x89PNG\r\n\x1a\n")

                    repro_cases = _json(await repro.get("/__test__/cases"))
                    assert len(repro_cases) == 1
                    assert repro_cases[0]["tag"] == "7XK4L93"
                    assert repro_cases[0]["number"] == case_number
                    for portal_status in ("in_progress", "part_shipped", "closed"):
                        advanced = await repro.post(f"/__test__/advance/{case_number}")
                        assert advanced.status_code == 200, advanced.text
                        assert advanced.json()["status"] == portal_status
                        tick = await client.post("/api/followup/tick")
                        assert tick.status_code == 200, tick.text
                        current_dell = _json(await client.get(f"/api/cases/{dell_case_id}"))
                        if portal_status == "closed":
                            assert current_dell["status"] == CaseStatus.RESOLVED.value
                        else:
                            assert current_dell["status"] == CaseStatus.TRACKED.value
                    dell_case_events = _json(await client.get(f"/api/cases/{dell_case_id}/events"))
                    portal_statuses = {
                        event["payload"]["proof"]["portal_status"]
                        for event in dell_case_events
                        if event["type"] == EventType.FOLLOWUP_RECEIVED.value
                        and isinstance(event["payload"].get("proof"), dict)
                        and event["payload"]["proof"].get("portal_status")
                    }
                    assert {"in_progress", "part_shipped", "closed"} <= portal_statuses
                    assert any(
                        event["type"] == EventType.FOLLOWUP_RECEIVED.value
                        and event["payload"].get("proof", {}).get("portal_status") == "closed"
                        for event in dell_case_events
                    )
                    final_checklist = _json(
                        await client.get(f"/api/cases/{dell_case_id}/checklist")
                    )
                    assert all(not step["done"] for step in final_checklist["steps"].values())

                    recommendations = _json(await client.get("/api/purchase-requests"))
                    assert len(recommendations) == 1
                    purchase = recommendations[0]
                    assert purchase["equipment"] == "Jabra Evolve2 65"
                    assert purchase["amountEur"] == 120
                    assert purchase["state"] == "recommendation"

                    suspended = _json(
                        await client.post(
                            f"/api/purchase-requests/{purchase['id']}/decision",
                            json={"choice": "suspend"},
                        )
                    )
                    purchase_case_id = suspended["caseId"]
                    assert purchase_case_id
                    assert suspended["state"] == "purchase_suspended"
                    assert purchase_case_id == paul_case_id
                    purchase_case = _json(await client.get(f"/api/cases/{purchase_case_id}"))
                    assert purchase_case["status"] == CaseStatus.TRACKED.value

                    cancelled = _json(
                        await client.post(
                            f"/api/purchase-requests/{purchase['id']}/confirm-cancellation",
                            json={"person_id": operator["id"]},
                        )
                    )
                    assert cancelled["state"] == "cancelled"
                    assert cancelled["state"] != "saving_realized"
                    assert (
                        _json(await client.get(f"/api/cases/{purchase_case_id}"))["status"]
                        != "resolved"
                    )

                    resolved = _json(
                        await client.post(
                            f"/api/cases/{purchase_case_id}/resolve",
                            json={
                                "person_id": operator["id"],
                                "note": "Remplacement annulé après résolution du dossier.",
                            },
                        )
                    )
                    assert resolved["status"] == CaseStatus.RESOLVED.value
                    resolution_event = next(
                        event
                        for event in _json(
                            await client.get(f"/api/cases/{purchase_case_id}/events")
                        )
                        if event["type"] == EventType.STATUS_CHANGED.value
                        and event["payload"].get("to") == CaseStatus.RESOLVED.value
                    )
                    assert resolution_event["actor"] == f"human:{operator['id']}"
                    resolved_purchase = _json(await client.get("/api/purchase-requests"))
                    assert resolved_purchase[0]["state"] == "saving_realized"
                    assert (
                        _json(await client.get(f"/api/cases/{purchase_case_id}"))["status"]
                        == "resolved"
                    )

                    journal = _json(await client.get("/api/journal/verify"))
                    assert journal["ok"] is True

                    maildir = mailbox.Maildir(str(maildir_path))
                    messages = [maildir.get_message(key) for key in maildir.iterkeys()]
                    sent_folder = maildir.get_folder("sent")
                    sent_messages = [sent_folder.get_message(key) for key in sent_folder.iterkeys()]
                    assert len(messages) == 1
                    assert len(sent_messages) == 1
                    assert messages[0]["Message-ID"] == email_proof["message_id"]
                    all_messages = messages + sent_messages
                    recipients = [
                        address.casefold()
                        for message in all_messages
                        for _, address in getaddresses([message.get("To", "")])
                        if address
                    ]
                    assert recipients
                    assert all(address in allowlist for address in recipients)

                    network_requests = [
                        url
                        for url in browser_requests
                        if urlsplit(url).scheme in {"http", "https", "ws", "wss", "ftp"}
                    ]
                    assert network_requests
                    assert all(
                        urlsplit(url).scheme == "http" and urlsplit(url).netloc == "127.0.0.1:8100"
                        for url in network_requests
                    )
