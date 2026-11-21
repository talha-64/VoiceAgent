import os
import re
import hmac
import time
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, status, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import AsyncGroq, Groq

import database
import tools

# ==============================================================================
# 1. Environment & Logging Configuration
# ==============================================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("hospital-voice-agent")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
VAPI_PUBLIC_KEY = os.getenv("VAPI_PUBLIC_KEY", "").strip()
VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY", "").strip()
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "").strip()
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()

VAPI_WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
AGENT_MD_PATH = BASE_DIR / "agent.md"

# ==============================================================================
# 2. System Prompt Loader & Dynamic Context Builder
# ==============================================================================
def load_base_system_prompt() -> str:
    """Extracts the base system prompt from agent.md."""
    try:
        if AGENT_MD_PATH.exists():
            content = AGENT_MD_PATH.read_text(encoding="utf-8")
            match = re.search(r"```text\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                return match.group(1).strip()
    except Exception as e:
        logger.error("Error reading agent.md: %s", e)
    
    return (
        "تم شفا کیئر ہسپتال کی استقبالیہ آفیسر عائشہ ہو۔ روزمرہ کی رواں اور شائستہ اردو میں بات کرو۔ "
        "مریضوں کے لیے ڈاکٹروں کے اوقات دیکھ کر اپائنٹمنٹ بک، تبدیل یا منسوخ کرو۔ جواب 1 سے 2 جملے رکھو۔"
    )

BASE_SYSTEM_PROMPT = load_base_system_prompt()

def build_dynamic_system_prompt() -> str:
    """
    Builds the real-time context containing today's date, day of week,
    current doctors, schedules, fees, and booked slots for instant awareness.
    """
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    today_day = today.strftime("%A")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_day = (today + timedelta(days=1)).strftime("%A")

    doctors = database.get_all_doctors()
    doc_lines = []
    for d in doctors:
        doc_lines.append(
            f"- {d['name']} ({d['name_en']}) | شعبہ: {d['specialty']} ({d['specialty_en']}) | "
            f"دن: {d['available_days']} | اوقات: {d['start_time']} تا {d['end_time']} | "
            f"کمرہ: {d['room_number']} | فیس: Rs. {d['consultation_fee']}"
        )
    doctors_context = "\n".join(doc_lines)

    # Today's active appointments
    active_apts = database.get_all_appointments(date_filter=today_str, status_filter="confirmed")
    booked_slots_info = []
    for a in active_apts[:10]:
        booked_slots_info.append(f"{a['doctor_name']} ({a['time_slot']}) - بک ہو چکا ہے")
    booked_text = "\n".join(booked_slots_info) if booked_slots_info else "آج کے لیے تمام ابتدائی سلاٹس دستیاب ہیں۔"

    dynamic_context = f"""{BASE_SYSTEM_PROMPT}

حقیقی وقت کی ہسپتال معلومات (Real-time Hospital State):
- آج کی تاریخ: {today_str} ({today_day})
- کل کی تاریخ: {tomorrow_str} ({tomorrow_day})

ہمارے ڈاکٹرز اور او پی ڈی نظام الاوقات:
{doctors_context}

آج کی پہلے سے بک شدہ سلاٹس:
{booked_text}

اہم ہدایات برائے اپائنٹمنٹ مینجمنٹ:
1. جب کالر ڈاکٹر یا اوقات پوچھے، فہرست سے دیکھ کر بتائیں یا مناسب معلومات دیں۔
2. نیا اپائنٹمنٹ بک کرنے کے لیے: مریض کا نام، موبائل نمبر اور وقت معلوم کریں، اور جواب کے آخر میں یہ ایکشن ٹیگ شامل کریں:
   [ACTION: BOOK | patient_name=نام | phone=فون | doctor_id=1 | date={today_str} | slot=10:30 AM | reason=وجہ]
3. اپائنٹمنٹ منسوخ کرنے کے لیے:
   [ACTION: CANCEL | identifier=فون_نمبر_یا_اپائنٹمنٹ_نمبر]
4. اپائنٹمنٹ ری شیڈول (تبدیل) کرنے کے لیے:
   [ACTION: RESCHEDULE | identifier=فون_نمبر_یا_اپائنٹمنٹ_نمبر | new_date={tomorrow_str} | new_slot=11:30 AM]
5. اپنے بولنے والے اردو جملے میں مریض کو یقین دہانی کرائیں کہ ان کا کام ہو گیا ہے۔ ایکشن ٹیگ آواز میں نہیں بولا جائے گا۔
"""
    return dynamic_context

# Initialize Groq Client
groq_async_client: Optional[AsyncGroq] = None
groq_sync_client: Optional[Groq] = None

if GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_your") and not GROQ_API_KEY.startswith("your_"):
    groq_async_client = AsyncGroq(api_key=GROQ_API_KEY)
    groq_sync_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq clients initialized successfully with model '%s'", DEFAULT_MODEL)
else:
    logger.warning("GROQ_API_KEY is not configured or placeholder.")

# ==============================================================================
# 3. FastAPI App Setup
# ==============================================================================
app = FastAPI(
    title="Shifa Care Hospital - Voice Receptionist & Clinical Operations",
    description="Urdu Voice Receptionist with real-time Appointment Management and Doctor Scheduling.",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_vapi_request(request: Request) -> None:
    """Verifies optional shared secret."""
    if not VAPI_WEBHOOK_SECRET:
        return
    supplied = request.headers.get("x-vapi-secret", "")
    if not supplied:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
    if not hmac.compare_digest(supplied.encode(), VAPI_WEBHOOK_SECRET.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")

# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ==============================================================================
# 4. Pydantic Models for REST API
# ==============================================================================
class AppointmentCreateRequest(BaseModel):
    patient_name: str
    patient_phone: str
    doctor_id: int
    appointment_date: str
    time_slot: str
    reason: Optional[str] = "General Consultation"

class AppointmentUpdateRequest(BaseModel):
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_id: Optional[int] = None
    appointment_date: Optional[str] = None
    time_slot: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[str] = None

# ==============================================================================
# 5. Core Dashboard & Operations REST API
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serves the Unified Hospital Receptionist & Appointment Dashboard."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Shifa Care Hospital Backend Active</h1>")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "phase": 2,
        "service": "Shifa Care Hospital - Urdu Voice Receptionist & Appointment System",
        "groq_configured": bool(groq_async_client),
        "groq_model": DEFAULT_MODEL,
        "vapi_configured": bool(VAPI_PUBLIC_KEY and not VAPI_PUBLIC_KEY.startswith("your_")),
        "timestamp": time.time()
    }

@app.get("/api/config")
async def get_config():
    """Provides configuration values to the frontend."""
    return {
        "vapi_public_key": VAPI_PUBLIC_KEY if not VAPI_PUBLIC_KEY.startswith("your_") else "",
        "vapi_assistant_id": VAPI_ASSISTANT_ID if not VAPI_ASSISTANT_ID.startswith("your_") else "",
        "groq_configured": bool(groq_async_client)
    }

@app.get("/api/stats")
async def get_stats():
    """Returns real-time operational statistics for the dashboard cards."""
    return database.get_dashboard_stats()

@app.get("/api/doctors")
async def list_doctors():
    """Returns all registered doctors with specialties, room numbers, and OPD hours."""
    return database.get_all_doctors()

@app.get("/api/doctors/{doctor_id}/slots")
async def get_doctor_slots(doctor_id: int, date: Optional[str] = None):
    """Calculates available and booked time slots for a doctor on a specific date."""
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    return database.get_doctor_availability_and_slots(doctor_id, target_date)

@app.get("/api/appointments")
async def list_appointments(
    search: Optional[str] = None,
    doctor_id: Optional[int] = None,
    status: Optional[str] = None,
    date: Optional[str] = None
):
    """Fetches appointments with search and filtering support."""
    return database.get_all_appointments(
        search=search,
        doctor_id=doctor_id,
        status_filter=status,
        date_filter=date
    )

@app.post("/api/appointments")
async def create_new_appointment(payload: AppointmentCreateRequest):
    """Books a new appointment from the dashboard modal."""
    result = database.create_appointment(
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        doctor_id=payload.doctor_id,
        appointment_date=payload.appointment_date,
        time_slot=payload.time_slot,
        reason=payload.reason
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@app.put("/api/appointments/{appointment_id}")
async def update_existing_appointment(appointment_id: int, payload: AppointmentUpdateRequest):
    """Updates appointment details, status, or date/time slot."""
    result = database.update_appointment(
        appointment_id=appointment_id,
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        doctor_id=payload.doctor_id,
        appointment_date=payload.appointment_date,
        time_slot=payload.time_slot,
        reason=payload.reason,
        status=payload.status
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@app.delete("/api/appointments/{appointment_id}")
async def cancel_existing_appointment(appointment_id: int):
    """Cancels an appointment."""
    result = database.cancel_appointment(str(appointment_id))
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result

# ==============================================================================
# 6. Action Tag Parser for Voice Agent Real-time DB Operations
# ==============================================================================

def execute_parsed_action(action_text: str) -> Optional[Dict[str, Any]]:
    """
    Parses action tags emitted by the LLM (e.g. [ACTION: BOOK | patient_name=...])
    and executes them in the SQLite database.
    """
    try:
        match = re.search(r"\[ACTION:\s*([A-Z_]+)\s*\|\s*(.*?)\]", action_text, re.DOTALL)
        if not match:
            return None

        action_type = match.group(1).upper()
        raw_params = match.group(2)

        # Parse key=value pairs
        params = {}
        for part in raw_params.split("|"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()

        logger.info("⚡ Voice Agent Dispatched Action: %s with params: %s", action_type, params)

        if action_type == "BOOK":
            doc_id = int(params.get("doctor_id", 1)) if params.get("doctor_id", "").isdigit() else 1
            if "doctor_name" in params and not params.get("doctor_id"):
                doc = database.find_doctor_by_query(params["doctor_name"])
                if doc:
                    doc_id = doc["id"]

            return database.create_appointment(
                patient_name=params.get("patient_name", "مریض"),
                patient_phone=params.get("phone", "03000000000"),
                doctor_id=doc_id,
                appointment_date=tools.resolve_date_str(params.get("date")),
                time_slot=params.get("slot", "10:00 AM"),
                reason=params.get("reason", "Voice Call Consultation")
            )

        elif action_type == "CANCEL":
            ident = params.get("identifier") or params.get("phone") or params.get("appointment_number", "")
            return database.cancel_appointment(ident)

        elif action_type == "RESCHEDULE":
            ident = params.get("identifier") or params.get("phone") or params.get("appointment_number", "")
            apt = database.get_appointment_by_id_or_number(ident)
            if apt:
                return database.update_appointment(
                    appointment_id=apt["id"],
                    appointment_date=tools.resolve_date_str(params.get("new_date")),
                    time_slot=params.get("new_slot", apt["time_slot"]),
                    status="rescheduled"
                )

    except Exception as e:
        logger.error("Error executing parsed action: %s", e, exc_info=True)
    return None

def strip_action_tags(text: str) -> str:
    """Removes [ACTION: ...] tags from text so TTS speaks only natural Urdu."""
    cleaned = re.sub(r"\[ACTION:\s*.*?\]", "", text, flags=re.DOTALL)
    # Also clean any stray tool markup
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"<function.*?>", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"</function>", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()

# ==============================================================================
# 7. Vapi Custom LLM: POST /chat/completions (OpenAI Compatible)
# ==============================================================================

@app.post("/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint called by Vapi's Custom LLM.
    Equipped with real-time database context injection and autonomous tool execution.
    """
    verify_vapi_request(request)
    start_time = time.time()

    try:
        body = await request.json()
    except Exception as e:
        logger.error("Failed to parse JSON body: %s", e)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    raw_messages = body.get("messages", [])
    stream = body.get("stream", False)
    temperature = body.get("temperature", 0.6)
    max_tokens = body.get("max_tokens", 250)

    requested_model = (body.get("model") or "").strip()
    if not requested_model or requested_model in ("custom-llm", "default", "gpt-4", "gpt-3.5-turbo") or requested_model.startswith("vapi"):
        groq_model = DEFAULT_MODEL
    else:
        groq_model = requested_model

    logger.info("=" * 60)
    logger.info("📞 INCOMING VAPI CALL COMPLETION REQUEST | Model: %s | Stream: %s", groq_model, stream)

    # Prepare messages: inject dynamic real-time system prompt
    current_system_prompt = build_dynamic_system_prompt()
    final_messages: List[Dict[str, str]] = []
    has_system = False

    for msg in raw_messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            final_messages.append({"role": "system", "content": current_system_prompt})
            has_system = True
        else:
            final_messages.append({"role": role, "content": content})

    if not has_system:
        final_messages.insert(0, {"role": "system", "content": current_system_prompt})

    # Log latest user utterance
    if final_messages and final_messages[-1]["role"] == "user":
        logger.info("🗣️ User Utterance: %s", final_messages[-1]["content"])

    if not groq_async_client:
        fallback_err = "معذرت، سرور پر Groq کنفیگریشن نامکمل ہے۔"
        if stream:
            async def err_gen():
                chunk = {
                    "id": f"chatcmpl-err-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{"index": 0, "delta": {"content": fallback_err}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(err_gen(), media_type="text/event-stream")
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY is not configured"})

    # --------------------------------------------------------------------------
    # Generate Completion & Process Any Actions
    # --------------------------------------------------------------------------
    try:
        # Fetch completion from Groq
        completion = await groq_async_client.chat.completions.create(
            model=groq_model,
            messages=final_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )

        raw_reply = completion.choices[0].message.content if completion.choices else ""
        logger.info("🤖 Raw Model Generation: %s", raw_reply)

        # Execute any action tags emitted by the model
        if "[ACTION:" in raw_reply:
            action_result = execute_parsed_action(raw_reply)
            logger.info("Database Action Execution Result: %s", action_result)

        # Clean text for spoken TTS output
        clean_speech_reply = strip_action_tags(raw_reply)
        if not clean_speech_reply:
            clean_speech_reply = "جی فرمائیے، میں آپ کی کیا مدد کر سکتی ہوں؟"

        duration = time.time() - start_time
        logger.info("✅ Generation complete in %.2fs. Spoken Text: %s", duration, clean_speech_reply)
        logger.info("=" * 60)

        # ----------------------------------------------------------------------
        # Stream back to Vapi via Server-Sent Events (SSE)
        # ----------------------------------------------------------------------
        if stream:
            async def event_generator():
                completion_id = f"chatcmpl-{int(time.time())}"
                # Split clean response into small, natural spoken speech chunks
                words = clean_speech_reply.split(" ")
                chunk_size = 3
                for i in range(0, len(words), chunk_size):
                    chunk_text = " ".join(words[i:i + chunk_size])
                    if i + chunk_size < len(words):
                        chunk_text += " "
                    
                    data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": groq_model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk_text},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                # Final chunk
                final_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

        # Non-streaming response
        return {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": groq_model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": clean_speech_reply},
                "finish_reason": "stop"
            }]
        }

    except Exception as e:
        logger.error("❌ Exception during chat completion: %s", e, exc_info=True)
        fallback_msg = "معاف کیجیے گا، تھوڑا سا فنی مسئلہ پیش آیا ہے۔ میں آپ کی کیا مدد کر سکتی ہوں؟"
        if stream:
            async def err_gen():
                chunk = {
                    "id": f"chatcmpl-err-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{"index": 0, "delta": {"content": fallback_msg}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(err_gen(), media_type="text/event-stream")
        return JSONResponse(status_code=500, content={"error": str(e)})

# ==============================================================================
# 8. Vapi Webhook: POST /webhook/vapi
# ==============================================================================

@app.post("/webhook/vapi")
async def vapi_webhook(request: Request):
    """Receives and logs Vapi server events cleanly."""
    verify_vapi_request(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    msg = payload.get("message", {})
    event_type = msg.get("type") or payload.get("type", "unknown")
    call_info = msg.get("call") or payload.get("call") or {}
    call_id = call_info.get("id", "N/A")

    logger.info("🔔 [VAPI WEBHOOK EVENT] Type: %s | Call ID: %s", event_type, call_id)

    if event_type == "transcript":
        role = msg.get("role", "unknown")
        transcript_text = msg.get("transcript", "")
        if msg.get("transcriptType") == "final":
            logger.info("   📝 Final Transcript [%s]: %s", role.upper(), transcript_text)
    elif event_type == "status-update":
        status_val = msg.get("status") or call_info.get("status")
        logger.info("   Status Update -> %s", status_val)
    elif event_type == "end-of-call-report":
        duration = msg.get("durationSeconds", "N/A")
        reason = msg.get("endedReason", "N/A")
        logger.info("   🏁 Call Finished | Duration: %ss | Reason: %s", duration, reason)

    return {"status": "ok", "received": event_type}

# ==============================================================================
# 9. Main Entrypoint
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    print(f"\n🏥 Starting Shifa Care Hospital Voice Agent & Dashboard on http://{host}:{PORT}\n")
    uvicorn.run("main:app", host=host, port=PORT, reload=True)
