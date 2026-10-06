from dotenv import load_dotenv
from io import StringIO

from app.config import get_settings


def test_nvidia_defaults_and_no_old_key_fallback(monkeypatch):
    monkeypatch.delenv('NVIDIA_API_KEY', raising=False)
    monkeypatch.delenv('ROOMSTYLER_VISION_MODEL', raising=False)
    monkeypatch.setenv('GEMINI_API_KEY', 'unused-test-secret')
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.nvidia_api_key is None
        assert settings.vision_model == 'z-ai/glm-5.3-flash'
        assert settings.provider_timeout_seconds == 180.0
        assert settings.provider_max_output_tokens == 16384
    finally:
        get_settings.cache_clear()


def test_env_precedence_and_key_redaction(monkeypatch):
    dotenv = StringIO('NVIDIA_API_KEY=file-key\nROOMSTYLER_VISION_MODEL=file-model\n')
    monkeypatch.setenv('NVIDIA_API_KEY', 'process-key')
    monkeypatch.setenv('ROOMSTYLER_VISION_MODEL', 'z-ai/glm-5.3-flash')
    load_dotenv(stream=dotenv, override=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.nvidia_api_key == 'process-key'
        assert settings.vision_model == 'z-ai/glm-5.3-flash'
        assert 'process-key' not in repr(settings)
    finally:
        get_settings.cache_clear()
