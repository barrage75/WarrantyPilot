"""H Company driver: a Holo computer-use loop over the Models API.

Follows https://hub.hcompany.ai/models-api/build-an-agent/function-calling and
core-concepts (read 2026-11-14): OpenAI-compatible ``/chat/completions``,
``tool_choice="required"``, thinking enabled with ``temperature=0.8``, an
``answer`` tool that ends the loop, screenshots sent as ``<observation>``
user messages (last 3 kept) and integer coordinates in ``[0, 1000]``.

The managed Agents API (``hai-agents``, successor of the deprecated Surfer-H
CLI) drives a cloud browser that cannot reach ``127.0.0.1``; the Models API
lets our guarded local Chromium execute every action instead. The agent never
types URLs: it only clicks/types inside pages, and the allowlist guard stops
any navigation outside the reproduction.
"""

from __future__ import annotations

import asyncio
import base64
import json
import urllib.error
import urllib.request
from collections.abc import Awaitable, Callable
from typing import Any

from app.actions.browser.drivers._session import (
    VIEWPORT_HEIGHT,
    VIEWPORT_WIDTH,
    GuardedBrowser,
    guarded_browser,
)
from app.actions.browser.drivers.base import PortalJob, PortalSubmission
from app.actions.browser.errors import PortalError, PortalErrorCode

ChatTransport = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
MAX_IMAGES = 3


def _point(description: str) -> dict[str, Any]:
    return {
        "element": {"type": "string", "description": description},
        "x": {"type": "integer", "description": "X coordinate as integer in [0, 1000]"},
        "y": {"type": "integer", "description": "Y coordinate as integer in [0, 1000]"},
    }


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
            },
        },
    }


TOOLS: list[dict[str, Any]] = [
    _tool(
        "click",
        "Click at (x, y) coordinates",
        _point("Detailed description of the target UI element"),
    ),
    _tool(
        "write",
        "Click the text field at (x, y), clear it and type the text",
        {**_point("Detailed description of the text field"), "text": {"type": "string"}},
    ),
    _tool(
        "select_option",
        "Choose an option of the drop-down list at (x, y) by its visible label",
        {**_point("Detailed description of the drop-down list"), "option": {"type": "string"}},
    ),
    _tool("press_key", "Press a keyboard key such as Enter or Tab", {"key": {"type": "string"}}),
    _tool(
        "scroll",
        "Scroll the page",
        {"direction": {"type": "string", "enum": ["up", "down"]}},
    ),
    _tool(
        "answer",
        "Provide a final answer",
        {"content": {"type": "string", "description": "The answer content"}},
    ),
]

SYSTEM_PROMPT = (
    "You are a careful web agent operating a local reproduction of the Dell repair-request "
    "portal. Use only the data given in the task. Never open another website. When the "
    "confirmation page shows the case number, or if you cannot proceed, call answer."
)

SELECT_AT_POINT = """([x, y, label]) => {
  const el = document.elementFromPoint(x, y);
  const select = el && el.closest('select');
  if (!select) return false;
  const option = [...select.options].find((o) => o.textContent.trim() === label);
  if (!option) return false;
  select.value = option.value;
  select.dispatchEvent(new Event('input', {bubbles: true}));
  select.dispatchEvent(new Event('change', {bubbles: true}));
  return true;
}"""


def build_task(job: PortalJob) -> str:
    claim = job.claim
    lines = [
        f"File a repair request for Service Tag {claim.service_tag} on the open page.",
        f"If asked to sign in: e-mail {job.email}, then password {job.password}.",
        "Fill the form with exactly these values:",
        f"- Catégorie du problème: {claim.problem_category}",
        f"- Créneau de disponibilité: {claim.availability_slot}",
    ]
    lines += [f"- {field}: {value}" for field, value in claim.form_values().items() if value]
    lines += [
        "Tick the consent checkbox, submit the request with the submit button,",
        "then answer with the case number displayed on the confirmation page.",
    ]
    return "\n".join(lines)


def trim_to_last_n_images(messages: list[dict[str, Any]], n: int = MAX_IMAGES) -> None:
    seen = 0
    for message in reversed(messages):
        if message["role"] != "user" or not isinstance(message["content"], list):
            continue
        for chunk in message["content"]:
            if chunk.get("type") != "image_url":
                continue
            seen += 1
            if seen > n:
                chunk["type"] = "text"
                chunk["text"] = "[screenshot evicted]"
                chunk.pop("image_url", None)


def observation(png: bytes) -> dict[str, Any]:
    b64 = base64.b64encode(png).decode()
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": "<observation>\n"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": "\n</observation>"},
        ],
    }


