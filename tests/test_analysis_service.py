from __future__ import annotations

import asyncio
import json

import pytest

from app.schemas import AnalyzeConstraints
from app.services.image_service import ProcessedImage
from app.services.room_analysis_service import AnalysisValidationError, analyze_room


class FakeProvider:
    def __init__(self, response: str): self.response = response
    async def analyze(self, image_bytes, mime_type, constraints): return self.response


def constraints() -> AnalyzeConstraints:
    return AnalyzeConstraints(main_goal="both", style="preserve_current_style", consent=True)


def image() -> ProcessedImage:
    return ProcessedImage(b"real", "image/jpeg", 1, 1, False)


def test_service_accepts_valid_structured_response(valid_analysis_dict: dict) -> None:
    result = asyncio.run(analyze_room(FakeProvider(json.dumps(valid_analysis_dict)), image(), constraints()))
    assert result.observations[0].observation_id == "obs_1"


def test_service_rejects_malformed_model_json() -> None:
    with pytest.raises(AnalysisValidationError, match="結構化"):
        asyncio.run(analyze_room(FakeProvider("not json"), image(), constraints()))


def test_provider_failure_path_has_no_fallback_advice() -> None:
    with pytest.raises(AnalysisValidationError):
        asyncio.run(analyze_room(FakeProvider("{}"), image(), constraints()))
