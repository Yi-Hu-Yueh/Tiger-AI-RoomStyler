from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers.analysis import router as analysis_router


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Tiger AI Room Styler", version="2A")
app.include_router(analysis_router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def request_validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": "提交的資料不完整或格式無效。"}},
    )


@app.exception_handler(Exception)
async def unexpected_error(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "伺服器發生未預期錯誤。"}},
    )


@app.get("/health")
async def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "application": {"status": "ok"},
        "provider": {
            "name": "NVIDIA NIM",
            "configured": bool(settings.nvidia_api_key),
            "model": settings.vision_model,
            "message": "NVIDIA API 金鑰已設定（尚未驗證連線）。" if settings.nvidia_api_key else "尚未設定 NVIDIA_API_KEY。",
        },
        "image_provider": {
            "name": "OpenAI Image API",
            "configured": bool(settings.openai_api_key),
            "model": settings.image_model,
            "message": "OpenAI API 金鑰已設定（功能尚未實際測試）。" if settings.openai_api_key else "尚未設定 OPENAI_API_KEY。",
        },
    }


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
