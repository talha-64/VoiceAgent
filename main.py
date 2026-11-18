import os
import re
import hmac
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from groq import AsyncGroq

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

# Optional shared secret. When set, /chat/completions and /webhook/vapi reject requests
# that don't send it (as an `X-Vapi-Secret` header or `Authorization: Bearer <secret>`).
VAPI_WEBHOOK_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()

# Origins allowed to call the API from a browser. The simulator is served by this app
# (same-origin), so the defaults are enough for local use.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if o.strip()
]

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
AGENT_MD_PATH = BASE_DIR / "agent.md"

# ==============================================================================
# 2. System Prompt Loader (from agent.md)
# ==============================================================================
DEFAULT_URDU_SYSTEM_PROMPT = (
    "تم شفا کیئر ہسپتال (Shifa Care Hospital) کی استقبالیہ آفیسر (Receptionist) عائشہ ہو۔ "
    "تمہارا کام آنے والے مریضوں اور تیمارداروں کی فون کالز پر انتہائی شائستہ، خوش اخلاق اور مددگار انداز میں رہنمائی کرنا ہے۔\n\n"
    "اہم ترین ہدایات:\n"
    "1. زبان: صرف اور صرف روزمرہ کی آسان اور رواں اردو (Urdu) میں بات کرو۔ کتابی یا مصنوعی الفاظ سے گریز کرو۔\n"
    "2. انداز: انتہائی پرسکون، باادب اور ہمدردانہ انداز رکھو۔ گفتگو میں فطری الفاظ جیسے \"جی بالکل\"، \"جی ضرور\"، \"جی فرمائیے\" کا موقع کی مناسبت سے استعمال کرو۔\n"
    "3. جواب کا دورانیہ: چونکہ یہ فون کال ہے، اس لیے تمہارا جواب انتہائی مختصر (صرف 1 سے 2 جملے) ہونا چاہیے۔ کبھی بھی لمبی تقریر یا پیراگراف مت بولو۔\n"
    "4. ایک وقت میں ایک بات: کالر سے ایک وقت میں صرف ایک سوال پوچھو تاکہ وہ آسانی سے جواب دے سکے۔\n"
    "5. اگر آواز صاف نہ ہو: صرف تب جب کالر کا متن خالی ہو یا بالکل بے معنی ہو، شائستگی سے دوبارہ کہنے کی درخواست کرو۔ اگر بات تھوڑی بھی سمجھ آ رہی ہو تو دوبارہ پوچھنے کے بجائے اسی کا جواب دو۔ دوبارہ کہنے کا جملہ: \"معذرت چاہتی ہوں، آپ کی آواز کٹ رہی تھی، کیا آپ دوبارہ دہرا سکتے ہیں؟\"\n"
    "6. ہسپتال کی بنیادی معلومات:\n"
    "   - او پی ڈی (OPD) کے اوقات: صبح 8:00 بجے سے رات 10:00 بجے تک۔\n"
    "   - ایمرجنسی سروس: 24 گھنٹے کھلی رہتی ہے۔\n"
    "   - شعبہ جات: دل کے امراض (Cardiology)، بچوں کے امراض (Pediatrics)، ہڈیوں کے امراض (Orthopedics)، اور جنرل فزیشن۔\n"
    "7. صرف اردو رسم الخط میں جواب دو۔ کوئی انگریزی جملے شامل نہ کرو تاوقتیکہ کوئی طبی اصطلاح لازمی ہو۔"
)

