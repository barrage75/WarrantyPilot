"""End-to-end runs of the real adapter against the local Dell reproduction."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.actions.browser import BrowserPortalAdapter, BrowserSettings, HCompanyDriver
from app.actions.browser.settings import BrowserEngine
from app.actions.browser.store import request_token_for
from app.contracts.enums import ActionResultStatus

from .conftest import SLOW_SECONDS, ReproServer, free_port
from .support import PNG_MAGIC, claim_payload, make_action

Steps = list[tuple[str, str | None]]


@pytest.fixture
def repro(dell_repro: ReproServer) -> ReproServer:
    dell_repro.reset()
    return dell_repro


def settings_for(repro: ReproServer, tmp_path: Path, **overrides: Any) -> BrowserSettings:
    values: dict[str, Any] = {
        "portal_url": repro.url,
        "test_mode": True,
        "test_origins": [f"127.0.0.1:{repro.port}", f"localhost:{repro.port}"],
        "runtime_dir": tmp_path / "runtime",
        "navigation_timeout_seconds": 10,
        "action_timeout_seconds": 60,
    }
    values.update(overrides)
    return BrowserSettings(**values)


def adapter_for(
    repro: ReproServer, tmp_path: Path, steps: Steps | None = None, **overrides: Any
) -> BrowserPortalAdapter:
    def on_step(text: str, path: str | None) -> None:
        if steps is not None:
            steps.append((text, path))

    return BrowserPortalAdapter(settings_for(repro, tmp_path, **overrides), on_step=on_step)


async def test_scripted_driver_files_the_request_up_to_the_case_number(repro, tmp_path) -> None:
    steps: Steps = []
    adapter = adapter_for(repro, tmp_path, steps)
    action = make_action(url=repro.url + "/support/home/fr-fr")

    result = await adapter.execute(action)

    assert result.status == ActionResultStatus.SUCCESS, result.error
    proof = json.loads(result.proof or "")
    cases = repro.cases()
    assert [c["number"] for c in cases] == [proof["case_number"]]
    assert cases[0]["tag"] == "7XK4L93"
    confirmation = "/support/incidents-online/fr-fr/servicerequest/confirmation/"
    assert proof["url"] == f"{repro.url}{confirmation}{proof['case_number']}"
    assert Path(proof["screenshot_path"]).read_bytes().startswith(PNG_MAGIC)
    assert proof["request_token"] == request_token_for(action.case_id)
    shots = [path for _, path in steps if path]
    assert len(shots) >= 4 and all(Path(p).exists() for p in shots)
    assert any("Connexion" in text for text, _ in steps)
    assert steps[-1][0].startswith("[scripted] Dossier Dell créé")


async def test_repeated_action_never_creates_a_second_case(repro, tmp_path) -> None:
    action = make_action(url=repro.url)
    first = await adapter_for(repro, tmp_path).execute(action)
    again = await adapter_for(repro, tmp_path).execute(action)
    retry = await adapter_for(repro, tmp_path / "other-runtime").execute(
        make_action(
            url=repro.url,
            case_id=action.case_id,
            key=f"case:{action.case_id}:browser_portal:7XK4L93",
        )
    )

    numbers = {json.loads(r.proof or "")["case_number"] for r in (first, again, retry)}
    assert len(numbers) == 1
    assert len(repro.cases()) == 1


@pytest.mark.parametrize(
    ("mode", "error"), [("500", "portal_error"), ("timeout", "portal_timeout")]
)
async def test_failure_modes_are_clean_failures(repro, tmp_path, mode, error) -> None:
    steps: Steps = []
    adapter = adapter_for(repro, tmp_path, steps)

    result = await adapter.execute(
        make_action(url=repro.url, claim=claim_payload(repro_fail_mode=mode))
    )

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == error
    assert result.proof is None
    assert repro.cases() == []
    assert any("Soumission refusée" in text and path for text, path in steps)


async def test_slow_portal_beyond_timeout_fails_then_retry_reuses_the_case(repro, tmp_path) -> None:
    case_id = uuid4()
    slow = await adapter_for(repro, tmp_path, navigation_timeout_seconds=0.5).execute(
        make_action(url=repro.url, case_id=case_id, claim=claim_payload(repro_fail_mode="slow"))
    )
    assert slow.status == ActionResultStatus.FAILURE
    assert slow.error == "portal_timeout"

    await asyncio.sleep(SLOW_SECONDS + 0.5)
    late_cases = repro.cases()
    retry = await adapter_for(repro, tmp_path).execute(
        make_action(
            url=repro.url,
            case_id=case_id,
            key=f"case:{case_id}:browser_portal:7XK4L93",
        )
    )

    assert retry.status == ActionResultStatus.SUCCESS
    assert len(repro.cases()) == 1
    if late_cases:
        assert json.loads(retry.proof or "")["case_number"] == late_cases[0]["number"]


async def test_slow_portal_within_timeout_succeeds(repro, tmp_path) -> None:
    result = await adapter_for(repro, tmp_path).execute(
        make_action(url=repro.url, claim=claim_payload(repro_fail_mode="slow"))
    )

    assert result.status == ActionResultStatus.SUCCESS
    assert len(repro.cases()) == 1


@pytest.mark.parametrize(
    ("tag", "error"), [("ZZZ0000", "unknown_service_tag"), ("4HB2QM2", "warranty_expired")]
)
async def test_portal_refusals_are_failures(repro, tmp_path, tag, error) -> None:
    result = await adapter_for(repro, tmp_path).execute(
        make_action(url=repro.url, claim=claim_payload(service_tag=tag))
    )

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == error
    assert repro.cases() == []


async def test_portal_validation_error_is_reported(repro, tmp_path) -> None:
    result = await adapter_for(repro, tmp_path).execute(
        make_action(url=repro.url, claim=claim_payload(availability_date="2026-11-14"))
    )

    assert result.error == "portal_validation_error"
    assert repro.cases() == []


async def test_attachment_from_payload_is_uploaded(repro, tmp_path) -> None:
    pdf = tmp_path / "facture-fictive.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% fictitious invoice\n%%EOF\n")
    result = await adapter_for(repro, tmp_path).execute(
        make_action(url=repro.url, claim=claim_payload(attachment_path=str(pdf)))
    )

    assert result.status == ActionResultStatus.SUCCESS, result.error


class _ExternalRedirect(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(302)
        self.send_header("Location", "https://support.example.invalid/servicerequest")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def redirecting_server() -> Iterator[int]:
    port = free_port()
    server = HTTPServer(("127.0.0.1", port), _ExternalRedirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield port
    server.shutdown()


async def test_redirect_outside_allowlist_stops_the_action(
    repro, tmp_path, redirecting_server
) -> None:
    origin = f"http://127.0.0.1:{redirecting_server}"
    adapter = adapter_for(
        repro,
        tmp_path,
        portal_url=origin,
        test_origins=[f"127.0.0.1:{redirecting_server}"],
    )

    result = await adapter.execute(make_action(url=origin))

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == "url_not_allowed"


async def test_ai_agent_without_proof_falls_back_to_scripted(repro, tmp_path, adapter_logs) -> None:
    requests: list[dict[str, Any]] = []

    async def lazy_model(body: dict[str, Any]) -> dict[str, Any]:
        requests.append(json.loads(json.dumps(body)))
        call = {
            "id": "call-1",
            "type": "function",
            "function": {"name": "answer", "arguments": json.dumps({"content": "Done: 123"})},
        }
        return {"choices": [{"message": {"content": None, "tool_calls": [call]}}]}

    steps: Steps = []
    adapter = adapter_for(repro, tmp_path, steps, browser_engine="hcompany")
    adapter.drivers[BrowserEngine.HCOMPANY] = HCompanyDriver(transport=lazy_model)

    result = await adapter.execute(make_action(url=repro.url))

    assert result.status == ActionResultStatus.SUCCESS
    assert json.loads(result.proof or "")["engine"] == "scripted"
    assert len(repro.cases()) == 1
    body = requests[0]
    assert body["tool_choice"] == "required" and body["model"] == "holo4-27b"
    assert body["messages"][-1]["content"][1]["type"] == "image_url"
    assert any("bascule sur le moteur scripté" in text for text, _ in steps)
    assert "falling back to scripted" in adapter_logs.text
