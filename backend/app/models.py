from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ConversationState(TypedDict, total=False):
    session_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    contact_name: str
    contact_email: str


class ChatRequest(TypedDict, total=False):
    session_id: str
    message: str
    name: str
    email: str
    selected_slot: str


class ChatResponse(TypedDict):
    session_id: str
    reply: str
    state: ConversationState
    available_slots: list[str]
