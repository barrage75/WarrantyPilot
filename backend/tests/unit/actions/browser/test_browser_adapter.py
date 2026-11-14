import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.actions.browser import BrowserSettings, HCompanyDriver, PortalErrorCode
from app.actions.browser.settings import BrowserEngine
from app.actions.browser.store import IdempotencyStore, request_token_for
from app.contracts.enums import ActionResultStatus, RealityBadge

from .support import PNG_MAGIC, FakeDriver, claim_payload, make_action, make_adapter


async def test_success_proof_has_case_number_url_screenshot_and_timestamp(tmp_path) -> None:
    steps: list[tuple[str, str | None]] = []
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted, steps=steps)
    action = make_action()

    result = await adapter.execute(action)

    assert result.status == ActionResultStatus.SUCCESS
    assert result.action_id == action.id
    assert result.badge == RealityBadge.REPRODUCTION
    proof = json.loads(result.proof or "")
    assert proof["case_number"] == "FAKE0001"
    assert proof["url"].startswith("http://127.0.0.1:8100/")
    assert Path(proof["screenshot_path"]).read_bytes().startswith(PNG_MAGIC)
    assert proof["captured_at"]
    assert proof["reality"] == "reproduction"
    assert proof["engine"] == "scripted"
    assert proof["request_token"] == request_token_for(action.case_id)
    assert steps and steps[0][0] == "[scripted] scripted started"


async def test_driver_receives_only_payload_data_and_demo_credentials(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted)
    await adapter.execute(make_action(claim=claim_payload(service_tag="9qf7r12")))

    job = scripted.jobs[0]
    assert job.claim.service_tag == "9QF7R12"
    assert job.email == "demo.appelia@reproduction.local"
    assert job.password == "demo-only"
    assert job.portal_url == "http://127.0.0.1:8100"
    assert "9QF7R12" in job.form_url


async def test_non_demo_credentials_are_refused(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted, demo_email="someone@dell.com")

    result = await adapter.execute(make_action())

    assert result.error == "demo_credentials_required"
    assert scripted.jobs == []


@pytest.mark.parametrize(
    "claim",
    [
        None,
        claim_payload(service_tag="BAD"),
        claim_payload(problem_category="Autre"),
        claim_payload(attachment_path="/tmp/x.exe"),
        claim_payload(unexpected="field"),
    ],
)
async def test_invalid_payload_is_a_clean_failure(tmp_path, claim) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted)
    action = make_action()
    if claim is None:
        action.payload.pop("portal_claim")
    else:
        action.payload["portal_claim"] = claim

    result = await adapter.execute(action)

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == "invalid_payload"
    assert scripted.jobs == []


async def test_same_action_twice_submits_once(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted)
    action = make_action()

    first = await adapter.execute(action)
    second = await adapter.execute(action)

    assert len(scripted.jobs) == 1
    assert json.loads(first.proof or "")["case_number"] == "FAKE0001"
    replay = json.loads(second.proof or "")
    assert replay["case_number"] == "FAKE0001" and replay["replayed"] is True


async def test_new_attempt_for_same_case_replays_existing_portal_case(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted)
    case_id = uuid4()

    stable_key = f"case:{case_id}:browser_portal:7XK4L93"
    await adapter.execute(make_action(case_id=case_id, key=stable_key))
    second = await adapter.execute(make_action(case_id=case_id, key=stable_key))

    assert len(scripted.jobs) == 1
    assert second.status == ActionResultStatus.SUCCESS
    assert json.loads(second.proof or "")["case_number"] == "FAKE0001"


async def test_idempotency_survives_a_new_adapter_instance(tmp_path) -> None:
    action = make_action()
    first_driver = FakeDriver("scripted")
    await make_adapter(tmp_path, scripted=first_driver).execute(action)
    second_driver = FakeDriver("scripted")

    result = await make_adapter(tmp_path, scripted=second_driver).execute(action)

    assert second_driver.jobs == []
    assert json.loads(result.proof or "")["replayed"] is True


async def test_concurrent_executions_of_one_action_submit_once(tmp_path) -> None:
    scripted = FakeDriver("scripted", delay=0.05)
    adapter = make_adapter(tmp_path, scripted=scripted)
    action = make_action()

    results = await asyncio.gather(*(adapter.execute(action) for _ in range(4)))

    assert len(scripted.jobs) == 1
    assert {json.loads(r.proof or "")["case_number"] for r in results} == {"FAKE0001"}


async def test_failed_attempt_is_retried_with_the_same_request_token(tmp_path) -> None:
    failing = FakeDriver("scripted", error=PortalErrorCode.PORTAL_TIMEOUT)
    case_id = uuid4()
    first = await make_adapter(tmp_path, scripted=failing).execute(make_action(case_id=case_id))
    working = FakeDriver("scripted")
    second = await make_adapter(tmp_path, scripted=working).execute(
        make_action(case_id=case_id, key=f"case:{case_id}:browser_portal:7XK4L93")
    )

    assert first.status == ActionResultStatus.FAILURE and first.error == "portal_timeout"
    assert second.status == ActionResultStatus.SUCCESS
    assert failing.jobs[0].request_token == working.jobs[0].request_token


def test_request_token_is_a_stable_uuid_per_case() -> None:
    case_id = uuid4()
    assert request_token_for(case_id) == request_token_for(case_id)
    assert request_token_for(case_id) != request_token_for(uuid4())


def test_store_keeps_pending_then_submitted(tmp_path) -> None:
    store = IdempotencyStore(tmp_path / "s.sqlite3")
    case_id = uuid4()
    assert store.reserve("k1", case_id, "t") is None
    assert store.get("k1").status == "pending"  # type: ignore[union-attr]
    store.complete("k1", '{"case_number": "X"}')
    assert store.reserve("k2", case_id, "t").proof == '{"case_number": "X"}'  # type: ignore[union-attr]
    store.clear()
    assert store.get("k1") is None


