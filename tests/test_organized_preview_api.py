from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.providers.openai_image import OpenAIImageEditProvider
from app.schemas import AnalyzeConstraints, RoomAnalysis
from app.services.image_service import process_image
from app.services.preview_binding import create_analysis_binding
from tests.conftest import make_image


client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def isolated_settings():
    app.dependency_overrides[get_settings] = lambda: Settings(
        nvidia_api_key="nvidia-test-secret", openai_api_key=None
    )
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def preview_context(valid_analysis_dict: dict, image_bytes: bytes | None = None):
    original = image_bytes or make_image()
    processed = process_image(original, 25_000_000, 2048)
    analysis = RoomAnalysis.model_validate(valid_analysis_dict)
    constraints = AnalyzeConstraints(
        main_goal="both",
        style="preserve_current_style",
        allow_moving_large_furniture=False,
        allow_purchases=False,
        preserve_items=None,
        additional_constraints=None,
        consent=True,
    )
    binding = create_analysis_binding(processed.data, analysis, constraints)
    data = {
        "analysis_json": analysis.model_dump_json(),
        "constraints_json": constraints.model_dump_json(),
        "analysis_binding": binding,
    }
    return original, processed, analysis, constraints, binding, data


def test_missing_openai_key_does_not_block_app_but_blocks_preview(valid_analysis_dict):
    assert client.get("/health").json()["application"]["status"] == "ok"
    assert client.get("/health").json()["image_provider"]["configured"] is False
    original, _, _, _, _, data = preview_context(valid_analysis_dict)
    response = client.post(
        "/api/v1/organized-preview",
        data=data,
        files={"image": ("room.png", original, "image/png")},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "missing_openai_api_key"


def test_preview_uses_bound_processed_image_recommendations_and_constraints(
    monkeypatch, valid_analysis_dict
):
    app.dependency_overrides[get_settings] = lambda: Settings(
        nvidia_api_key="nvidia-test-secret", openai_api_key="openai-test-secret"
    )
    original, processed, analysis, _, binding, data = preview_context(valid_analysis_dict)
    calls = []

    async def mocked_edit(self, image_bytes, mime_type, recommendations, constraints):
        calls.append((image_bytes, mime_type, recommendations, constraints))
        assert self.model == "gpt-image-2.5-sunburst"
        assert image_bytes == processed.data
        assert mime_type == "image/jpeg"
        assert recommendations == analysis.recommendations
        assert constraints.allow_purchases is False
        assert constraints.allow_moving_large_furniture is False
        return make_image("PNG", (40, 30)), "image/png"

    monkeypatch.setattr(OpenAIImageEditProvider, "edit", mocked_edit)
    response = client.post(
        "/api/v1/organized-preview",
        data=data,
        files={"image": ("room.png", original, "image/png")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "AI 整理預覽"
    assert payload["provider_model"] == "gpt-image-2.5-sunburst"
    assert payload["analysis_binding"] == binding
    assert payload["preview_data_url"].startswith("data:image/png;base64,")
    assert len(calls) == 1


@pytest.mark.parametrize("entered", [None, "", "   ", " owner-openai-test-key "])
def test_preview_request_key_precedence_and_isolation(monkeypatch, valid_analysis_dict, caplog, entered):
    settings = Settings(openai_api_key="server-openai-test-key", nvidia_api_key="server-nvidia-test-key")
    app.dependency_overrides[get_settings] = lambda: settings
    original, _, _, _, _, data = preview_context(valid_analysis_dict)
    keys = []

    async def mocked(self, *_):
        keys.append(self.api_key)
        return make_image("PNG"), "image/png"

    monkeypatch.setattr(OpenAIImageEditProvider, "edit", mocked)
    response = client.post(
        "/api/v1/organized-preview", data=data, files={"image": ("room.png", original, "image/png")},
        headers={} if entered is None else {"X-RoomStyler-API-Key": entered},
    )
    assert response.status_code == 200
    assert keys == [(entered or "").strip() or "server-openai-test-key"]
    assert settings.openai_api_key == "server-openai-test-key"
    assert settings.nvidia_api_key == "server-nvidia-test-key"
    second = client.post(
        "/api/v1/organized-preview", data=data, files={"image": ("room.png", original, "image/png")},
    )
    assert second.status_code == 200
    assert keys[-1] == "server-openai-test-key"
    for secret in ("owner-openai-test-key", "server-openai-test-key", "server-nvidia-test-key"):
        assert secret not in response.text + second.text + client.get("/health").text + caplog.text


def test_preview_entered_key_works_without_server_configuration(monkeypatch, valid_analysis_dict):
    original, _, _, _, _, data = preview_context(valid_analysis_dict)

    async def mocked(self, *_):
        assert self.api_key == "owner-openai-test-key"
        return make_image("PNG"), "image/png"

    monkeypatch.setattr(OpenAIImageEditProvider, "edit", mocked)
    response = client.post(
        "/api/v1/organized-preview", data=data, files={"image": ("room.png", original, "image/png")},
        headers={"X-RoomStyler-API-Key": "owner-openai-test-key"},
    )
    assert response.status_code == 200


def test_changed_image_is_rejected_before_remote_edit(monkeypatch, valid_analysis_dict):
    app.dependency_overrides[get_settings] = lambda: Settings(openai_api_key="openai-test-secret")
    _, _, _, _, _, data = preview_context(valid_analysis_dict)

    async def must_not_run(*_):
        pytest.fail("stale context must not reach the provider")

    monkeypatch.setattr(OpenAIImageEditProvider, "edit", must_not_run)
    changed = make_image(color=(220, 30, 30))
    response = client.post(
        "/api/v1/organized-preview",
        data=data,
        files={"image": ("changed.png", changed, "image/png")},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_analysis"


def test_changed_recommendations_are_rejected_before_remote_edit(monkeypatch, valid_analysis_dict):
    app.dependency_overrides[get_settings] = lambda: Settings(openai_api_key="openai-test-secret")
    original, _, _, _, _, data = preview_context(valid_analysis_dict)
    changed = json.loads(data["analysis_json"])
    changed["recommendations"][0]["action"] = "未經本次分析核准的動作"
    data["analysis_json"] = json.dumps(changed)

    async def must_not_run(*_):
        pytest.fail("modified recommendations must not reach the provider")

    monkeypatch.setattr(OpenAIImageEditProvider, "edit", must_not_run)
    response = client.post(
        "/api/v1/organized-preview",
        data=data,
        files={"image": ("room.png", original, "image/png")},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_analysis"