def to_pixels(args: dict[str, Any]) -> tuple[float, float]:
    x, y = int(args["x"]), int(args["y"])
    if not (0 <= x <= 1000 and 0 <= y <= 1000):
        raise ValueError(f"coordinates out of range: {x}, {y}")
    return x / 1000 * VIEWPORT_WIDTH, y / 1000 * VIEWPORT_HEIGHT


class HCompanyDriver:
    name = "hcompany"

    def __init__(self, transport: ChatTransport | None = None) -> None:
        self._transport = transport

    def _resolve_transport(self, job: PortalJob) -> ChatTransport:
        if self._transport is not None:
            return self._transport
        key = job.settings.hcompany_api_key
        if key is None or not key.get_secret_value():
            raise PortalError(PortalErrorCode.ENGINE_UNAVAILABLE, "HCOMPANY_API_KEY is not set")
        url = job.settings.hcompany_base_url.rstrip("/") + "/chat/completions"
        secret = key.get_secret_value()
        timeout = job.settings.navigation_timeout_seconds * 4

        def post(body: dict[str, Any]) -> dict[str, Any]:
            request = urllib.request.Request(
                url,
                data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                data: dict[str, Any] = json.loads(response.read())
                return data

        async def transport(body: dict[str, Any]) -> dict[str, Any]:
            try:
                return await asyncio.to_thread(post, body)
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                raise PortalError(PortalErrorCode.AGENT_FAILED, f"H Company API: {exc}") from exc

        return transport

    async def submit(self, job: PortalJob) -> PortalSubmission:
        transport = self._resolve_transport(job)
        async with guarded_browser(job) as browser:
            await browser.goto(job.form_url)
            await browser.step("Agent Holo démarré sur la reproduction Dell", "agent-start")
            answer = await self.loop(browser, transport)
            await job.reporter.step(f"Réponse de l'agent : {answer[:200]}")
            return await browser.read_confirmation()

    async def loop(self, browser: GuardedBrowser, transport: ChatTransport) -> str:
        job = browser.job
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_task(job)},
        ]
        for index in range(job.settings.agent_max_steps):
            await self._attach_file_if_needed(browser)
            messages.append(observation(await browser.screenshot_bytes()))
            trim_to_last_n_images(messages)
            body = {
                "model": job.settings.hcompany_model,
                "messages": messages,
                "tools": TOOLS,
                "tool_choice": "required",
                "temperature": 0.8,
                "chat_template_kwargs": {"enable_thinking": True},
            }
            try:
                message = (await transport(body))["choices"][0]["message"]
            except PortalError:
                raise
            except (KeyError, IndexError, TypeError) as exc:
                raise PortalError(PortalErrorCode.AGENT_FAILED, "malformed model response") from exc
            calls = message.get("tool_calls") or []
            messages.append(
                {"role": "assistant", "content": message.get("content"), "tool_calls": calls}
            )
            for call in calls:
                name = str(call["function"]["name"])
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name == "answer":
                    return str(args.get("content", ""))
                result = await self.execute(browser, name, args)
                label = f"agent-{index + 1:02d}"
                await browser.step(f"Étape {index + 1} : {name} — {result}", label)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        raise PortalError(PortalErrorCode.AGENT_FAILED, "agent reached max steps without answering")

    async def _attach_file_if_needed(self, browser: GuardedBrowser) -> None:
        path = browser.job.claim.attachment_path
        page = browser.page
        if path is None or await page.locator("#attachment").count() == 0:
            return
        if not await page.locator("#attachment").evaluate("(el) => el.files.length > 0"):
            await page.set_input_files("#attachment", str(path))

    async def execute(self, browser: GuardedBrowser, name: str, args: dict[str, Any]) -> str:
        page = browser.page
        try:
            if name in {"click", "write", "select_option"}:
                x, y = to_pixels(args)
                if name == "select_option":
                    ok = await page.evaluate(SELECT_AT_POINT, [x, y, str(args.get("option", ""))])
                    return "option selected" if ok else "no matching drop-down option"
                await page.mouse.click(x, y)
                if name == "write":
                    await page.keyboard.press("ControlOrMeta+A")
                    await page.keyboard.type(str(args.get("text", "")))
            elif name == "press_key":
                await page.keyboard.press(str(args.get("key", "Enter")))
            elif name == "scroll":
                await page.mouse.wheel(0, -600 if args.get("direction") == "up" else 600)
            else:
                return f"unknown tool {name}"
            await page.wait_for_load_state(
                "domcontentloaded", timeout=browser.job.navigation_timeout_ms
            )
        except (ValueError, KeyError) as exc:
            return f"invalid arguments: {exc}"
        except Exception as exc:
            raise browser.fail_from(exc, f"agent action {name}") from exc
        browser.check()
        return "done"
