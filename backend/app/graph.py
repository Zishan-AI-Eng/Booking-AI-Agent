import os
from pathlib import Path
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, SystemMessage
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .models import ConversationState
from .knowledge import US_DUCT_KNOWLEDGE
from .services import book_appointment_and_send_email, get_available_slots

from dotenv import load_dotenv

try:
    import langchain
except ImportError:
    pass
else:
    if not hasattr(langchain, "verbose"):
        langchain.verbose = False
    if not hasattr(langchain, "debug"):
        langchain.debug = False
    if not hasattr(langchain, "llm_cache"):
        langchain.llm_cache = None

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ROOT_ENV_FILE, override=True)

SYSTEM_PROMPT = """You are the US-Duct appointment assistant.

US-Duct serves industrial and commercial customers with industrial ducting,
ventilation systems, clamp-together ducting, and custom fabrication.

Behavior rules:
- Sound like a capable human account manager: warm, direct, attentive, and natural. Never sound like a script, checklist, or chatbot.
- Keep replies concise: normally 1-3 short sentences. For several items, use a clean Markdown list with no more than 5 bullets and a blank line before it.
- Prefer a short heading plus a few bullets when listing services, products, or options. Never put an entire answer into one dense paragraph.
- Use plain Markdown only: headings, bullets, and bold labels. Do not use emojis, decorative symbols, or long unbroken text.
- Use the conversation history. Do not repeat information the visitor already gave you, and ask only one clear question at a time.
- For a greeting, respond naturally and briefly introduce how you can help with US-Duct's industrial services.
- Answer service questions with industrial ducting, ventilation systems, clamp-together ducting, and custom fabrication. You own the conversation and can handle the lead yourself; never say you will connect or forward the visitor to a specialist.
- Explain benefits in practical language: faster installation, flexible layouts, reliable airflow, easier expansion, and fabrication matched to the project.
- Never push a booking while the visitor is asking a general question. Answer first, then let the visitor decide what to do next.
- When the visitor explicitly agrees to meet, first collect their full name and work email if either is missing. Ask naturally: "Absolutely. What name and work email should I put on the invitation?"
- Do not call get_available_slots until the visitor has explicitly agreed to meet and both name and email are known.
- After get_available_slots returns, present the slots clearly and ask which one they prefer. Do not book until the visitor selects a slot.
- Only call book_appointment_and_send_email after the visitor selects an offered slot and you have their real name and email. Never use placeholder contact details.
- After successful booking, include the returned Google Meet link. Say the confirmation email was sent only when email_status is "sent"; if it is "not_configured" or "failed", say the meeting is booked but the email could not be sent yet.
- Do not invent pricing, certifications, lead times, or technical specifications. Say when a detail needs confirmation while still keeping ownership of the conversation.
- Residential AC repair and unrelated home HVAC work are out of scope. Decline briefly and do not call either tool.

Current contact details, if supplied by the API client:
{contact_context}

US-DUCT KNOWLEDGE BASE:
{knowledge}
"""


def chatbot_node(state: ConversationState, model: BaseChatModel) -> dict[str, Any]:
    contact_context = (
        f"name={state.get('contact_name', 'not supplied')}, "
        f"email={state.get('contact_email', 'not supplied')}"
    )
    llm = model.bind_tools([get_available_slots, book_appointment_and_send_email])
    prompt = [
        SystemMessage(
            content=SYSTEM_PROMPT.format(
                contact_context=contact_context,
                knowledge=US_DUCT_KNOWLEDGE,
            )
        ),
        *state["messages"],
    ]
    try:
        writer = get_stream_writer()
    except RuntimeError:
        writer = lambda _event: None
    response: AIMessageChunk | None = None
    stream = llm.stream(prompt) if hasattr(llm, "stream") else [llm.invoke(prompt)]
    for chunk in stream:
        if isinstance(chunk, AIMessageChunk):
            response = chunk if response is None else response + chunk
            if isinstance(chunk.content, str) and chunk.content:
                writer({"type": "token", "content": chunk.content})
        else:
            response = chunk
    if response is None:
        raise RuntimeError("The model returned no response.")
    return {"messages": [response]}


def route_after_chatbot(state: ConversationState) -> str:
    last_message = state["messages"][-1]
    return "tools" if getattr(last_message, "tool_calls", None) else END


def build_graph(model: BaseChatModel | None = None):
    configured_model = os.getenv("GROQ_MODEL", "").strip()
    unavailable_models = {
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
    }
    if configured_model in unavailable_models:
        configured_model = "openai/gpt-oss-20b"
    selected_model = model or ChatGroq(
        model=configured_model or "openai/gpt-oss-20b",
        temperature=0.3,
        max_tokens=300,
    )
    graph = StateGraph(ConversationState)
    graph.add_node("chatbot", lambda state: chatbot_node(state, selected_model))
    graph.add_node("tools", ToolNode([get_available_slots, book_appointment_and_send_email]))
    graph.add_edge(START, "chatbot")
    graph.add_conditional_edges("chatbot", route_after_chatbot, {"tools": "tools", END: END})
    graph.add_edge("tools", "chatbot")
    return graph.compile()
