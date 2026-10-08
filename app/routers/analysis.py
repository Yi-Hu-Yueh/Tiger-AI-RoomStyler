from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import SecretStr, ValidationError

from app.config import Settings, get_settings
from app.providers.nvidia_nim import NvidiaNimVisionProvider, ProviderError
from app.providers.openai_image import ImageEditProviderError, OpenAIImageEditProvider
from app.schemas import (
    AnalyzeConstraints,
    AnalyzeResponse,
    ImageMetadata,
    OrganizedPreviewResponse,
    RoomAnalysis,
)
from app.services.image_service import ImageValidationError, validate_and_process_upload
from app.services.preview_binding import binding_matches, create_analysis_binding
from app.services.room_analysis_service import AnalysisValidationError, analyze_room, validate_semantics


router = APIRouter(prefix="/api/v1", tags=["analysis"])


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _request_key(entered: SecretStr | None, server_key: str | None) -> str | None:
    # Request-only header: never mutate settings/environment or include it in response/binding data.
    value = entered.get_secret_value().strip() if entered is not None else ""
    return value or server_key


def _constraints(
    main_goal: str,
    style: str,
    allow_moving_large_furniture: bool,
    allow_purchases: bool,
    preserve_items: str | None,
    additional_constraints: str | None,
    consent: bool,
) -> AnalyzeConstraints:
    try:
        result = AnalyzeConstraints(
            main_goal=main_goal,
            style=style,
            allow_moving_large_furniture=allow_moving_large_furniture,
            allow_purchases=allow_purchases,
            preserve_items=preserve_items or None,
            additional_constraints=additional_constraints or None,
            consent=consent,
        )
    except ValidationError as exc:
        raise _http_error(422, "invalid_constraints", "提交的目標、風格或限制無效。") from exc
    if not result.consent:
        raise _http_error(422, "consent_required", "必須明確同意雲端處理後才能開始分析。")
    return result


async def _image(upload: UploadFile, settings: Settings):
    try:
        return await validate_and_process_upload(
            upload,
            settings.max_upload_bytes,
            settings.max_decoded_pixels,
            settings.provider_longest_edge,
        )
    except ImageValidationError as exc:
        raise _http_error(422, "invalid_image", str(exc)) from exc


@router.post("/preview")
async def preview_image(
    image: UploadFile = File(...), settings: Settings = Depends(get_settings)
) -> dict[str, object]:
    processed = await _image(image, settings)
    return {
        "preview_data_url": processed.preview_data_url,
        "image": {
            "width": processed.width,
            "height": processed.height,
            "mime_type": processed.mime_type,
            "resized_for_provider": processed.resized,
        },
    }


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    image: UploadFile = File(...),
    main_goal: str = Form(...),
    style: str = Form(...),
    allow_moving_large_furniture: bool = Form(False),
    allow_purchases: bool = Form(False),
    preserve_items: str | None = Form(None),
    additional_constraints: str | None = Form(None),
    consent: bool = Form(False),
    api_key: SecretStr | None = Header(None, alias="X-RoomStyler-API-Key"),
    settings: Settings = Depends(get_settings),
) -> AnalyzeResponse:
    constraints = _constraints(
        main_goal,
        style,
        allow_moving_large_furniture,
        allow_purchases,
        preserve_items,
        additional_constraints,
        consent,
    )
    processed = await _image(image, settings)
    provider = NvidiaNimVisionProvider(
        _request_key(api_key, settings.nvidia_api_key),
        settings.vision_model,
        settings.provider_timeout_seconds,
        settings.provider_max_output_tokens,
    )
    try:
        result = await analyze_room(provider, processed, constraints)
    except ProviderError as exc:
        raise _http_error(exc.status_code, exc.code, exc.message) from exc
    except AnalysisValidationError as exc:
        raise _http_error(502, "response_validation_failed", str(exc)) from exc
    return AnalyzeResponse(
        analysis=result,
        image=ImageMetadata(
            width=processed.width,
            height=processed.height,
            mime_type=processed.mime_type,
            resized_for_provider=processed.resized,
        ),
        preview_data_url=processed.preview_data_url,
        submitted_constraints=constraints,
        provider_model=settings.vision_model,
        analysis_binding=create_analysis_binding(processed.data, result, constraints),
    )


@router.post("/organized-preview", response_model=OrganizedPreviewResponse)
async def organized_preview(
    image: UploadFile = File(...),
    analysis_json: str = Form(...),
    constraints_json: str = Form(...),
    analysis_binding: str = Form(...),
    api_key: SecretStr | None = Header(None, alias="X-RoomStyler-API-Key"),
    settings: Settings = Depends(get_settings),
) -> OrganizedPreviewResponse:
    try:
        analysis = RoomAnalysis.model_validate_json(analysis_json)
        constraints = AnalyzeConstraints.model_validate_json(constraints_json)
        validate_semantics(analysis, constraints)
    except (ValidationError, AnalysisValidationError) as exc:
        raise _http_error(422, "invalid_preview_context", "預覽所需的分析或限制資料無效。") from exc
    if not analysis.input_suitability.suitable or not analysis.recommendations:
        raise _http_error(422, "preview_not_available", "目前分析沒有可供產生預覽的核准行動。")

    processed = await _image(image, settings)
    if not binding_matches(analysis_binding, processed.data, analysis, constraints):
        raise _http_error(409, "stale_analysis", "照片、建議或限制已變更，請重新分析後再產生預覽。")

    provider = OpenAIImageEditProvider(
        _request_key(api_key, settings.openai_api_key),
        settings.image_model,
        settings.provider_timeout_seconds,
    )
    try:
        output, output_mime = await provider.edit(
            processed.data,
            processed.mime_type,
            analysis.recommendations,
            constraints,
        )
    except ImageEditProviderError as exc:
        raise _http_error(exc.status_code, exc.code, exc.message) from exc
    return OrganizedPreviewResponse(
        label="AI 整理預覽",
        preview_data_url=f"data:{output_mime};base64,{base64.b64encode(output).decode('ascii')}",
        provider_model=settings.image_model,
        analysis_binding=analysis_binding,
    )
