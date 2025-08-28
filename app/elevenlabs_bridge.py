
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
    return settings.elevenlabs_ws_url_template.format(MODEL_ID=model_id)


async def stream_tts_to_client(*, client_ws, text: str, model_id: Optional[str], voice_id: Optional[str]) -> int:
    import ssl
    ssl_context = ssl.create_default_context()
    model = model_id or settings.elevenlabs_model_id
    upstream_url = build_upstream_url(model)

    # Prepare two auth header strategies (some envs/versions accept only one)
    key = settings.elevenlabs_api_key
    auth_strategies = []
    if key:
        auth_strategies.append({"xi-api-key": key})
        auth_strategies.append({"Authorization": f"Bearer {key}"})
    else:
        await client_ws.send_text(json.dumps({"stage": "error", "message": "ELEVENLABS_API_KEY saknas"}))
        return 0

    await client_ws.send_text(json.dumps({"stage": "connecting_upstream", "model": model}))

    total_bytes = 0
    last_error: str | None = None

    for headers in auth_strategies:
        try:
            async with websockets.connect(upstream_url, extra_headers=headers, open_timeout=settings.upstream_connect_timeout_s, ssl=ssl_context) as upstream:
                init_msg = {"init": True, "chunk_length_schedule": list(settings.chunk_length_schedule)}
                if voice_id or settings.elevenlabs_voice_id:
                    init_msg["voice_id"] = voice_id or settings.elevenlabs_voice_id
                await upstream.send(json.dumps(init_msg))

                await upstream.send(json.dumps({"text": text, "try_trigger_generation": True}))
                await upstream.send(json.dumps({"text": "", "flush": True}))

                await client_ws.send_text(json.dumps({"stage": "awaiting_audio"}))

                stall_timeout = settings.upstream_stall_timeout_s
                while True:
                    try:
                        msg = await asyncio.wait_for(upstream.recv(), timeout=stall_timeout)
                    except asyncio.TimeoutError:
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
                        continue

                    try:
                        data = json.loads(msg)
                    except Exception:
                        continue

                    audio_b64 = data.get("audio") if isinstance(data, dict) else None
                    if audio_b64 is not None:
                        if not audio_b64:
                            continue
                        try:
                            pcm = base64.b64decode(audio_b64)
                        except Exception:
                            continue
                        if pcm:
                            await client_ws.send_bytes(pcm)
                            total_bytes += len(pcm)
                        continue

                    state = (data.get("state") or data.get("status") or data.get("stage")) if isinstance(data, dict) else None
                    if state:
                        await client_ws.send_text(json.dumps({"stage": str(state)}))

                # success path
                return total_bytes

        except websockets.InvalidStatusCode as e:
            # Handshake rejected with HTTP status
            last_error = f"Upstream rejected WebSocket (HTTP {getattr(e, 'status_code', '???')}) with headers {list(headers.keys())}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    # If we reach here, all auth strategies failed
    await client_ws.send_text(json.dumps({"stage": "error", "message": last_error or "Unknown upstream error"}))
    return total_bytes
