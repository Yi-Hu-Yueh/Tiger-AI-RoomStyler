from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.config import Settings
from app.providers.nvidia_nim import NvidiaNimVisionProvider, ProviderError
import base64
from io import BytesIO
import json
import pytest
from PIL import Image
from tests.conftest import make_image


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def isolated_settings():
    app.dependency_overrides[get_settings] = lambda: Settings(nvidia_api_key="test-secret")
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def form(consent: str = "true") -> dict[str, str]:
    return {
        "main_goal": "both",
        "style": "preserve_current_style",
        "allow_moving_large_furniture": "false",
        "allow_purchases": "false",
        "consent": consent,
    }


def test_health_distinguishes_application_and_provider(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    get_settings.cache_clear()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["application"]["status"] == "ok"
    assert response.json()["provider"]["configured"] is False


def test_missing_consent_rejected_before_provider() -> None:
    response = client.post(
        "/api/v1/analyze", data=form("false"), files={"image": ("room.png", make_image(), "image/png")}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "consent_required"


def test_invalid_enum() -> None:
    values = form(); values["main_goal"] = "invalid"
    response = client.post(
        "/api/v1/analyze", data=values, files={"image": ("room.png", make_image(), "image/png")}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_constraints"


def test_preview_validates_and_returns_processed_snapshot() -> None:
    response = client.post("/api/v1/preview", files={"image": ("fake.txt", make_image(), "text/plain")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["preview_data_url"].startswith("data:image/jpeg;base64,")
    assert payload["image"]["width"] == 80


def test_missing_credentials_returns_no_fake_advice(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    app.dependency_overrides[get_settings] = lambda: Settings(nvidia_api_key=None)
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/analyze", data=form(), files={"image": ("room.png", make_image(), "image/png")}
    )
    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["code"] == "missing_api_key"
    assert "analysis" not in payload and "recommendations" not in payload


def test_mocked_analysis_uses_exact_preview_bytes(monkeypatch, valid_analysis_dict):
    calls = []
    async def mocked(self, data, mime, constraints):
        calls.append(data)
        with Image.open(BytesIO(data)) as image:
            assert image.format == "JPEG"
        assert mime == "image/jpeg"
        assert constraints.allow_purchases is False
        return json.dumps(valid_analysis_dict)
    monkeypatch.setattr(NvidiaNimVisionProvider, "analyze", mocked)
    response = client.post('/api/v1/analyze', data=form(), files={'image': ('room.png', make_image(), 'image/png')})
    assert response.status_code == 200
    payload = response.json()
    assert base64.b64decode(payload['preview_data_url'].split(',', 1)[1]) == calls[0]
    assert len(calls) == 1
    assert payload['provider_model'] == 'z-ai/glm-5.3-flash'


@pytest.mark.parametrize('code', ['authentication_failed', 'rate_limited', 'provider_timeout', 'provider_network_error', 'blocked_response'])
def test_failed_provider_never_returns_fake_advice(monkeypatch, code):
    async def fail(*args):
        raise ProviderError(code, '雲端分析失敗。')
    monkeypatch.setattr(NvidiaNimVisionProvider, 'analyze', fail)
    response = client.post('/api/v1/analyze', data=form(), files={'image': ('room.png', make_image(), 'image/png')})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == code
    assert 'analysis' not in response.json()


@pytest.mark.parametrize('field', ['requires_purchase', 'moves_large_furniture'])
def test_constraint_violation_is_not_success(monkeypatch, valid_analysis_dict, field):
    valid_analysis_dict['recommendations'][0][field] = True
    async def mocked(*args):
        return json.dumps(valid_analysis_dict)
    monkeypatch.setattr(NvidiaNimVisionProvider, 'analyze', mocked)
    response = client.post('/api/v1/analyze', data=form(), files={'image': ('room.png', make_image(), 'image/png')})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'response_validation_failed'
    assert 'analysis' not in response.json()
