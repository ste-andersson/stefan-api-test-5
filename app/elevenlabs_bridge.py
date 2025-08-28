
import asyncio
import base64
import json
import logging
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed

from .config import get_settings
settings = get_settings()

log = logging.getLogger("elevenlabs_bridge")

def build_upstream_url(model_id: str) -> str:
    tmpl = settings.elevenlabs_ws_url_template
    return tmpl.format(MODEL_ID=model_id)

async def stream_tts_to_client(*, client_ws, text: str, model_id: Optional[str], voice_id: Optional[str]) -> int:
    """Open upstream ElevenLabs WS, send text, and stream PCM16k mono bytes to client as binary frames.
    Returns total bytes relayed.
    Sends status JSON to client as needed.
    """
    import ssl
    ssl_context = ssl.create_default_context()
    model = model_id or settings.elevenlabs_model_id
    upstream_url = build_upstream_url(model)

    headers = {}
    if settings.elevenlabs_api_key:
        headers["xi-api-key"] = settings.elevenlabs_api_key

    await client_ws.send_text(json.dumps({"stage": "connecting_upstream", "model": model}))

    total_bytes = 0
    try:
        async with websockets.connect(upstream_url, extra_headers=headers, open_timeout=settings.upstream_connect_timeout_s, ssl=ssl_context) as upstream:
            # INIT per user's spec
            init_msg = {
                "init": True,
                "chunk_length_schedule": list(settings.chunk_length_schedule),
            }
            if voice_id or settings.elevenlabs_voice_id:
                init_msg["voice_id"] = voice_id or settings.elevenlabs_voice_id
            await upstream.send(json.dumps(init_msg))

            # Send the text and trigger generation
            await upstream.send(json.dumps({"text": text, "try_trigger_generation": True}))
            # Flush
            await upstream.send(json.dumps({"text": "", "flush": True}))

            await client_ws.send_text(json.dumps({"stage": "awaiting_audio"}))

            stall_timeout = settings.upstream_stall_timeout_s
            last_data = asyncio.get_event_loop().time()

            while True:
                try:
                    msg = await asyncio.wait_for(upstream.recv(), timeout=stall_timeout)
                except asyncio.TimeoutError:
                    # stall timeout
                    if total_bytes > 0:
                        await client_ws.send_text(json.dumps({"stage": "done", "bytes": total_bytes}))
                    else:
                        await client_ws.send_text(json.dumps({"stage": "error", "message": "Upstream timeout without audio"}))
                    break

                if isinstance(msg, (bytes, bytearray)):
                    buf = bytes(msg)
                    if not buf:
                        continue
                    await client_ws.send_bytes(buf)
                    total_bytes += len(buf)
                    last_data = asyncio.get_event_loop().time()
                    continue

                # JSON/text messages from upstream
                try:
                    data = json.loads(msg)
                except Exception:
                    log.debug("Non-JSON text from upstream: %s", msg)
                    continue

                # Some upstreams send base64 pcm inside JSON
                audio_b64 = data.get("audio") if isinstance(data, dict) else None
                if audio_b64 is not None:
                    if not audio_b64:
                        # ignore null/empty per spec
                        continue
                    try:
                        pcm = base64.b64decode(audio_b64)
                    except Exception:
                        continue
                    if pcm:
                        await client_ws.send_bytes(pcm)
                        total_bytes += len(pcm)
                        last_data = asyncio.get_event_loop().time()
                    continue

                # Forward notable status fields if present (without leaking secrets)
                state = data.get("state") or data.get("status") or data.get("stage")
                if state:
                    await client_ws.send_text(json.dumps({"stage": str(state)}))

            # End while
    except ConnectionClosed:
        log.info("Upstream connection closed.")
    except Exception as e:
        log.exception("Error in upstream relay: %s", e)
        await client_ws.send_text(json.dumps({"stage": "error", "message": str(e)}))

    return total_bytes
