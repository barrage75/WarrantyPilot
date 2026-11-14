from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_orchestrator, get_session
from app.contracts.enums import (
    CaseStatus,
    Channel,
    EventType,
    IncidentKind,
    IncidentReportedVia,
    RealityBadge,
)
from app.contracts.models import utc_now
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.tables import cases, equipment, incidents, people

router = APIRouter(prefix="/chat", tags=["chat"])

DISCLOSURE_TEXT = (
    "Cette conversation est assistée par une intelligence artificielle. "
    "Toute décision de garantie reste soumise à validation humaine."
)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    role: Literal["human", "assistant"]
    text: str | None = None
    text_key: str | None = Field(default=None, alias="textKey")


class ChatConversation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    conversation_id: str
    messages: list[ChatMessage]
    disclosure_text: str


class ChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    reporter_id: UUID


class ChatReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: ChatMessage
    messages: list[ChatMessage]
    case_id: str | None = None
    equipment: str | None = None
    identified_equipment: str | None = None
    questions: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)


class ChatLLM(Protocol):
    async def rephrase_reply(
        self,
        *,
        text: str,
        equipment: str | None,
        questions: list[str],
        case_id: str | None,
    ) -> str: ...


@router.post("/conversations", response_model=ChatConversation)
def start_conversation(
    request: Request,
    session: Session = Depends(get_session),
) -> ChatConversation:
    conversation_id = str(uuid4())
    messages = [ChatMessage(id=str(uuid4()), role="assistant", text_key="greeting")]
    conversations: dict[str, list[ChatMessage]] = request.app.state.chat_conversations
    conversations[conversation_id] = messages
    append_event(
        session,
        EventType.CHAT_DISCLOSURE,
        actor="system",
        payload={
            "conversation_id": conversation_id,
            "disclosure_text": DISCLOSURE_TEXT,
        },
    )
    session.commit()
    return ChatConversation(
        id=conversation_id,
        conversation_id=conversation_id,
        messages=messages,
        disclosure_text=DISCLOSURE_TEXT,
    )


def _equipment_category(text: str) -> str | None:
    folded = text.casefold()
    terms = (
        (("casque", "écouteur", "micro"), "headset"),
        (("ordinateur", "portable", "latitude", "pc"), "laptop"),
        (("écran", "moniteur"), "monitor"),
        (("imprimante", "laserjet"), "printer"),
    )
    for words, category in terms:
        if any(word in folded for word in words):
            return category
    return None


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ChatReply,
)
async def send_message(
    conversation_id: str,
    body: ChatMessageRequest,
    request: Request,
    session: Session = Depends(get_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ChatReply:
    conversations: dict[str, list[ChatMessage]] = request.app.state.chat_conversations
    messages = conversations.get(conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if (
        session.execute(select(people.c.id).where(people.c.id == str(body.reporter_id))).first()
        is None
    ):
        raise HTTPException(status_code=404, detail="Reporter not found")

    messages.append(ChatMessage(id=str(uuid4()), role="human", text=body.text.strip()))
    rows = (
        session.execute(
            select(
                equipment.c.id,
                equipment.c.brand,
                equipment.c.model,
                equipment.c.serial,
                equipment.c.category,
            )
            .where(equipment.c.assigned_to == str(body.reporter_id))
            .order_by(equipment.c.model, equipment.c.serial)
        )
        .mappings()
        .all()
    )
    category = _equipment_category(body.text)
    folded_text = body.text.casefold()
    explicit = [
        row
        for row in rows
        if str(row["serial"]).casefold() in folded_text
        or str(row["model"]).casefold() in folded_text
    ]
    candidates = explicit or [
        row for row in rows if category is None or row["category"] == category
    ]
    questions: list[str] = []
    identified = None
    case_id: str | None = None
    if len(candidates) != 1:
        if not candidates:
            questions = ["Quel équipement est concerné ?"]
        else:
            labels = ", ".join(f"{row['brand']} {row['model']}" for row in candidates)
            questions = [f"Quel équipement est concerné parmi {labels} ?"]
        reply_text = questions[0]
    else:
        identified = candidates[0]
        incident_id = uuid4()
        case_uuid = uuid4()
        created_at = utc_now()
        session.execute(
            insert(incidents).values(
                id=str(incident_id),
                kind=IncidentKind.FAILURE.value,
                reporter_id=str(body.reporter_id),
                equipment_id=identified["id"],
                description=body.text.strip(),
                reported_via=IncidentReportedVia.CHAT.value,
                created_at=created_at.isoformat(),
            )
        )
        session.execute(
            insert(cases).values(
                id=str(case_uuid),
                incident_id=str(incident_id),
                equipment_id=identified["id"],
                status=CaseStatus.PREPARED.value,
                channel=Channel.MANUAL.value,
                verdict_id=None,
                policy_id=None,
                badge=RealityBadge.SIMULATED.value,
                created_at=created_at.isoformat(),
                updated_at=created_at.isoformat(),
            )
        )
        append_event(
            session,
            EventType.CASE_CREATED,
            case_id=str(case_uuid),
            payload={
                "incident_id": str(incident_id),
                "equipment_id": str(identified["id"]),
                "reported_via": IncidentReportedVia.CHAT.value,
            },
        )
        session.commit()
        await orchestrator.run(case_uuid)
        case_id = str(case_uuid)
        equipment_label = f"{identified['brand']} {identified['model']}"
        reply_text = f"J'ai identifié {equipment_label} et créé le dossier de garantie."

    equipment_label = (
        f"{identified['brand']} {identified['model']}" if identified is not None else None
    )
    assistant: ChatLLM | None = request.app.state.services.get("chat_llm")
    if os.getenv("MISTRAL_API_KEY") and assistant is not None:
        rephrase: Callable[..., Awaitable[str]] = assistant.rephrase_reply
        reply_text = await rephrase(
            text=reply_text,
            equipment=equipment_label,
            questions=questions,
            case_id=case_id,
        )
    reply = ChatMessage(id=str(uuid4()), role="assistant", text=reply_text)
    messages.append(reply)
    return ChatReply(
        message=reply,
        messages=messages,
        case_id=case_id,
        equipment=equipment_label,
        identified_equipment=equipment_label,
        questions=questions,
        clarifying_questions=questions,
    )