@pytest.mark.parametrize(
    "error",
    [
        PortalErrorCode.PORTAL_ERROR,
        PortalErrorCode.PORTAL_TIMEOUT,
        PortalErrorCode.UNKNOWN_SERVICE_TAG,
        PortalErrorCode.WARRANTY_EXPIRED,
        PortalErrorCode.BROWSER_UNAVAILABLE,
    ],
)
async def test_portal_failures_are_failures_never_success(tmp_path, error) -> None:
    adapter = make_adapter(tmp_path, scripted=FakeDriver("scripted", error=error))

    result = await adapter.execute(make_action())

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == error.value
    assert result.proof is None


async def test_global_timeout_is_a_failure(tmp_path) -> None:
    adapter = make_adapter(
        tmp_path, scripted=FakeDriver("scripted", delay=5), action_timeout_seconds=0.05
    )

    result = await adapter.execute(make_action())

    assert result.status == ActionResultStatus.FAILURE
    assert result.error == "portal_timeout"


async def test_scripted_crash_is_a_portal_error(tmp_path) -> None:
    adapter = make_adapter(tmp_path, scripted=FakeDriver("scripted", crash=True))

    result = await adapter.execute(make_action())

    assert result.error == "portal_error"


@pytest.mark.parametrize(
    "hcompany",
    [
        FakeDriver("hcompany", error=PortalErrorCode.AGENT_FAILED),
        FakeDriver("hcompany", error=PortalErrorCode.CASE_NUMBER_MISSING),
        FakeDriver("hcompany", crash=True),
    ],
)
async def test_ai_failure_falls_back_to_scripted_and_is_logged(
    tmp_path, adapter_logs, hcompany
) -> None:
    steps: list[tuple[str, str | None]] = []
    scripted = FakeDriver("scripted")
    adapter = make_adapter(
        tmp_path, scripted=scripted, hcompany=hcompany, steps=steps, browser_engine="hcompany"
    )

    result = await adapter.execute(make_action())

    assert result.status == ActionResultStatus.SUCCESS
    assert json.loads(result.proof or "")["engine"] == "scripted"
    assert len(hcompany.jobs) == 1 and len(scripted.jobs) == 1
    assert hcompany.jobs[0].request_token == scripted.jobs[0].request_token
    assert "falling back to scripted" in adapter_logs.text
    assert any("bascule sur le moteur scripté" in text for text, _ in steps)


async def test_fallback_can_be_disabled(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(
        tmp_path,
        scripted=scripted,
        hcompany=FakeDriver("hcompany", error=PortalErrorCode.AGENT_FAILED),
        browser_engine="hcompany",
        fallback_to_scripted=False,
    )

    result = await adapter.execute(make_action())

    assert result.error == "agent_failed"
    assert scripted.jobs == []


async def test_portal_side_failures_do_not_trigger_fallback(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(
        tmp_path,
        scripted=scripted,
        hcompany=FakeDriver("hcompany", error=PortalErrorCode.PORTAL_ERROR),
        browser_engine="hcompany",
    )

    result = await adapter.execute(make_action())

    assert result.error == "portal_error"
    assert scripted.jobs == []


async def test_hcompany_without_key_falls_back_to_scripted(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted, browser_engine="hcompany")
    adapter.drivers[BrowserEngine.HCOMPANY] = HCompanyDriver()
    adapter.settings.hcompany_api_key = None

    result = await adapter.execute(make_action())

    assert result.status == ActionResultStatus.SUCCESS
    assert len(scripted.jobs) == 1


async def test_browser_use_without_library_or_key_falls_back(tmp_path) -> None:
    scripted = FakeDriver("scripted")
    adapter = make_adapter(tmp_path, scripted=scripted, browser_engine="browser_use")
    adapter.settings.browser_use_api_key = None
    adapter.settings.openai_api_key = None

    result = await adapter.execute(make_action())

    assert result.status == ActionResultStatus.SUCCESS
    assert len(scripted.jobs) == 1


async def test_failing_step_callback_never_breaks_the_action(tmp_path) -> None:
    from app.actions.browser import BrowserPortalAdapter

    def broken(text: str, path: str | None) -> None:
        raise RuntimeError("timeline down")

    adapter = BrowserPortalAdapter(
        BrowserSettings(runtime_dir=tmp_path),
        on_step=broken,
        drivers={BrowserEngine.SCRIPTED: FakeDriver("scripted")},
    )

    assert (await adapter.execute(make_action())).status == ActionResultStatus.SUCCESS


async def test_async_step_callback_is_awaited(tmp_path) -> None:
    from app.actions.browser import BrowserPortalAdapter

    seen: list[str] = []

    async def on_step(text: str, path: str | None) -> None:
        seen.append(text)

    adapter = BrowserPortalAdapter(
        BrowserSettings(runtime_dir=tmp_path),
        on_step=on_step,
        drivers={BrowserEngine.SCRIPTED: FakeDriver("scripted")},
    )
    await adapter.execute(make_action())

    assert seen == ["[scripted] scripted started"]


def test_browser_engine_setting_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("WP_BROWSER_ENGINE", "hcompany")
    monkeypatch.setenv("HCOMPANY_API_KEY", "dummy-test-value")
    monkeypatch.setenv("WP_BROWSER_FALLBACK_TO_SCRIPTED", "false")
    settings = BrowserSettings()
    assert settings.browser_engine == BrowserEngine.HCOMPANY
    assert settings.fallback_to_scripted is False
    assert settings.hcompany_api_key is not None
    assert BrowserSettings(browser_engine="scripted").browser_engine == BrowserEngine.SCRIPTED
