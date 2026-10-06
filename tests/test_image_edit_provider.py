from __future__ import annotations

import asyncio
import base64
from io import BytesIO

import httpx
import pytest
from PIL import Image

from app.providers.openai_image import (
    DEFAULT_IMAGE_MODEL,
    OPENAI_IMAGE_EDIT_ENDPOINT,
    ImageEditProviderError,
    OpenAIImageEditProvider,
)
from app.schemas import AnalyzeConstraints, Recommendation


def output_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 12), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def constraints() -> AnalyzeConstraints:
    return AnalyzeConstraints(
        main_goal="both",
        style="preserve_current_style",
        allow_moving_large_furniture=False,
        allow_purchases=False,
        consent=True,
    )


def recommendations() -> list[Recommendation]:
    return [
        Recommendation(
            recommendation_id="rec_1",
            priority="high",
            supporting_observation_ids=["obs_1"],
            target_item_or_area="桌面瓶罐",
            action="把水瓶移離鍵盤旁。",
            destination_or_arrangement="放到原照片可見的桌面右側空位。",
            practical_reason="避免液體靠近設備。",
            requires_purchase=False,
            moves_large_furniture=False,
            requires_confirmation=False,
        )
    ]


def test_one_image_edit_request_contains_actual_image_model_and_preservation_rules():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert str(request.url) == OPENAI_IMAGE_EDIT_ENDPOINT
        assert request.headers["Authorization"] == "Bearer test-secret"
        assert b"actual-processed-room-image" in request.content
        assert DEFAULT_IMAGE_MODEL.encode() in request.content
        assert "同一相機視角".encode() in request.content
        assert "不得新增家具".encode() in request.content
        assert "大型家具的位置與方向必須完全不變".encode() in request.content
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(output_png()).decode()}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAIImageEditProvider("test-secret", DEFAULT_IMAGE_MODEL, 30, client)
            return await provider.edit(
                b"actual-processed-room-image", "image/jpeg", recommendations(), constraints()
            )

    data, mime = asyncio.run(run())
    assert data == output_png()
    assert mime == "image/png"
    assert len(calls) == 1


def test_missing_openai_key_never_sends_request():
    def handler(_: httpx.Request) -> httpx.Response:
        pytest.fail("missing key must not send a request")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAIImageEditProvider(None, DEFAULT_IMAGE_MODEL, 30, client)
            return await provider.edit(b"image", "image/jpeg", recommendations(), constraints())

    with pytest.raises(ImageEditProviderError) as exc:
        asyncio.run(run())
    assert exc.value.code == "missing_openai_api_key"


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "image_authentication_failed"), (403, "image_authorization_failed"),
     (429, "image_rate_limited"), (500, "image_provider_error")],
)
def test_image_provider_errors_are_sanitized_and_not_retried(status, code):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"error": "private provider content"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenAIImageEditProvider("key", DEFAULT_IMAGE_MODEL, 30, client)
            return await provider.edit(b"image", "image/jpeg", recommendations(), constraints())

    with pytest.raises(ImageEditProviderError) as exc:
        asyncio.run(run())
    assert exc.value.code == code
    assert "private provider content" not in str(exc.value)
    assert len(calls) == 1


def test_prompt_never_invents_unapproved_objects_when_purchases_disabled():
    prompt = OpenAIImageEditProvider.build_prompt(recommendations(), constraints())
    assert "只能重新整理原本可見的物品" in prompt
    assert "保留無法確定身分或用途的物品" in prompt
    assert "已核准行動" in prompt
