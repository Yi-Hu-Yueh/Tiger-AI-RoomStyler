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
        assert settings.image_model == 'gpt-image-2.5-sunburst'
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


def test_openai_key_is_optional_and_redacted(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('ROOMSTYLER_IMAGE_MODEL', raising=False)
    get_settings.cache_clear()
    assert get_settings().openai_api_key is None
    monkeypatch.setenv('OPENAI_API_KEY', 'openai-test-secret')
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.openai_api_key == 'openai-test-secret'
    assert settings.image_model == 'gpt-image-2.5-sunburst'
    assert 'openai-test-secret' not in repr(settings)
    get_settings.cache_clear()
