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


@pytest.mark.parametrize("entered", [None, "", "   ", " owner-nvidia-test-key "])
def test_request_key_precedence_is_scoped_and_never_returned(monkeypatch, valid_analysis_dict, caplog, entered):
    settings = Settings(nvidia_api_key="server-nvidia-test-key")
    app.dependency_overrides[get_settings] = lambda: settings
    keys = []

    async def mocked(self, *_):
        keys.append(self.api_key)
        return json.dumps(valid_analysis_dict)

    monkeypatch.setattr(NvidiaNimVisionProvider, "analyze", mocked)
    response = client.post(
        "/api/v1/analyze", data=form(), files={"image": ("room.png", make_image(), "image/png")},
        headers={} if entered is None else {"X-RoomStyler-API-Key": entered},
    )
    assert response.status_code == 200
    assert keys == [(entered or "").strip() or settings.nvidia_api_key]
    assert settings.nvidia_api_key == "server-nvidia-test-key"
    second = client.post(
        "/api/v1/analyze", data=form(), files={"image": ("room.png", make_image(), "image/png")},
    )
    assert second.status_code == 200
    assert keys[-1] == "server-nvidia-test-key"
    for secret in ("server-nvidia-test-key", "owner-nvidia-test-key"):
        assert secret not in response.text + second.text + client.get("/health").text + caplog.text


def test_entered_key_works_without_server_key(monkeypatch, valid_analysis_dict):
    app.dependency_overrides[get_settings] = lambda: Settings(nvidia_api_key=None)

    async def mocked(self, *_):
        assert self.api_key == "owner-nvidia-test-key"
        return json.dumps(valid_analysis_dict)

    monkeypatch.setattr(NvidiaNimVisionProvider, "analyze", mocked)
    response = client.post(
        "/api/v1/analyze", data=form(), files={"image": ("room.png", make_image(), "image/png")},
        headers={"X-RoomStyler-API-Key": "owner-nvidia-test-key"},
    )
    assert response.status_code == 200


def test_rejected_user_key_does_not_retry_with_server_key(monkeypatch, caplog):
    calls = []

    async def rejected(self, *_):
        calls.append(self.api_key)
        raise ProviderError("authentication_failed", "NVIDIA API 金鑰驗證失敗。")

    monkeypatch.setattr(NvidiaNimVisionProvider, "analyze", rejected)
    response = client.post(
        "/api/v1/analyze", data=form(), files={"image": ("room.png", make_image(), "image/png")},
        headers={"X-RoomStyler-API-Key": "rejected-owner-test-key"},
    )
    assert response.status_code == 502
    assert calls == ["rejected-owner-test-key"]
    assert "rejected-owner-test-key" not in response.text + caplog.text


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
