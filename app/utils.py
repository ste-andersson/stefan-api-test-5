
import asyncio
import json
from typing import Any

async def send_json(ws, payload: dict[str, Any]) -> None:
    # Starlette WebSocket has .send_json but we want to ensure text frames.
    await ws.send_text(json.dumps(payload, ensure_ascii=False))

class ByteMeter:
    def __init__(self) -> None:
        self.total = 0

    def add(self, n: int) -> None:
        self.total += int(n)

    @property
    def any(self) -> bool:
        return self.total > 0

async def aiter_websocket_messages(ws):
    """Async iterator over incoming websocket messages (client side).
    Yields text as str and binary as bytes.
    """
    while True:
        try:
            msg = await ws.receive_text()
            yield msg
        except Exception:
            # try binary
            try:
                data = await ws.receive_bytes()
                yield data
            except Exception:
                break
