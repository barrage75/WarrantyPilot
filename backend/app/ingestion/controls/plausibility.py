import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from app.contracts.models import Fact

DEFAULT_PRICE_RANGES = {
    "laptop": (100, 10000),
    "monitor": (30, 5000),
    "headset": (5, 1500),
    "smartphone": (50, 5000),
    "dock": (10, 1000),
    "keyboard": (2, 600),
    "mouse": (2, 500),
    "keyboard/mouse": (2, 800),
}
DEFAULT_SERIAL_PATTERNS = {
    "dell": r"^[A-Z0-9]{7}$",
    "lenovo": r"^[A-Z0-9]{8}$",
    "hp": r"^[A-Z0-9]{10}$",
    "apple": r"^[A-Z0-9]{10,12}$",
}


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    detail: str
    fact_id: UUID


def check_plausibility(
    facts: list[Fact],
    *,
    reference_date: date,
    category: str | None = None,
    brand: str | None = None,
    price_ranges: Mapping[str, tuple[int | Decimal, int | Decimal]] = DEFAULT_PRICE_RANGES,
    serial_patterns: Mapping[str, str] = DEFAULT_SERIAL_PATTERNS,
) -> list[Issue]:
    issues: list[Issue] = []
    bounds = price_ranges.get(category.casefold()) if category else None
    pattern = serial_patterns.get(brand.casefold()) if brand else None
    for fact in facts:
        code: str | None = None
        if fact.field == "invoice_date":
            try:
                if date.fromisoformat(str(fact.value)) > reference_date:
                    code = "future_invoice_date"
            except ValueError:
                code = "invalid_invoice_date"
        elif fact.field.endswith(".quantity") or (fact.field.endswith(".unit_price_ht") and bounds):
            try:
                value = Decimal(str(fact.value))
                if not value.is_finite():
                    code = "invalid_number"
                elif fact.field.endswith(".quantity") and value <= 0:
                    code = "nonpositive_quantity"
                elif (
                    fact.field.endswith(".unit_price_ht")
                    and bounds
                    and not bounds[0] <= value <= bounds[1]
                ):
                    code = "price_out_of_range"
            except InvalidOperation:
                code = "invalid_number"
        elif (
            fact.field.endswith(".serial")
            and pattern
            and not re.fullmatch(pattern, str(fact.value))
        ):
            code = "invalid_serial"
        if code:
            issues.append(Issue(code, fact.field, f"{code}: {fact.value}", fact.id))
    return issues
