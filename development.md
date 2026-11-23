# Development & Testing Guide (Phase 2)

This guide provides step-by-step instructions to set up, run, and test **Phase 2 (Full-Stack Hospital Operations & Agentic Urdu Voice Receptionist)**.

---

## 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+ & npm**
- **Groq API Key**: Free/instant access at [console.groq.com](https://console.groq.com/keys)
- **Vapi Account**: Sign up at [dashboard.vapi.ai](https://dashboard.vapi.ai)
- **ngrok**: Installed and authenticated ([ngrok.com](https://ngrok.com))

---

## 2. Setup & Installation

### Backend Setup:
```powershell
# 1. Activate Python virtual environment
.\.venv\Scripts\activate

# 2. Install dependencies (if not already installed)
pip install -r requirements.txt
```

### Frontend Setup:
```powershell
# 1. Navigate to frontend folder
cd frontend

# 2. Install React dependencies
npm install

# 3. Build production bundle (or run Vite dev server)
npm run build
```

---

## 3. Environment Configuration

### Root `.env` (FastAPI backend):
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
VAPI_PUBLIC_KEY=your_vapi_public_key_here
VAPI_PRIVATE_KEY=your_vapi_private_key_here
VAPI_ASSISTANT_ID=your_vapi_assistant_id_here
PORT=8000
HOST=0.0.0.0
```

### Frontend `frontend/.env`:
```env
VITE_VAPI_PUBLIC_KEY=your_vapi_public_key_here
VITE_VAPI_ASSISTANT_ID=your_vapi_assistant_id_here
VITE_NGROK_URL=https://your-active-subdomain.ngrok-free.dev
```

---

## 4. Running the System

You have two options for running the project:

### Option A: Unified FastAPI Production Mode (Recommended)
FastAPI serves both the REST API endpoints, the SSE streaming Custom LLM, and the compiled React frontend directly:

```powershell
# In root directory:
.\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser!

### Option B: React Vite Dev Server (Hot-Reloading UI)
Run both backend and frontend separately:

1. **Terminal 1 (Backend):**
   ```powershell
   .\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

2. **Terminal 2 (Frontend):**
   ```powershell
   cd frontend
   npm run dev
   ```
Open **[http://localhost:5173](http://localhost:5173)** in your browser. (All API calls to `/api` and `/chat/completions` proxy automatically to port 8000).

3. **Terminal 3 (ngrok for Voice Calls):**
   ```powershell
   ngrok http 8000
   ```
   Ensure your active ngrok URL matches `VITE_NGROK_URL` in `frontend/.env` or in the call drawer.

---

## 5. Live Features to Test

1. **Doctors & Slots Tab:**
   - Filter by specialty (*Cardiology, Dermatology, Pediatrics, Orthopedics, General Physician*).
   - Select dates (*Today, Tomorrow, +2 Days, +3 Days*).
   - Click any green **Available Slot** chip to launch the instant booking modal.
   - Watch slots switch between available and booked in real time (3-second auto-sync).

2. **Appointments Ledger Tab:**
   - Search by Patient Name, Phone, or Booking Reference (`APT-XXXX`).
   - Filter by Doctor or Booking Status (*Confirmed, Cancelled*).
   - Click **Reschedule** on any booking to assign a new date/slot.
   - Click **Cancel** to immediately release the slot back into the available pool.

3. **Urdu AI Voice Receptionist (Persistent Call Drawer):**
   - Click **Call Urdu Agent** at top-right to open the live call drawer.
   - Click **Start Call** to test conversational Urdu appointment booking:
     - *"السلام علیکم، مجھے جلد کے ڈاکٹر کو دکھانا ہے"* (Dr. Bilal Ahmed - Dermatologist)
     - *"ڈاکٹر بلال کے پاس کل کیا وقت دستیاب ہے؟"* (Checks live SQLite slots)
     - *"میرا نام علی ہے، 10:30 بجے بک کر دیں"* (Confirms details & generates `APT-XXXX`)
   - Notice the Doctors and Appointments ledger updates on screen live while you speak!

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
