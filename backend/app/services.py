import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langchain_core.tools import tool

BOOKINGS: list[dict[str, str]] = []


@tool
def get_available_slots() -> str:
    """Return three available consultation times in UTC.

    Call this only after the visitor explicitly agrees to book a meeting.
    """
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    slots = [
        (now + timedelta(days=1, hours=2)).isoformat(),
        (now + timedelta(days=2, hours=4)).isoformat(),
        (now + timedelta(days=3, hours=1)).isoformat(),
    ]
    return json.dumps({"available_slots": slots, "timezone": "UTC"})


@tool
def book_appointment_and_send_email(
    slot: str,
    name: str,
    email: str,
) -> str:
    """Book the selected slot and simulate an email confirmation.

    Call this only after the visitor has selected one of the offered slots.
    """
    event_id = f"mock-event-{uuid4().hex[:10]}"
    meet_link = f"https://meet.google.com/us-duct-{event_id[-6:]}"
    booking = {
        "event_id": event_id,
        "slot": slot,
        "name": name,
        "email": email,
        "meet_link": meet_link,
        "email_status": "simulated_sent",
    }
    BOOKINGS.append(booking)
    return json.dumps(booking)