def load_system_prompt() -> str:
    """Extracts the system prompt from agent.md or falls back to default."""
    try:
        if AGENT_MD_PATH.exists():
            content = AGENT_MD_PATH.read_text(encoding="utf-8")
            match = re.search(r"```text\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                extracted = match.group(1).strip()
                logger.info("Successfully loaded Urdu system prompt from agent.md (%d characters)", len(extracted))
                return extracted
            else:
                logger.warning("Section 5 ```text code block not found in agent.md. Using default prompt.")
    except Exception as e:
        logger.error("Error reading agent.md: %s. Using default fallback prompt.", e)
    return DEFAULT_URDU_SYSTEM_PROMPT

SYSTEM_PROMPT = load_system_prompt()

# Initialize Groq Client
groq_client: Optional[AsyncGroq] = None
if GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_your") and not GROQ_API_KEY.startswith("your_"):
    groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    logger.info("Groq Async client initialized successfully with model '%s'", DEFAULT_MODEL)
else:
    logger.warning("GROQ_API_KEY is not set or contains placeholder text. Please update your .env file.")

# ==============================================================================
# 3. FastAPI App Setup
# ==============================================================================
app = FastAPI(
    title="Hospital Voice Agent (Urdu Receptionist - Phase 1)",
    description="Real-time calling & voice pipeline using Vapi Custom LLM, Groq Llama 3.3, and Deepgram STT.",
    version="1.0.0"
)

# CORS middleware for local web testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

if not VAPI_WEBHOOK_SECRET:
    logger.warning(
        "VAPI_WEBHOOK_SECRET is not set: /chat/completions and /webhook/vapi accept any caller. "
        "Set it in .env before exposing this server publicly."
    )

def verify_vapi_request(request: Request) -> None:
    """Rejects requests without the shared secret. Only enforced when VAPI_WEBHOOK_SECRET is set."""
    if not VAPI_WEBHOOK_SECRET:
        return
    supplied = request.headers.get("x-vapi-secret", "")
    if not supplied:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            supplied = auth[7:].strip()
    if not hmac.compare_digest(supplied.encode(), VAPI_WEBHOOK_SECRET.encode()):
        logger.warning("Rejected request to %s: missing or invalid secret", request.url.path)
        raise HTTPException(status_code=401, detail="Unauthorized")

# Mount static folder
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ==============================================================================
# 4. Pydantic Models for OpenAI-Compatible Chat Completions
# ==============================================================================
class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = ""

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = DEFAULT_MODEL
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.6
    max_tokens: Optional[int] = 250
    call: Optional[Dict[str, Any]] = None  # Injected by Vapi when calling Custom LLM

# ==============================================================================
# 5. Core Endpoints
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def serve_home():
    """Serves the Vapi Web Call Test Simulator UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Hospital Urdu Voice Agent Backend Running</h1><p>index.html not found in static/</p>")

@app.get("/health")
async def health_check():
    """Health check endpoint displaying configuration status."""
    return {
        "status": "healthy",
        "phase": 1,
        "service": "Urdu Hospital Receptionist Voice Agent",
        "groq_configured": bool(groq_client),
        "groq_model": DEFAULT_MODEL,
        "vapi_configured": bool(VAPI_PUBLIC_KEY and not VAPI_PUBLIC_KEY.startswith("your_")),
        "prompt_length": len(SYSTEM_PROMPT),
        "timestamp": time.time()
    }

@app.get("/api/config")
async def get_config():
    """Provides public configuration values to the frontend simulator."""
    return {
        "vapi_public_key": VAPI_PUBLIC_KEY if not VAPI_PUBLIC_KEY.startswith("your_") else "",
        "vapi_assistant_id": VAPI_ASSISTANT_ID if not VAPI_ASSISTANT_ID.startswith("your_") else "",
        "groq_configured": bool(groq_client)
    }

# ==============================================================================
# 6. Vapi Custom LLM: POST /chat/completions (OpenAI Compatible)
# ==============================================================================
@app.post("/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible streaming chat completions endpoint called by Vapi's Custom LLM.
    Streams Server-Sent Events (SSE) back to Vapi in real time.
    """
    start_time = time.time()
    
    verify_vapi_request(request)

    # Parse raw JSON body
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
    
    # Determine the Groq model to use (fallback to DEFAULT_MODEL if generic or not specified)
    if not requested_model or requested_model in ("custom-llm", "default", "gpt-4", "gpt-3.5-turbo") or requested_model.startswith("vapi"):
        groq_model = DEFAULT_MODEL
    else:
        groq_model = requested_model

    logger.info("=" * 60)
    logger.info("📞 INCOMING VAPI CUSTOM LLM REQUEST")
    logger.info("Model: %s | Stream: %s | Message Count: %d", groq_model, stream, len(raw_messages))

    # Log incoming conversation turns for debugging
    for idx, msg in enumerate(raw_messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Truncate if too long
        preview = (content[:120] + "...") if len(content) > 120 else content
        logger.info("  [%d] %s: %s", idx, role.upper(), preview)

    # Verify Groq client
    if not groq_client:
        logger.error("GROQ_API_KEY is not configured on the backend.")
        error_msg = "معذرت، سرور پر Groq API Key کی سیٹنگ مکمل نہیں ہے۔ برائے مہربانی ایڈمنسٹریٹر سے رابطہ کریں۔"
        if stream:
            async def error_stream():
                chunk_id = f"chatcmpl-err-{int(time.time())}"
                data = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{"index": 0, "delta": {"content": error_msg}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")
        else:
            return JSONResponse(status_code=500, content={"error": "GROQ_API_KEY is not configured"})

    # Prepare messages: enforce the Urdu Hospital Receptionist system prompt at index 0
    final_messages: List[Dict[str, str]] = []
    has_system = False
    
    for msg in raw_messages:
        role = msg.get("role")
        content = msg.get("content") or ""
        if role == "system":
            # Override or prepend our Urdu persona instructions
            final_messages.append({"role": "system", "content": SYSTEM_PROMPT})
            has_system = True
        else:
            final_messages.append({"role": role, "content": content})

    if not has_system:
        final_messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})

    # --------------------------------------------------------------------------
    # Streaming Response (Server-Sent Events)
    # --------------------------------------------------------------------------
    if stream:
        async def event_generator():
            accumulated_text = []
            chunk_count = 0
            try:
                groq_stream = await groq_client.chat.completions.create(
                    model=groq_model,
                    messages=final_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

                async for chunk in groq_stream:
                    chunk_count += 1
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        accumulated_text.append(delta.content)
                    
                    # Yield standard OpenAI chunk JSON
                    chunk_json = chunk.model_dump_json()
                    yield f"data: {chunk_json}\n\n"

                yield "data: [DONE]\n\n"

                duration = time.time() - start_time
                full_reply = "".join(accumulated_text)
                logger.info("✅ STREAM COMPLETED in %.2fs (%d chunks)", duration, chunk_count)
                logger.info("🤖 Generated Urdu Response: %s", full_reply)
                logger.info("=" * 60)

            except Exception as e:
                logger.error("❌ Exception during Groq streaming: %s", e, exc_info=True)
                err_chunk = {
                    "id": f"chatcmpl-err-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": groq_model,
                    "choices": [{"index": 0, "delta": {"content": "معاف کیجیے گا، تھوڑا سا فنی مسئلہ پیش آیا ہے۔"}, "finish_reason": "stop"}]
                }
                yield f"data: {json.dumps(err_chunk, ensure_ascii=False)}\n\n"
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

    # --------------------------------------------------------------------------
    # Non-Streaming Fallback
    # --------------------------------------------------------------------------
    try:
        completion = await groq_client.chat.completions.create(
            model=groq_model,
            messages=final_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        duration = time.time() - start_time
        reply_text = completion.choices[0].message.content if completion.choices else ""
        logger.info("✅ NON-STREAM COMPLETED in %.2fs", duration)
        logger.info("🤖 Generated Urdu Response: %s", reply_text)
        logger.info("=" * 60)
        return completion.model_dump()
    except Exception as e:
        logger.error("❌ Non-streaming Groq call failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# 7. Vapi Webhook: POST /webhook/vapi
# ==============================================================================
@app.post("/webhook/vapi")
async def vapi_webhook(request: Request):
    """
    Receives and logs Vapi server events (status-update, transcript, end-of-call-report).
    Useful for debugging audio latency, speech recognition errors, and call termination reasons.
    """
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
    
    if event_type == "status-update":
        status_val = msg.get("status") or call_info.get("status")
        logger.info("   Status Update -> %s", status_val)
    elif event_type == "transcript":
        role = msg.get("role", "unknown")
        transcript_text = msg.get("transcript", "")
        transcript_type = msg.get("transcriptType", "partial")
        if transcript_type == "final":
            logger.info("   📝 Final Transcript [%s]: %s", role.upper(), transcript_text)
    elif event_type == "end-of-call-report":
        ended_reason = msg.get("endedReason", "unspecified")
        duration_seconds = msg.get("durationSeconds", "N/A")
        cost = msg.get("cost", "N/A")
        logger.info("   🏁 Call Finished | Reason: %s | Duration: %ss | Cost: $%s", ended_reason, duration_seconds, cost)
    else:
        # Pretty print other events for debugging
        logger.info("   Payload summary: %s", json.dumps(payload, ensure_ascii=False)[:300])

    return {"status": "ok", "received": event_type}

# ==============================================================================
# 8. Main Entrypoint
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    print(f"\n🏥 Starting Shifa Care Hospital Urdu Receptionist on http://{host}:{PORT}\n")
    uvicorn.run("main:app", host=host, port=PORT, reload=True)

