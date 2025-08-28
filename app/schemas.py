
from pydantic import BaseModel, Field

class TTSRequest(BaseModel):
    text: str = Field(min_length=1, description="Text to synthesize")
    model_id: str | None = Field(default=None, description="Override ElevenLabs model id")
    voice_id: str | None = Field(default=None, description="Override ElevenLabs voice id")

class StatusMsg(BaseModel):
    stage: str
    bytes: int | None = None
    message: str | None = None
