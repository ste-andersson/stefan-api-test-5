
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "stefan-api-test-5 backend"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    # ElevenLabs
    elevenlabs_api_key: str | None = Field(default=None, env="ELEVENLABS_API_KEY")
    elevenlabs_model_id: str = Field(default="eleven_turbo_v2_5", env="ELEVENLABS_MODEL_ID")
    elevenlabs_voice_id: str | None = Field(default=None, env="ELEVENLABS_VOICE_ID")
    # Upstream ws template (from user's spec)
    elevenlabs_ws_url_template: str = Field(
        default="wss://api.elevenlabs.io/v1/text-to-speech/stream-input?model_id={MODEL_ID}&output_format=pcm_16000&auto_mode=true"
    )
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    # Tuning
    upstream_connect_timeout_s: float = Field(default=10.0)
    upstream_stall_timeout_s: float = Field(default=8.0)
    chunk_length_schedule: tuple[int, int, int] = Field(default=(30, 60, 100))

    # Pydantic v2+ settings config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
