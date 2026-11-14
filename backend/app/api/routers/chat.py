from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Literal, Protocol
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_orchestrator, get_session
from app.contracts.enums import EventType, IncidentReportedVia
from app.core.journal import append_event
from app.core.orchestrator import Orchestrator
from app.core.tables import people
from app.intake.reporting import report_failure

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
    result = report_failure(
        session, body.reporter_id, body.text, reported_via=IncidentReportedVia.CHAT
    )
    case_id = result.case_id
    equipment_label = result.equipment_label
    questions = result.questions
    if case_id is not None:
        session.commit()
        await orchestrator.run(UUID(case_id))
        reply_text = f"J'ai identifié {equipment_label} et créé le dossier de garantie."
    else:
        reply_text = questions[0]
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
