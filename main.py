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
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import AsyncGroq, Groq

import database
import tools
from models import AppointmentCreate, AppointmentReschedule

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
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
VAPI_WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
AGENT_MD_PATH = BASE_DIR / "agent.md"

# ==============================================================================
# 2. System Prompt Loader & Dynamic Context
# ==============================================================================
def resolve_server_base_url(request: Request) -> str:
    """
    Resolves the public base URL for Vapi callbacks (Custom LLM & Webhooks).
    Prioritizes SERVER_URL or NGROK_URL in environment, falls back to x-forwarded headers or request.base_url.
    """
    env_url = (
        os.getenv("SERVER_URL", "").strip()
        or os.getenv("NGROK_URL", "").strip()
        or os.getenv("VITE_NGROK_URL", "").strip()
    )
    if env_url:
        return env_url.rstrip("/")

    # If incoming request is through ngrok/reverse-proxy
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def load_base_system_prompt() -> str:
    """Extracts base system prompt from agent.md."""
    try:
        if AGENT_MD_PATH.exists():
            content = AGENT_MD_PATH.read_text(encoding="utf-8")
            match = re.search(r"```text\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                return match.group(1).strip()
    except Exception as e:
        logger.error("Error reading agent.md: %s", e)
    
    return (
        "تم سٹی ہسپتال کی ہیڈ ریسپشنسٹ عائشہ ہو۔ مریضوں کی کالز پر انتہائی شائستہ اور قدرتی اردو میں رہنمائی کرو۔ "
        "ڈاکٹروں کے اوقات معلوم کر کے اپائنٹمنٹ بک، تبدیل یا منسوخ کرو۔ جوابات 1 سے 2 جملے مختصر رکھو۔"
    )

BASE_SYSTEM_PROMPT = load_base_system_prompt()

def build_dynamic_prompt(caller_phone: Optional[str] = None) -> str:
    """Builds prompt with current date, dynamic slot summary, doctor roster, and caller ID context."""
    base_prompt = load_base_system_prompt()
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    today_day = today.strftime("%A")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    doctors = database.get_all_doctors_with_slots()
    doc_lines = []
    for d in doctors:
        doc_lines.append(
            f"- {d['name']} ({d['specialty']}) | شعبہ: {d['department']} | فیس: Rs. {d['fee_pkr']} | تجربہ: {d['experience_years']} سال"
        )
    doc_text = "\n".join(doc_lines)

    caller_section = ""
    if caller_phone:
        caller_section = f"""
کالر کی تفصیلات (Detected Inbound Caller Details):
- Caller Phone Number: {caller_phone}
- خصوصی ہدایات برائے فون نمبر:
  * کالر کا فون نمبر ({caller_phone}) سسٹم میں پہلے سے موجود ہے۔
  * کالر سے تمام 11 ہندسے دوبارہ مت پوچھیں اور نہ ہی ان سے ہندسہ بہ ہندسہ نمبر لکھوائیں۔
  * نیا اپائنٹمنٹ بک کرتے وقت یا پرانا اپائنٹمنٹ تلاش کرتے وقت صرف شائستگی سے تصدیق کریں: "کیا آپ اپنے موجودہ کال والے نمبر {caller_phone} پر ہی اپائنٹمنٹ بک کروانا چاہتے ہیں یا کوئی اور نمبر دینا چاہتے ہیں؟"
  * اگر کالر رضامندی دے یا کہے کہ اسی نمبر پر، تو `book_appointment` یا `check_appointment` میں patient_phone کے طور پر بلا جھجھک '{caller_phone}' استعمال کریں۔
  * اگر کالر کوئی دوسرا متبادل نمبر بتائے تو وہ نیا نمبر استعمال کریں۔
"""

    return f"""{base_prompt}

حقیقی وقت کا ہسپتال کیلنڈر:
- آج کی تاریخ: {today_str} ({today_day})
- کل کی تاریخ: {tomorrow_str}

ہسپتال کے سپیشلسٹ ڈاکٹرز:
{doc_text}
{caller_section}
ہدایات برائے ٹولز:
- جب مریض کا نام اور فون نمبر (یا موجودہ کال والے نمبر کی تصدیق) حاصل ہو جائے تو `book_appointment` ٹول کال کریں۔
- بکنگ مکمل ہونے کے بعد بکنگ ریفرنس کوڈ (مثلاً APT-1045) ضرور بتائیں۔
"""

# Initialize Groq Clients
groq_async_client: Optional[AsyncGroq] = None
groq_sync_client: Optional[Groq] = None

if GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_your") and not GROQ_API_KEY.startswith("your_"):
    groq_async_client = AsyncGroq(api_key=GROQ_API_KEY)
    groq_sync_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq clients initialized with default model: %s", DEFAULT_MODEL)
else:
    logger.warning("GROQ_API_KEY not configured or placeholder.")

# ==============================================================================
# 3. FastAPI App Setup
# ==============================================================================
app = FastAPI(
    title="City Hospital - Voice Receptionist & Clinical Operations",
    description="Full-stack hospital appointment management system with Groq Agentic Voice Receptionist.",
    version="2.0.0"
)

# CORS Middleware (supports React on localhost:5173 and Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def verify_vapi_request(request: Request) -> None:
    if not VAPI_WEBHOOK_SECRET:
        return
    supplied = request.headers.get("x-vapi-secret", "")
    if not supplied:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
    if not hmac.compare_digest(supplied.encode(), VAPI_WEBHOOK_SECRET.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")

# Mount static assets
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="dist-assets")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def serve_root():
    """Serves the modern React frontend dashboard or fallback static UI."""
    if (FRONTEND_DIST / "index.html").exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    if (STATIC_DIR / "index.html").exists():
        return FileResponse(STATIC_DIR / "index.html")
    return HTMLResponse("<h1>City Hospital System Backend Running</h1>")

# ==============================================================================
# 4. REST API Endpoints for React Frontend
# ==============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "City Hospital System",
        "groq_configured": bool(groq_async_client),
        "groq_model": DEFAULT_MODEL,
        "vapi_configured": bool(VAPI_PUBLIC_KEY and not VAPI_PUBLIC_KEY.startswith("your_")),
        "timestamp": time.time()
    }

