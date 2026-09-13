import json
from collections.abc import Generator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, EmailStr, Field
from starlette.responses import StreamingResponse

from .graph import build_graph
from .models import ConversationState

sessions: dict[str, dict[str, Any]] = {}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(min_length=1)
    name: str | None = None
    email: EmailStr | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> Generator[None, None, None]:
    yield
    sessions.clear()


app = FastAPI(title="US-Duct Groq Appointment Agent", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    session_id = request.session_id or str(uuid4())
    previous = sessions.get(session_id, {})
    state: ConversationState = {
        "session_id": session_id,
        "messages": [*previous.get("messages", []), HumanMessage(content=request.message)],
    }
    contact_name = request.name or previous.get("contact_name")
    contact_email = str(request.email) if request.email else previous.get("contact_email")
    if contact_name:
        state["contact_name"] = contact_name
    if contact_email:
        state["contact_email"] = contact_email

    try:
        result = build_graph().invoke(state)
    except Exception as exc:
        if "GROQ_API_KEY" in str(exc) or "api_key" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail="Set GROQ_API_KEY before using the chat agent.",
            ) from exc
        raise HTTPException(status_code=502, detail="The chat agent could not complete the request.") from exc

    sessions[session_id] = {
        "messages": result["messages"],
        "contact_name": result.get("contact_name", contact_name),
        "contact_email": result.get("contact_email", contact_email),
    }
    reply = next(
        (
            message.content
            for message in reversed(result["messages"])
            if isinstance(message, AIMessage) and isinstance(message.content, str) and message.content
        ),
        "I could not generate a response.",
    )
    available_slots: list[str] = []
    booking: dict[str, Any] | None = None
    for message in result["messages"]:
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if message.name == "get_available_slots":
            available_slots = payload.get("available_slots", [])
        if message.name == "book_appointment_and_send_email":
            booking = payload

    return {
        "session_id": session_id,
        "reply": reply,
        "available_slots": available_slots,
        "booking": booking,
        "message_count": len(result["messages"]),
    }


def _tool_results(messages: list[Any]) -> tuple[list[str], dict[str, Any] | None]:
    available_slots: list[str] = []
    booking: dict[str, Any] | None = None
    for message in messages:
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        try:
            payload = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if message.name == "get_available_slots":
            available_slots = payload.get("available_slots", [])
        elif message.name == "book_appointment_and_send_email":
            booking = payload
    return available_slots, booking


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=True)}\n\n"


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or str(uuid4())
    previous = sessions.get(session_id, {})
    contact_name = request.name or previous.get("contact_name")
    contact_email = str(request.email) if request.email else previous.get("contact_email")
    state: ConversationState = {
        "session_id": session_id,
        "messages": [*previous.get("messages", []), HumanMessage(content=request.message)],
    }
    if contact_name:
        state["contact_name"] = contact_name
    if contact_email:
        state["contact_email"] = contact_email

    def generate() -> Generator[str, None, None]:
        final_state: dict[str, Any] | None = None
        try:
            yield _sse({"type": "start", "session_id": session_id})
            for mode, payload in build_graph().stream(
                state,
                stream_mode=["custom", "values"],
            ):
                if mode == "custom" and isinstance(payload, dict) and payload.get("type") == "token":
                    yield _sse(payload)
                elif mode == "values":
                    final_state = payload

            if final_state is None:
                raise RuntimeError("The graph ended without a final state.")
            messages = final_state["messages"]
            sessions[session_id] = {
                "messages": messages,
                "contact_name": final_state.get("contact_name", contact_name),
                "contact_email": final_state.get("contact_email", contact_email),
            }
            available_slots, booking = _tool_results(messages)
            yield _sse(
                {
                    "type": "done",
                    "session_id": session_id,
                    "available_slots": available_slots,
                    "booking": booking,
                    "message_count": len(messages),
                }
            )
        except Exception as exc:
            detail = "Set GROQ_API_KEY before using the chat agent." if "api_key" in str(exc).lower() else "The assistant could not complete the request."
            yield _sse({"type": "error", "detail": detail})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
