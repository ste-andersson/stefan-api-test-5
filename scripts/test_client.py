
import argparse
import asyncio
import json
import wave
from pathlib import Path

import websockets

PCM_RATE = 16000
PCM_WIDTH = 2  # 16-bit
PCM_CH = 1

async def run(url: str, text: str, out_path: Path, voice_id: str | None):
    pcm_chunks: list[bytes] = []
    async with websockets.connect(url) as ws:
        payload = {"text": text}
        if voice_id:
            payload["voice_id"] = voice_id
        await ws.send(json.dumps(payload, ensure_ascii=False))
        while True:
            msg = await ws.recv()
            if isinstance(msg, (bytes, bytearray)):
                if msg:
                    pcm_chunks.append(bytes(msg))
            else:
                try:
                    data = json.loads(msg)
                except Exception:
                    print("[text]", msg)
                    continue
                stage = data.get("stage")
                print("[status]", data)
                if stage in {"done", "error"}:
                    break

    pcm = b"".join(pcm_chunks)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(PCM_CH)
        wf.setsampwidth(PCM_WIDTH)
        wf.setframerate(PCM_RATE)
        wf.writeframes(pcm)
    print(f"Wrote {len(pcm)} bytes PCM -> {out_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://localhost:8000/ws/tts")
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", default="out.wav")
    ap.add_argument("--voice", dest="voice_id", default=None)
    args = ap.parse_args()
    asyncio.run(run(args.url, args.text, Path(args.out), args.voice_id))

if __name__ == "__main__":
    main()
