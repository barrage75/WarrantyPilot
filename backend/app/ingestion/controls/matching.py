import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.contracts.models import Equipment, Fact
from app.ingestion.controls.duplicates import normalize


def _serial(value: str) -> str:
    return re.sub(r"[\s-]", "", value.casefold())


@dataclass(frozen=True)
class LineMatch:
    document_id: UUID
    line: int
    method: Literal["serial", "model", "ambiguous", "unmatched"]
    candidate_ids: list[UUID]
    conflict: bool = False


@dataclass(frozen=True)
class MatchReport:
    matches: list[LineMatch]
    matched_facts: list[Fact]


def match_to_inventory(facts: list[Fact], inventory: list[Equipment]) -> MatchReport:
    lines: dict[tuple[UUID, int], list[Fact]] = {}
    for fact in facts:
        match = re.fullmatch(r"lines\[(\d+)\]\.(\w+)", fact.field)
        if match:
            lines.setdefault((fact.document_id, int(match[1])), []).append(fact)
    serial_matches: dict[tuple[UUID, int], list[Equipment]] = {}
    for key, line in lines.items():
        serials = {_serial(str(f.value)) for f in line if f.field.endswith(".serial") and f.value}
        serial_matches[key] = [item for item in inventory if _serial(item.serial) in serials]
    reserved = {item.id for candidates in serial_matches.values() for item in candidates}
    matches: list[LineMatch] = []
    copied: list[Fact] = []
    for key, line in lines.items():
        models = {normalize(str(f.value)) for f in line if f.field.endswith(".model") and f.value}
        candidates = serial_matches[key]
        method: Literal["serial", "model", "ambiguous", "unmatched"] = "serial"
        conflict = bool(
            candidates and models and any(normalize(c.model) not in models for c in candidates)
        )
        if not candidates:
            candidates = [
                item
                for item in inventory
                if item.id not in reserved and normalize(item.model) in models
            ]
            method = "model"
            if candidates and any(f.field.endswith(".serial") and f.value for f in line):
                conflict = True
        if len(candidates) > 1:
            method = "ambiguous"
        elif not candidates:
            method = "unmatched"
        else:
            copied.extend(
                fact.model_copy(update={"equipment_id": candidates[0].id}) for fact in line
            )
        matches.append(LineMatch(key[0], key[1], method, [c.id for c in candidates], conflict))
    return MatchReport(matches, copied)