@app.get("/api/config")
async def get_config():
    return {
        "vapi_public_key": VAPI_PUBLIC_KEY if not VAPI_PUBLIC_KEY.startswith("your_") else "",
        "vapi_assistant_id": VAPI_ASSISTANT_ID if not VAPI_ASSISTANT_ID.startswith("your_") else "",
        "groq_configured": bool(groq_async_client)
    }

@app.get("/api/stats")
async def get_dashboard_stats():
    """Returns overview counts for the frontend stats bar."""
    return database.get_dashboard_stats()

@app.get("/api/doctors")
async def list_doctors_api(
    specialty: Optional[str] = None,
    date: Optional[str] = None
):
    """
    Returns all doctors along with their grouped available & booked time slots by date.
    """
    return database.get_all_doctors_with_slots(specialty=specialty, target_date=date)

@app.get("/api/appointments")
async def list_appointments_api(
    search: Optional[str] = None,
    doctor_id: Optional[int] = None,
    status: Optional[str] = None,
    date: Optional[str] = None
):
    """
    Returns all booked appointments joined with doctor name, specialty, date, and time slot.
    """
    return database.get_all_appointments(
        search=search,
        doctor_id=doctor_id,
        status=status,
        target_date=date
    )

@app.post("/api/appointments")
async def create_appointment_api(payload: AppointmentCreate):
    """
    Allows manual booking from the React UI.
    """
    # Resolve doctor
    doc = database.find_doctor_by_name(str(payload.doctor_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Doctor not found")

    res = database.tool_book_appointment(
        doctor_name=doc["name"],
        date_str=payload.date or date.today().strftime("%Y-%m-%d"),
        time_slot=payload.time_slot or "10:00 AM",
        patient_name=payload.patient_name,
        patient_phone=payload.patient_phone,
        reason=payload.reason or "Manual Clinic Booking"
    )

    if res.get("status") != "confirmed":
        raise HTTPException(status_code=400, detail=res.get("message", "Booking failed"))

    return res

@app.patch("/api/appointments/{appointment_id}/reschedule")
async def reschedule_appointment_api(appointment_id: int, payload: AppointmentReschedule):
    """
    Allows manual rescheduling from the React UI.
    """
    # Find appointment to get booking reference
    conn = database.get_connection()
    row = conn.execute("SELECT booking_reference FROM appointments WHERE id = ?;", (appointment_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")

    res = database.tool_reschedule_appointment(
        booking_reference=row["booking_reference"],
        new_date=payload.new_date,
        new_time_slot=payload.new_time_slot
    )

    if res.get("status") != "rescheduled":
        raise HTTPException(status_code=400, detail=res.get("message", "Rescheduling failed"))

    return res

@app.delete("/api/appointments/{appointment_id}")
async def cancel_appointment_api(appointment_id: int):
    """
    Allows manual cancellation from the React UI.
    """
    conn = database.get_connection()
    row = conn.execute("SELECT booking_reference FROM appointments WHERE id = ?;", (appointment_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")

    res = database.tool_cancel_appointment(row["booking_reference"])
    if res.get("status") != "cancelled":
        raise HTTPException(status_code=400, detail=res.get("message", "Cancellation failed"))

    return res

# ==============================================================================
# 5. Agentic Custom LLM: POST /chat/completions (Vapi SSE Stream with Tool Calling)
# ==============================================================================

@app.post("/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible /chat/completions endpoint for Vapi's Custom LLM.
    Implements multi-step tool execution loop with Groq, executing database tools
    before streaming the final natural Urdu response back to Vapi via SSE.
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

    # 1. Extract caller's phone number from incoming Vapi request payload
    call_obj = body.get("call") or {}
    customer_obj = call_obj.get("customer") or body.get("customer") or {}
    caller_phone = (
        customer_obj.get("number")
        or body.get("call", {}).get("customer", {}).get("number")
        or body.get("message", {}).get("call", {}).get("customer", {}).get("number")
    )
    if caller_phone:
        logger.info("📞 Inbound PSTN Caller Phone Detected: %s", caller_phone)

    # Ingest dynamic system prompt with caller ID awareness
    current_system_prompt = build_dynamic_prompt(caller_phone=caller_phone)
    conversation: List[Dict[str, Any]] = []
    has_system = False

    for m in raw_messages:
        role = m.get("role")
        content = m.get("content") or ""
        if role == "system":
            conversation.append({"role": "system", "content": current_system_prompt})
            has_system = True
        else:
            conversation.append({"role": role, "content": content})

    if not has_system:
        conversation.insert(0, {"role": "system", "content": current_system_prompt})

    if conversation and conversation[-1]["role"] == "user":
        logger.info("🗣️ Caller Voice Utterance: %s", conversation[-1]["content"])

    if not groq_sync_client:
        err_text = "معذرت، سرور پر Groq API کنفیگر نہیں ہے۔"
        if stream:
            async def err_gen():
                chunk = {
                    "id": f"chatcmpl-err-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{"index": 0, "delta": {"content": err_text}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(err_gen(), media_type="text/event-stream")
        return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY missing"})

    # --------------------------------------------------------------------------
    # Autonomous Tool Execution Loop (up to 4 iterations)
    # --------------------------------------------------------------------------
    final_text_reply = ""
    iteration = 0
    max_tool_iterations = 4

    try:
        while iteration < max_tool_iterations:
            iteration += 1
            response = groq_sync_client.chat.completions.create(
                model=groq_model,
                messages=conversation,
                tools=tools.GROQ_TOOLS,
                tool_choice="auto",
                temperature=temperature,
                max_tokens=max_tokens
            )

            choice = response.choices[0]
            msg = choice.message

            # Check if Groq invoked any tools
            if msg.tool_calls:
                # Add assistant message with tool calls to conversation
                conversation.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                })

                # Execute each tool in database
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except Exception:
                        fn_args = {}

                    logger.info("⚡ Agent Executing Tool: %s with args: %s", fn_name, fn_args)
                    tool_output = tools.execute_tool(fn_name, fn_args)
                    logger.info("   -> Tool Result: %s", json.dumps(tool_output, ensure_ascii=False)[:180])

                    conversation.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_output, ensure_ascii=False)
                    })

                # Loop continues to generate the spoken reply with tool results
                continue

            else:
                # Model returned final conversational text
                final_text_reply = msg.content or ""
                break

    except Exception as e:
        logger.error("Error in Groq tool loop: %s. Falling back to direct generation.", e)
        # Fallback to direct chat completion without tools if model had tool issues
        try:
            fb = groq_sync_client.chat.completions.create(
                model=groq_model,
                messages=conversation,
                temperature=temperature,
                max_tokens=max_tokens
            )
            final_text_reply = fb.choices[0].message.content or ""
        except Exception as e2:
            logger.error("Fallback generation failed: %s", e2)
            final_text_reply = "جی فرمائیے، میں سٹی ہسپتال سے عائشہ ہوں، میں آپ کی کیا مدد کر سکتی ہوں؟"

    if not final_text_reply:
        final_text_reply = "جی بالکل، فرمائیے میں آپ کی مزید کیا مدد کر سکتی ہوں؟"

    duration = time.time() - start_time
    logger.info("✅ Generation Finished in %.2fs (Turn %d)", duration, iteration)
    logger.info("🤖 Final Spoken Urdu Reply: %s", final_text_reply)
    logger.info("=" * 60)

    # --------------------------------------------------------------------------
    # Stream Response to Vapi via Server-Sent Events (SSE)
    # --------------------------------------------------------------------------
    if stream:
        async def event_generator():
            completion_id = f"chatcmpl-{int(time.time())}"
            words = final_text_reply.split(" ")
            chunk_size = 3

            for i in range(0, len(words), chunk_size):
                chunk_slice = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk_slice += " "

                chunk_obj = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk_slice},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(chunk_obj, ensure_ascii=False)}\n\n"

            # Stop chunk
            stop_chunk = {
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
            yield f"data: {json.dumps(stop_chunk, ensure_ascii=False)}\n\n"
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

    # Non-streaming fallback
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": groq_model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": final_text_reply},
            "finish_reason": "stop"
        }]
    }

