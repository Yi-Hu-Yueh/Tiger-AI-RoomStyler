from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.schemas import AnalyzeConstraints, Recommendation


OPENAI_IMAGE_EDIT_ENDPOINT = "https://api.openai.com/v1/images/edits"
DEFAULT_IMAGE_MODEL = "gpt-image-2.5-sunburst"
OUTPUT_LIMIT_BYTES = 50 * 1024 * 1024


class ImageEditProviderError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class OpenAIImageEditProvider:
    """One image-edit request with no retries, alternatives, or fallback."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client = client

    @staticmethod
    def build_prompt(
        recommendations: list[Recommendation], constraints: AnalyzeConstraints
    ) -> str:
        if not recommendations:
            raise ImageEditProviderError(
                "preview_not_available", "沒有已核准的整理建議可供產生預覽。", 422
            )
        actions = "\n".join(
            f"{index}. {item.action}"
            + (f" 安排：{item.destination_or_arrangement}" if item.destination_or_arrangement else "")
            + (f" 執行前確認：{item.confirmation_needed}" if item.confirmation_needed else "")
            + (f" 免購買替代：{item.no_purchase_alternative}" if item.no_purchase_alternative else "")
            for index, item in enumerate(recommendations, start=1)
        )
        purchase_rule = (
            "不得新增家具、收納用品、裝飾或任何原照片中不存在的物品；只能重新整理原本可見的物品。"
            if not constraints.allow_purchases
            else "除非下列已核准行動明確要求，否則不得新增物品。"
        )
        furniture_rule = (
            "所有大型家具的位置與方向必須完全不變。"
            if not constraints.allow_moving_large_furniture
            else "除非下列已核准行動明確要求，否則大型家具的位置與方向必須不變。"
        )
        return (
            "對輸入的真實房間照片做精準、局部的整理編輯，只執行下列已核准行動。\n"
            "硬性不變條件：必須是同一房間、同一相機視角、同一構圖與透視；牆壁、窗、門、地板、天花板及固定結構完全不變；"
            "保留目前風格、光線與材質；保留無法確定身分或用途的物品，不得以猜測內容替換。\n"
            f"{furniture_rule}\n{purchase_rule}\n"
            "不得移除任何未被核准行動明確涵蓋的 belongings，不得重新設計空間。不要在圖片中加入文字、標籤或浮水印。\n"
            "已核准行動：\n"
            f"{actions}"
        )

    @staticmethod
    def _validated_output(data: bytes) -> tuple[bytes, str]:
        if not data or len(data) > OUTPUT_LIMIT_BYTES:
            raise ImageEditProviderError("malformed_provider_response", "OpenAI 未提供有效的預覽圖片。")
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
                mime_type = Image.MIME.get(image.format or "")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageEditProviderError(
                "malformed_provider_response", "OpenAI 回傳的預覽圖片無法驗證。"
            ) from exc
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            raise ImageEditProviderError("malformed_provider_response", "OpenAI 回傳了不支援的圖片格式。")
        return data, mime_type

    async def edit(
        self,
        image_bytes: bytes,
        mime_type: str,
        recommendations: list[Recommendation],
        constraints: AnalyzeConstraints,
    ) -> tuple[bytes, str]:
        if not self.api_key or not self.api_key.strip():
            raise ImageEditProviderError(
                "missing_openai_api_key", "伺服器尚未設定 OPENAI_API_KEY。", 503
            )
        if not image_bytes or mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ImageEditProviderError("invalid_provider_image", "缺少可供編輯的有效房間圖片。", 422)

        prompt = self.build_prompt(recommendations, constraints)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(follow_redirects=False)
        try:
            response = await client.post(
                OPENAI_IMAGE_EDIT_ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={
                    "model": self.model,
                    "prompt": prompt,
                    "n": "1",
                    "output_format": "png",
                },
                files={"image": ("room.jpg", image_bytes, mime_type)},
                timeout=httpx.Timeout(
                    self.timeout_seconds,
                    connect=min(10.0, self.timeout_seconds),
                    write=self.timeout_seconds,
                    pool=min(10.0, self.timeout_seconds),
                ),
                follow_redirects=False,
            )
        except httpx.TimeoutException as exc:
            raise ImageEditProviderError("image_provider_timeout", "OpenAI 圖片編輯逾時。", 504) from exc
        except httpx.RequestError as exc:
            raise ImageEditProviderError("image_provider_network_error", "無法連線至 OpenAI 圖片服務。") from exc
        finally:
            if owns_client:
                await client.aclose()

        errors: dict[int, tuple[str, str, int]] = {
            400: ("image_request_rejected", "OpenAI 拒絕圖片編輯請求。", 502),
            401: ("image_authentication_failed", "OPENAI_API_KEY 驗證失敗。", 502),
            403: ("image_authorization_failed", "OpenAI 帳戶無權使用指定圖片模型。", 502),
            413: ("image_request_too_large", "圖片編輯請求超過 OpenAI 服務上限。", 413),
            429: ("image_rate_limited", "OpenAI 額度不足或請求過於頻繁。", 429),
        }
        if response.status_code in errors:
            raise ImageEditProviderError(*errors[response.status_code])
        if response.status_code != 200:
            raise ImageEditProviderError("image_provider_error", "OpenAI 圖片服務未能完成請求。")
        try:
            body: Any = response.json()
            items = body.get("data") if isinstance(body, dict) else None
            encoded = items[0].get("b64_json") if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict) else None
            if not isinstance(encoded, str) or not encoded:
                raise ValueError("missing image")
            output = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ImageEditProviderError(
                "malformed_provider_response", "OpenAI 回應缺少單一有效的預覽圖片。"
            ) from exc
        return self._validated_output(output)


__all__ = [
    "DEFAULT_IMAGE_MODEL",
    "ImageEditProviderError",
    "OPENAI_IMAGE_EDIT_ENDPOINT",
    "OpenAIImageEditProvider",
]
