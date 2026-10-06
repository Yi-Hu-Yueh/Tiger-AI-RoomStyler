import asyncio
import base64
import json
import logging

import httpx
import pytest

from app.providers.nvidia_nim import DEFAULT_MODEL, NVIDIA_ENDPOINT, NvidiaNimVisionProvider, ProviderError
from app.schemas import AnalyzeConstraints


def constraints():
    return AnalyzeConstraints(main_goal="both", style="simple_and_clean", consent=True)


def response_body(text, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": text}}]}


def invoke(handler, api_key="test-secret"):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = NvidiaNimVisionProvider(api_key, DEFAULT_MODEL, 10, 16384, client)
            return await provider.analyze(b"actual-processed-image", "image/jpeg", constraints())
    return asyncio.run(run())


def test_actual_image_bytes_headers_model_endpoint_and_one_request(valid_analysis_dict):
    calls = []
    def handler(request):
        calls.append(request)
        assert str(request.url) == NVIDIA_ENDPOINT
        assert request.headers["Authorization"] == "Bearer test-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "z-ai/glm-5.3-flash"
        assert payload["stream"] is False
        assert payload["max_tokens"] == 16384
        assert "response_format" not in payload
        parts = payload["messages"][1]["content"]
        images = [part for part in parts if part["type"] == "image_url"]
        assert len(images) == 1
        prefix, data = images[0]["image_url"]["url"].split(",", 1)
        assert prefix == "data:image/jpeg;base64"
        assert base64.b64decode(data) == b"actual-processed-image"
        assert "supporting_observation_ids" in payload["messages"][0]["content"]
        assert "destination_observation_id" in payload["messages"][0]["content"]
        assert "visual_action_available" in payload["messages"][0]["content"]
        assert "no_purchase_alternative" in payload["messages"][0]["content"]
        assert "若使用者已擁有" in payload["messages"][0]["content"]
        return httpx.Response(200, json=response_body(json.dumps(valid_analysis_dict)))
    assert json.loads(invoke(handler)) == valid_analysis_dict
    assert len(calls) == 1


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_never_calls_provider(key):
    def handler(request):
        pytest.fail("Missing credentials must not send a request")
    with pytest.raises(ProviderError) as exc:
        invoke(handler, key)
    assert exc.value.code == "missing_api_key"


@pytest.mark.parametrize(("status", "code"), [
    (401, "authentication_failed"), (403, "authorization_failed"),
    (402, "quota_exhausted"), (429, "rate_limited"), (404, "model_unavailable"),
    (400, "provider_request_rejected"), (422, "provider_request_rejected"),
    (413, "provider_request_too_large"), (500, "provider_error"),
    (503, "provider_error"), (504, "provider_timeout"), (302, "provider_error"),
])
def test_http_failures_no_retry_or_private_error_leak(status, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "private-provider-details"}, headers={"Location": "https://example.invalid"})
    with pytest.raises(ProviderError) as exc:
        invoke(handler)
    assert exc.value.code == code
    assert "private-provider-details" not in str(exc.value)
    assert len(calls) == 1


@pytest.mark.parametrize(("exception", "code"), [
    (httpx.ReadTimeout, "provider_timeout"), (httpx.ConnectError, "provider_network_error"),
])
def test_transport_errors(exception, code):
    calls = []
    def handler(request):
        calls.append(request)
        raise exception("private details", request=request)
    with pytest.raises(ProviderError) as exc:
        invoke(handler)
    assert exc.value.code == code
    assert len(calls) == 1


def test_timeout_configuration_uses_bounded_phase_limits(valid_analysis_dict):
    observed = {}

    def handler(request):
        observed.update(request.extensions["timeout"])
        return httpx.Response(200, json=response_body(json.dumps(valid_analysis_dict)))

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = NvidiaNimVisionProvider("key", DEFAULT_MODEL, 180, 16384, client)
            await provider.analyze(b"actual-processed-image", "image/jpeg", constraints())

    asyncio.run(run())
    assert observed == {"connect": 10.0, "read": 180, "write": 30.0, "pool": 10.0}


def test_read_timeout_is_sanitized_logged_and_not_retried(caplog):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("private timeout details", request=request)

    with caplog.at_level(logging.WARNING, logger="app.providers.nvidia_nim"):
        with pytest.raises(ProviderError) as exc:
            invoke(handler)
    assert exc.value.code == "provider_timeout"
    assert exc.value.status_code == 504
    assert len(calls) == 1
    assert "timeout_type=ReadTimeout" in caplog.text
    assert "private timeout details" not in caplog.text


def test_malformed_provider_json():
    with pytest.raises(ProviderError) as exc:
        invoke(lambda request: httpx.Response(200, content=b"invalid json"))
    assert exc.value.code == "malformed_provider_response"


@pytest.mark.parametrize("body", [[], None, {}, {"choices": []}, {"choices": [None]}, response_body(None), response_body(123)])
def test_malformed_envelope(body):
    with pytest.raises(ProviderError) as exc:
        invoke(lambda request: httpx.Response(200, json=body))
    assert exc.value.code == "malformed_provider_response"


@pytest.mark.parametrize("text", ["not json", "```json\n{}\n```", "{incomplete"])
def test_malformed_model_json(text):
    with pytest.raises(ProviderError) as exc:
        invoke(lambda request: httpx.Response(200, json=response_body(text)))
    assert exc.value.code == "malformed_model_json"


@pytest.mark.parametrize("finish", ["length", None, "tool_calls"])
def test_incomplete_response(finish):
    with pytest.raises(ProviderError) as exc:
        invoke(lambda request: httpx.Response(200, json=response_body("{}", finish)))
    assert exc.value.code == "incomplete_response"


def test_length_limited_partial_json_is_rejected_without_private_logging(caplog):
    partial = '{"room_summary":"private cut off content"'
    with caplog.at_level(logging.INFO, logger="app.providers.nvidia_nim"):
        with pytest.raises(ProviderError) as exc:
            invoke(lambda request: httpx.Response(200, json=response_body(partial, "length")))
    assert exc.value.code == "incomplete_response"
    assert "finish_reason='length'" in caplog.text
    assert "requested_max_tokens=16384" in caplog.text
    assert "private cut off content" not in caplog.text


@pytest.mark.parametrize("body", [response_body("", "content_filter"), {"choices": [{"finish_reason": "stop", "message": {"refusal": "private refusal"}}]}])
def test_blocked_response(body):
    with pytest.raises(ProviderError) as exc:
        invoke(lambda request: httpx.Response(200, json=body))
    assert exc.value.code == "blocked_response"


def test_reasoning_is_not_returned(valid_analysis_dict):
    body = response_body(json.dumps(valid_analysis_dict))
    body["choices"][0]["message"]["reasoning_content"] = "private reasoning"
    assert "private reasoning" not in invoke(lambda request: httpx.Response(200, json=body))


def test_empty_image_cannot_become_text_only_request():
    provider = NvidiaNimVisionProvider("key", DEFAULT_MODEL, 10, 16384)
    with pytest.raises(ProviderError, match="圖片"):
        provider.build_request(b"", "image/jpeg", constraints())