# ==============================================================================
# 6. Vapi Webhook: POST /webhook/vapi
# ==============================================================================
@app.post("/webhook/vapi")
async def vapi_webhook(request: Request):
    """
    Handles Vapi webhook events including dynamic assistant configuration for
    inbound phone calls (assistant-request) and call lifecycle logs.
    """
    verify_vapi_request(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    msg = payload.get("message", {})
    event_type = msg.get("type") or payload.get("type", "unknown")
    call_obj = msg.get("call") or payload.get("call") or {}
    call_id = call_obj.get("id", "N/A")
    caller_phone = (
        call_obj.get("customer", {}).get("number")
        or payload.get("customer", {}).get("number")
        or msg.get("customer", {}).get("number")
    )

    logger.info("🔔 [VAPI WEBHOOK EVENT] Type: %s | Call ID: %s | Caller: %s", event_type, call_id, caller_phone or "N/A")

    # 1. Dynamic Assistant Request: Vapi phone number routed via Server URL
    if event_type == "assistant-request":
        base_url = resolve_server_base_url(request)
        chat_completions_url = f"{base_url}/chat/completions"
        webhook_url = f"{base_url}/webhook/vapi"

        logger.info("⚡ Returning dynamic Assistant config for inbound PSTN call. Chat URL: %s", chat_completions_url)

        return {
            "assistant": {
                "name": "Shifa Care Urdu Receptionist",
                "firstMessage": "السلام علیکم! شفا کیئر ہسپتال میں خوش آمدید، میں عائشہ ہوں۔ فرمائیے میں آپ کی کیا مدد کر سکتی ہوں؟",
                "transcriber": {
                    "provider": "deepgram",
                    "model": "nova-3",
                    "language": "ur"
                },
                "model": {
                    "provider": "custom-llm",
                    "url": chat_completions_url,
                    "headers": {
                        "ngrok-skip-browser-warning": "true"
                    }
                },
                "voice": {
                    "provider": "11labs",
                    "voiceId": "21m00Tcm4TlvDq8ikWAM",
                    "model": "eleven_multilingual_v2"
                },
                "serverUrl": webhook_url,
                "server": {
                    "url": webhook_url,
                    "timeoutSeconds": 20,
                    "headers": {
                        "ngrok-skip-browser-warning": "true"
                    }
                }
            }
        }

    # 2. Call lifecycle & transcripts logging
    if event_type == "transcript" and msg.get("transcriptType") == "final":
        logger.info("   📝 Final Transcript [%s]: %s", msg.get("role", "user").upper(), msg.get("transcript", ""))
    elif event_type == "status-update":
        logger.info("   Status Update -> %s", msg.get("status"))

    return {"status": "ok", "received": event_type}


@app.post("/")
async def root_webhook_fallback(request: Request):
    """Fallback handler in case Vapi phone number Server URL is set to root / instead of /webhook/vapi."""
    return await vapi_webhook(request)

# ==============================================================================
# 7. Main Entrypoint
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    print(f"\n🏥 Starting Shifa Care Hospital Backend on http://{host}:{PORT}\n")
    uvicorn.run("main:app", host=host, port=PORT, reload=True)
