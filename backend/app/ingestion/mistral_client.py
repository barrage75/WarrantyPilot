import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from mistralai.client import Mistral
from mistralai.client.models import JSONSchema, ResponseFormat, SystemMessage, UserMessage


@dataclass(frozen=True)
class OcrPage:
    index: int
    markdown: str


class ExtractionClient(Protocol):
    def ocr(self, pdf: bytes) -> list[OcrPage]: ...

    def extract_json(
        self, system_prompt: str, document_block: str, json_schema: dict[str, Any]
    ) -> dict[str, Any]: ...


class MistralClient:
    def __init__(self, model: str = "mistral-large-latest") -> None:
        key = os.environ.get("MISTRAL_API_KEY")
        if not key:
            raise ValueError("MISTRAL_API_KEY is required")
        self._sdk = Mistral(api_key=key)
        self.model = model

    def ocr(self, pdf: bytes) -> list[OcrPage]:
        url = "data:application/pdf;base64," + base64.b64encode(pdf).decode("ascii")
        result = self._sdk.ocr.process(
            model="mistral-ocr-latest", document={"type": "document_url", "document_url": url}
        )
        return [OcrPage(index=page.index + 1, markdown=page.markdown) for page in result.pages]

    def extract_json(
        self, system_prompt: str, document_block: str, json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        messages: list[SystemMessage | UserMessage] = [
            SystemMessage(content=system_prompt),
            UserMessage(content=document_block),
        ]
        result = self._sdk.chat.complete(
            model=self.model,
            temperature=0,
            messages=messages,
            response_format=ResponseFormat(
                type="json_schema",
                json_schema=JSONSchema(name="invoice", schema_definition=json_schema, strict=True),
            ),
        )
        message = result.choices[0].message
        content = message.content if message is not None else None
        if not isinstance(content, str):
            raise ValueError("Mistral returned no JSON text")
        parsed: Any = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Mistral returned a non-object JSON response")
        return parsed
