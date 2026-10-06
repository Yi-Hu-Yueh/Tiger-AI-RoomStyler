from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseModel):
    nvidia_api_key: str | None = Field(default=None, repr=False)
    vision_model: str = "z-ai/glm-5.3-flash"
    openai_api_key: str | None = Field(default=None, repr=False)
    image_model: str = "gpt-image-2.5-sunburst"
    host: str = "127.0.0.1"
    port: int = Field(default=18083, ge=1, le=65535)
    provider_timeout_seconds: float = Field(default=180.0, gt=0, le=300)
    provider_max_output_tokens: int = Field(default=16384, ge=256, le=16384)
    max_upload_bytes: int = 10 * 1024 * 1024
    max_decoded_pixels: int = 25_000_000
    provider_longest_edge: int = 2048


def _integer(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _floating(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        nvidia_api_key=(os.getenv("NVIDIA_API_KEY") or "").strip() or None,
        vision_model=os.getenv("ROOMSTYLER_VISION_MODEL", "z-ai/glm-5.3-flash"),
        openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip() or None,
        image_model=os.getenv("ROOMSTYLER_IMAGE_MODEL", "gpt-image-2.5-sunburst"),
        host=os.getenv("ROOMSTYLER_HOST", "127.0.0.1"),
        port=_integer("ROOMSTYLER_PORT", 18083),
        provider_timeout_seconds=_floating("ROOMSTYLER_PROVIDER_TIMEOUT_SECONDS", 180.0),
        provider_max_output_tokens=_integer("ROOMSTYLER_PROVIDER_MAX_OUTPUT_TOKENS", 16384),
        max_upload_bytes=_integer("ROOMSTYLER_MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
        max_decoded_pixels=_integer("ROOMSTYLER_MAX_DECODED_PIXELS", 25_000_000),
        provider_longest_edge=_integer("ROOMSTYLER_PROVIDER_LONGEST_EDGE", 2048),
    )
