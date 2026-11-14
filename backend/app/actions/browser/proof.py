"""Proof attached to a successful ``ActionResult`` (serialized as JSON)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class PortalProof(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = "dell_repair_request"
    reality: str = "reproduction"
    case_number: str = Field(min_length=1)
    url: str = Field(min_length=1)
    screenshot_path: str = Field(min_length=1)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    engine: str
    request_token: str
    replayed: bool = False

    def to_json(self) -> str:
        return self.model_dump_json()
