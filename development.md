# Development & Testing Guide (Phase 1)

This guide provides step-by-step instructions to set up, run, and test **Phase 1 (Calling & Voice Pipeline Foundation)** of the Urdu Hospital Receptionist Voice Agent.

---

## 1. Prerequisites
- **Python 3.10+**
- **Groq API Key**: Free/instant access at [console.groq.com](https://console.groq.com/keys)
- **Vapi Account**: Sign up at [dashboard.vapi.ai](https://dashboard.vapi.ai)
- **ngrok**: Installed and authenticated ([ngrok.com](https://ngrok.com))

---

## 2. Virtual Environment Setup & Dependencies

### Windows (PowerShell or Command Prompt):
```powershell
# 1. Create the virtual environment
python -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\activate

# 3. Upgrade pip and install requirements
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux:
```bash
# 1. Create the virtual environment
python3 -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Upgrade pip and install requirements
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Environment Configuration (`.env`)

Copy `.env.example` to `.env` if not already done:
```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```env
# Groq API Key (powers llama-3.3-70b-versatile)
GROQ_API_KEY=gsk_your_actual_groq_key_here

# Vapi Credentials
VAPI_PUBLIC_KEY=your_vapi_public_key_here
VAPI_PRIVATE_KEY=your_vapi_private_key_here

# Optional: Pre-configured Assistant ID from Vapi Dashboard
VAPI_ASSISTANT_ID=your_vapi_assistant_id_here

# Server Settings
PORT=8000
HOST=0.0.0.0

# Recommended: shared secret Vapi must send on /chat/completions and /webhook/vapi
VAPI_WEBHOOK_SECRET=change_me_to_a_long_random_string
```

---

## 4. Run the FastAPI Server

Start the local server with auto-reload:
```bash
uvicorn main:app --reload --port 8000
```
Verify the server is healthy by visiting:
- UI Simulator: [http://localhost:8000](http://localhost:8000)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 5. Expose Local Port 8000 via ngrok

Open a new terminal window and run:
```bash
ngrok http 8000
```
Copy your forwarding HTTPS URL (e.g., `https://abcdef1234.ngrok-free.app`).

> **Note:** Whenever you restart ngrok, update the URL in your Vapi configuration.

---

## 6. Configure Vapi Dashboard (Custom LLM)

To let Vapi stream audio while delegating conversation directly to our local FastAPI Groq backend:

1. Go to **[Vapi Dashboard -> Assistants](https://dashboard.vapi.ai/assistants)**.
2. Click **Create Assistant** (Select "Blank Template").
3. **Model Configuration:**
   - **Provider:** Select `Custom LLM`.
   - **URL:** Paste your ngrok endpoint:  
     `https://<your-ngrok-subdomain>.ngrok-free.app/chat/completions`
   - **Model Name:** Enter `llama-3.3-70b-versatile`.
   - **Temperature:** `0.6`
   - **Max Tokens:** `250`
4. **Transcriber Configuration (STT):**
   - **Provider:** `Deepgram`
   - **Model:** `nova-3` (**not** `nova-2` — nova-2 has no Urdu support and causes the agent to keep saying "can you repeat?")
   - **Language:** `ur` (Urdu)
5. **Voice Configuration (TTS):**
   - Select an expressive natural voice provider (e.g. `Cartesia` or `ElevenLabs`).
   - Pick a smooth, calm female voice suitable for customer support.
6. **First Message:**
   - Set to:  
     `السلام علیکم! شفا کیئر ہسپتال میں خوش آمدید، میں عائشہ ہوں، فرمائیے میں آپ کی کیا مدد کر سکتی ہوں؟`
7. **Server URL (Webhook for lifecycle events):**
   - Go to assistant settings or account settings and set Server URL to:  
     `https://<your-ngrok-subdomain>.ngrok-free.app/webhook/vapi`
8. Click **Save** and copy your **Assistant ID** from the top of the page.

---

## 7. Test in the Local Web Simulator

1. Open [http://localhost:8000](http://localhost:8000) in Google Chrome or any modern browser.
2. Ensure your **Vapi Public Key** and **Assistant ID** are populated (the backend auto-fills them if present in `.env`).
3. Click **Start Urdu Call**.
4. Allow microphone access when prompted.
5. Speak in conversational Urdu, for example:
   - *"السلام علیکم، مجھے او پی ڈی کے اوقات معلوم کرنے ہیں"*
   - *"کیا کل دل کے ڈاکٹر دستیاب ہیں؟"*
   - *"ہسپتال کہاں واقع ہے؟"*
6. Observe:
   - Live Urdu audio transcription appears in the transcript panel.
   - The terminal shows real-time Groq SSE stream generation and latency metrics.
   - The assistant replies smoothly in natural Urdu speech.
7. Click **End Call** when finished.

---

## 8. Troubleshooting

**Agent keeps asking "can you repeat?" / ignores what I say**
- The speech-to-text isn't understanding Urdu. Use Deepgram `nova-3` with language `ur` (nova-2 does not support Urdu). The simulator's *Speech Recognition* dropdown overrides the dashboard setting; switch to *ElevenLabs Scribe* if Deepgram still struggles.
- Check the terminal log: the `USER:` lines show what the STT actually heard. Empty or garbled lines mean an STT problem, not an LLM problem.
- Make sure the browser has microphone permission and the correct input device is selected.

**401 Unauthorized in the logs**
- `VAPI_WEBHOOK_SECRET` is set in `.env` but Vapi isn't sending it. Configure the same secret in Vapi, or leave the variable empty for local testing.
