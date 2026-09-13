import json

from langchain_core.messages import AIMessage, HumanMessage

from app.graph import build_graph
from app.graph import chatbot_node, route_after_chatbot
from app.services import BOOKINGS, book_appointment_and_send_email, get_available_slots


class StubModel:
    def __init__(self, responses):
        self.responses = iter(responses)

    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        return next(self.responses)


def test_general_conversation_does_not_call_tools():
    response = chatbot_node(
        {"messages": [HumanMessage(content="What services do you provide?")]},
        StubModel([AIMessage(content="US-Duct provides industrial ducting, custom fabrication, and ventilation systems.")]),
    )["messages"][0]
    assert response.content.startswith("US-Duct provides")
    assert route_after_chatbot({"messages": [response]}) == "__end__"


def test_explicit_agreement_fetches_slots():
    response = chatbot_node(
        {"messages": [HumanMessage(content="I like these benefits, please book a meeting.")]},
        StubModel([AIMessage(content="", tool_calls=[{"name": "get_available_slots", "args": {}, "id": "slots-1", "type": "tool_call"}])]),
    )["messages"][0]
    assert route_after_chatbot({"messages": [response]}) == "tools"
    assert build_graph(StubModel([AIMessage(content="done")])) is not None


def test_selected_slot_books_and_simulates_email():
    BOOKINGS.clear()
    payload = json.loads(
        book_appointment_and_send_email.func(
            "2026-09-15T14:00:00+00:00", "Ava Khan", "ava@example.com"
        )
    )
    assert payload["meet_link"].startswith("https://meet.google.com/")
    assert payload["email_status"] in {"sent", "not_configured", "failed"}
    assert BOOKINGS[-1]["email"] == "ava@example.com"


def test_tools_return_structured_mvp_payloads():
    slots = json.loads(get_available_slots.func())
    booking = json.loads(
        book_appointment_and_send_email.func(
            slots["available_slots"][0], "Test User", "test@example.com"
        )
    )
    assert len(slots["available_slots"]) == 3
    assert booking["email"] == "test@example.com"


def test_booking_tool_requires_real_contact_details():
    schema = book_appointment_and_send_email.args_schema.model_json_schema()
    assert "name" in schema["required"]
    assert "email" in schema["required"]


def test_booking_without_email_configuration_is_truthful(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.delenv("EMAIL_SENDER", raising=False)
    payload = json.loads(
        book_appointment_and_send_email.func(
            "2026-09-15T14:00:00+00:00", "Ava Khan", "ava@example.com"
        )
    )
    assert payload["email_status"] == "not_configured"
