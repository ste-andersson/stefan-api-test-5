
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.websockets import WebSocketState

from .config import get_settings
from .schemas import TTSRequest
from .elevenlabs_bridge import stream_tts_to_client

settings = get_settings()
log = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

# CORS: tillåt *.lovable.app, din Render-domän och localhost (ingen credentials krävs)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https://([a-z0-9-]+\.)*lovable\.app$|^https://stefan-api-test-5\.onrender\.com$|^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=PlainTextResponse)
async def root():
    return "ok"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/config.json")
async def config(request: Request):
    scheme = request.url.scheme
    host = request.headers.get("x-forwarded-host") or request.url.netloc
    ws_scheme = "wss" if scheme == "https" else "ws"
    resp = JSONResponse({
        "backend_http": f"{scheme}://{host}",
        "backend_ws": f"{ws_scheme}://{host}/ws/tts",
        "format": "pcm_s16le_16000_mono",
    })
    # Extra försäkring för CORS på just denna route
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.websocket("/ws/tts")
async def ws_tts(ws: WebSocket):
    await ws.accept()
    try:
        first = await ws.receive_text()
        try:
            payload = json.loads(first)
        except Exception:
            await ws.send_text(json.dumps({"stage": "error", "message": "First message must be JSON"}))
            await ws.close()
            return

        req = TTSRequest(**payload)
        total = await stream_tts_to_client(
            client_ws=ws,
            text=req.text,
            model_id=req.model_id,
            voice_id=req.voice_id or settings.elevenlabs_voice_id,
        )
        if ws.application_state == WebSocketState.CONNECTED:
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
