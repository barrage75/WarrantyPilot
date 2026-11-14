from __future__ import annotations

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.contracts.models import DataChecklist
from app.core.tables import data_checklists, equipment


def ensure_data_checklist(
    session: Session, case_id: UUID | str, equipment_id: UUID | str | None
) -> None:
    if equipment_id is None:
        return
    category = session.execute(
        select(equipment.c.category).where(equipment.c.id == str(equipment_id))
    ).scalar_one_or_none()
    if not isinstance(category, str) or category.casefold() not in {
        "computer",
        "laptop",
        "notebook",
    }:
        return
    exists = session.execute(
        select(data_checklists.c.id).where(data_checklists.c.case_id == str(case_id))
    ).first()
    if exists is not None:
        return
    checklist = DataChecklist(case_id=UUID(str(case_id)))
    session.execute(
        insert(data_checklists).values(
            id=str(checklist.id),
            case_id=str(case_id),
            steps=checklist.model_dump(mode="json")["steps"],
        )
    )
