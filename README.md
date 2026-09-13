# US-Duct AI Appointment Agent MVP

A focused FastAPI + LangGraph backend and Next.js chat widget for US-Duct's industrial and commercial ducting consultation flow.

## Run the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY = "your-groq-api-key"
# Optional: use another model available to your Groq account
$env:GROQ_MODEL = "openai/gpt-oss-20b"
$env:BREVO_API_KEY = "your-brevo-api-key"
$env:EMAIL_SENDER = "verified-sender@example.com"
$env:EMAIL_SENDER_NAME = "US-Duct"
uvicorn app.main:app --reload --port 8000
```

The calendar remains mocked/in-memory for this MVP. Confirmation emails use Brevo's free transactional email API when `BREVO_API_KEY` and a verified `EMAIL_SENDER` are configured. Without those variables, the booking result reports `not_configured` instead of falsely claiming delivery.

The graph stores LangChain messages per `session_id`. The chatbot node answers normal questions directly; LangGraph routes to `get_available_slots` only after explicit booking agreement, then routes to `book_appointment_and_send_email` only after a selected slot.

Run tests with `pytest` from the `backend` directory.

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://localhost:8000` and runs at `http://localhost:3000`.

The calendar and email services are intentionally mocked/in-memory for this MVP.
