from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.providers.nvidia_nim import NvidiaNimVisionProvider, ProviderError
from app.schemas import AnalyzeConstraints, AnalyzeResponse, ImageMetadata
from app.services.image_service import ImageValidationError, validate_and_process_upload
from app.services.room_analysis_service import AnalysisValidationError, analyze_room


router = APIRouter(prefix="/api/v1", tags=["analysis"])


def _http_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


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
        settings.nvidia_api_key,
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
    )
