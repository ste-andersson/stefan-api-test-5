
# stefan-api-test-5 — Backend (FastAPI + ElevenLabs TTS)

Låg-latens TTS via WebSocket. **Audio out:** PCM s16le, 16 kHz, mono.  
**WS ut:** binära frames = ljud, text/JSON = status.

## Endpoints

- `GET /` → "ok"
- `GET /health` → `{status:"ok"}`
- `GET /config.json` → `{ backend_http, backend_ws, format }`
- `WS /ws/tts` → Skicka `{text, model_id?, voice_id?}` som första meddelande (JSON). Binära frames kommer tillbaka som PCM s16le 16 kHz. Status skickas som JSON.

### WS-protokoll (server → klient)
- Binära WS-frames: rå PCM 16 kHz mono, **Int16 LE**
- Text/JSON:
  - `{"stage": "connecting_upstream" | "awaiting_audio" | "done" | "error" | ...}`
  - På timeout: om bytes>0 → `stage=done`, annars `stage=error`.

### Upstream (server → ElevenLabs)
Använder `wss://.../stream-input?model_id={MODEL_ID}&output_format=pcm_16000&auto_mode=true`.
Skickar i tur och ordning:
1. `{"init": true, "chunk_length_schedule": [30,60,100], "voice_id": <valfritt>}`
2. `{"text": "<TEXT>", "try_trigger_generation": true}`
3. `{"text": "", "flush": true}`

JSON-svar från ElevenLabs kan ibland innehålla `audio` som base64; `null` eller tomt ignoreras.

## Kör lokalt

```bash
make venv
make install
export ELEVENLABS_API_KEY=sk-... # krävs
make dev
```
Testa TTS och skriv till WAV:
```bash
make test-client TEXT="Hej världen!"
open out.wav  # macOS t.ex.
```

## Deploy (Render)
- Lägg till **Environment Variable**: `ELEVENLABS_API_KEY`.
- (Valfritt) `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID`.
- Använd `render.yaml` för auto-konfig.

## Säkerhet
- Ingen text lagras.
- CORS tillåter Lovable/Render-domäner samt localhost.
