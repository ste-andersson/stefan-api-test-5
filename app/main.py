
import json
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.websockets import WebSocketState

from .config import get_settings
from .schemas import TTSRequest
from .elevenlabs_bridge import stream_tts_to_client

settings = get_settings()

log = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

# CORS: allow local dev and the Lovable/Render hostnames
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://stefan-api-test-5.lovable.app",
    "https://stefan-api-test-5.onrender.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/", response_class=PlainTextResponse)
async def root():
    return "ok"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/config.json")
async def config(request: Request):
    # Derive ws URL from current request host/scheme
    scheme = request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    ws_scheme = "wss" if scheme == "https" else "ws"
    return JSONResponse({
        "backend_http": f"{scheme}://{host}",
        "backend_ws": f"{ws_scheme}://{host}/ws/tts",
        "format": "pcm_s16le_16000_mono",
    })

@app.websocket("/ws/tts")
async def ws_tts(ws: WebSocket):
    await ws.accept()
    try:
        # Expect a JSON message first: { text, model_id?, voice_id? }
        first = await ws.receive_text()
        try:
            payload = json.loads(first)
        except Exception:
            await ws.send_text(json.dumps({"stage": "error", "message": "First message must be JSON"}))
            await ws.close()
            return

        req = TTSRequest(**payload)
        # relay to elevenlabs
        total = await stream_tts_to_client(
            client_ws=ws,
            text=req.text,
            model_id=req.model_id,
            voice_id=req.voice_id or settings.elevenlabs_voice_id,
        )
        if ws.application_state == WebSocketState.CONNECTED:
            # Per spec: if bytes>0 => stage:done; else => error (handled in bridge too)
            if total > 0:
                await ws.send_text(json.dumps({"stage": "done", "bytes": total}))
            else:
                await ws.send_text(json.dumps({"stage": "error", "message": "No audio produced"}))
            await ws.close()
    except WebSocketDisconnect:
        log.info("Client disconnected.")
    except Exception as e:
        if ws.application_state == WebSocketState.CONNECTED:
            await ws.send_text(json.dumps({"stage": "error", "message": str(e)}))
            await ws.close()

