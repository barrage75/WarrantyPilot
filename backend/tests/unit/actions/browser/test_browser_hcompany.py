import base64
import json

import pytest

from app.actions.browser.drivers.hcompany import (
    SYSTEM_PROMPT,
    TOOLS,
    build_task,
    observation,
    to_pixels,
    trim_to_last_n_images,
)

from .support import make_action, make_adapter


def test_tools_follow_holo_function_calling_conventions() -> None:
    names = [tool["function"]["name"] for tool in TOOLS]
    assert "answer" in names and "click" in names
    click = next(t for t in TOOLS if t["function"]["name"] == "click")["function"]
    assert set(click["parameters"]["required"]) == {"element", "x", "y"}
    assert "goto" not in names, "the agent must never be able to type a URL"
    assert "{" not in SYSTEM_PROMPT, "no tool-format examples in the system prompt"


def test_observation_wraps_the_screenshot() -> None:
    message = observation(b"png")
    assert message["role"] == "user"
    assert message["content"][0]["text"] == "<observation>\n"
    url = message["content"][1]["image_url"]["url"]
    assert base64.b64decode(url.split(",", 1)[1]) == b"png"
    assert message["content"][2]["text"] == "\n</observation>"


def test_only_last_three_screenshots_are_kept() -> None:
    messages = [{"role": "system", "content": "s"}] + [observation(b"x") for _ in range(5)]
    trim_to_last_n_images(messages)
    kinds = [m["content"][1]["type"] for m in messages[1:]]
    assert kinds == ["text", "text", "image_url", "image_url", "image_url"]
    assert messages[1]["content"][0]["text"] == "<observation>\n"


def test_coordinates_are_scaled_from_thousandths() -> None:
    assert to_pixels({"x": 500, "y": 1000}) == (640.0, 900.0)
    with pytest.raises(ValueError):
        to_pixels({"x": 1001, "y": 0})


def test_task_contains_only_action_data_and_demo_account(tmp_path) -> None:
    adapter = make_adapter(tmp_path)
    action = make_action()
    from app.actions.browser.claim import parse_claim

    claim = parse_claim(action.payload)
    from app.actions.browser.drivers.base import PortalJob, StepReporter

    job = PortalJob(
        action_id=action.id,
        claim=claim,
        portal_url="http://127.0.0.1:8100",
        request_token="t",
        email=adapter.settings.demo_email,
        password="demo-only",
        screenshot_dir=tmp_path,
        allowlist=adapter.allowlist,
        settings=adapter.settings,
        reporter=StepReporter(None, "hcompany"),
    )
    task = build_task(job)
    assert "7XK4L93" in task and "demo.appelia@reproduction.local" in task
    assert claim.problem_description in task
    assert "dell.com" not in task
    json.dumps(TOOLS)
