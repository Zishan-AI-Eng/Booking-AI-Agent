import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from langchain_core.tools import tool

BOOKINGS: list[dict[str, str]] = []


def _confirmation_html(name: str, slot: str, meet_link: str) -> str:
    appointment_time = datetime.fromisoformat(slot.replace("Z", "+00:00")).strftime("%B %d, %Y at %H:%M UTC")
    return f"""
    <div style=\"font-family:Arial,sans-serif;max-width:600px;color:#15251f;line-height:1.6\">
      <h2 style=\"color:#15251f\">Your US-Duct consultation is confirmed</h2>
      <p>Hello {name},</p>
      <p>Your consultation with US-Duct has been confirmed.</p>
      <p><strong>Date and time:</strong> {appointment_time}<br>
      <strong>Google Meet:</strong> <a href=\"{meet_link}\">Join the meeting</a></p>
      <p>We look forward to learning more about your industrial ductwork, dust collection, or ventilation project.</p>
      <p>Best,<br>US-Duct</p>
    </div>
    """


def _send_brevo_confirmation(name: str, email: str, slot: str, meet_link: str) -> str:
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_email = os.getenv("EMAIL_SENDER", "").strip()
    sender_name = os.getenv("EMAIL_SENDER_NAME", "US-Duct").strip()
    if not api_key or not sender_email:
        return "not_configured"

    appointment_time = datetime.fromisoformat(slot.replace("Z", "+00:00")).strftime("%B %d, %Y at %H:%M UTC")
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": email, "name": name}],
        "subject": "Your US-Duct consultation is confirmed",
        "textContent": (
            f"Hello {name},\n\nYour US-Duct consultation is confirmed for "
            f"{appointment_time}.\n\nGoogle Meet: {meet_link}\n\n"
            "We look forward to speaking with you.\n\nBest,\nUS-Duct"
        ),
        "htmlContent": _confirmation_html(name, slot, meet_link),
    }
    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={"accept": "application/json", "api-key": api_key, "content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if 200 <= response.status < 300:
                return "sent"
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return "failed"
    return "failed"


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
    """Book the selected slot and send a confirmation email through Brevo.

    Call this only after the visitor has selected one of the offered slots and provided real contact details.
    """
    event_id = f"mock-event-{uuid4().hex[:10]}"
    meet_link = f"https://meet.google.com/us-duct-{event_id[-6:]}"
    email_status = _send_brevo_confirmation(name, email, slot, meet_link)
    booking = {
        "event_id": event_id,
        "slot": slot,
        "name": name,
        "email": email,
        "meet_link": meet_link,
        "email_status": email_status,
    }
    BOOKINGS.append(booking)
    return json.dumps(booking)
