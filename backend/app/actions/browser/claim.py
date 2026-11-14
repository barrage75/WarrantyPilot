"""Form data for the Dell repair request, read only from ``Action.payload``."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.actions.browser.errors import PortalError, PortalErrorCode

ProblemCategory = Literal[
    "Ne démarre pas",
    "Écran",
    "Clavier/pavé tactile",
    "Batterie/alimentation",
    "Disque/stockage",
    "Carte mère/autre matériel",
    "Logiciel",
]
AvailabilitySlot = Literal["Matin 8h–12h", "Après-midi 13h–18h"]
ReproFailMode = Literal["500", "timeout", "slow"]


class PortalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    service_tag: str = Field(pattern=r"^[A-Z0-9]{7}$")
    problem_category: ProblemCategory
    problem_description: str = Field(min_length=20, max_length=2000)
    contact_first_name: str = Field(min_length=1, max_length=80)
    contact_last_name: str = Field(min_length=1, max_length=80)
    contact_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    contact_phone: str = Field(min_length=10, max_length=20)
    company_name: str = ""
    address_line1: str = Field(min_length=1, max_length=120)
    address_line2: str = ""
    postal_code: str = Field(pattern=r"^\d{5}$")
    city: str = Field(min_length=1, max_length=80)
    availability_date: date
    availability_slot: AvailabilitySlot
    attachment_path: Path | None = None
    repro_fail_mode: ReproFailMode | None = None

    @field_validator("service_tag", mode="before")
    @classmethod
    def upper_tag(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("attachment_path")
    @classmethod
    def pdf_only(cls, value: Path | None) -> Path | None:
        if value is not None and value.suffix.lower() != ".pdf":
            raise ValueError("attachment must be a PDF file")
        return value

    def form_values(self) -> dict[str, str]:
        """Values keyed by the ids of the reproduction form fields."""
        return {
            "problemDescription": self.problem_description,
            "contactFirstName": self.contact_first_name,
            "contactLastName": self.contact_last_name,
            "contactEmail": self.contact_email,
            "contactPhone": self.contact_phone,
            "companyName": self.company_name,
            "addressLine1": self.address_line1,
            "addressLine2": self.address_line2,
            "postalCode": self.postal_code,
            "city": self.city,
            "availabilityDate": self.availability_date.isoformat(),
        }


def parse_claim(payload: dict[str, Any]) -> PortalClaim:
    raw = payload.get("portal_claim")
    if not isinstance(raw, dict):
        raise PortalError(PortalErrorCode.INVALID_PAYLOAD, "payload.portal_claim is missing")
    try:
        return PortalClaim.model_validate(raw)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in err["loc"]) for err in exc.errors()})
        raise PortalError(PortalErrorCode.INVALID_PAYLOAD, ", ".join(fields)) from exc
