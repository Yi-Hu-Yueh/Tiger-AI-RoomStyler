from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MainGoal(str, Enum):
    organization = "organization"
    aesthetics = "aesthetics"
    both = "both"


class Style(str, Enum):
    simple_and_clean = "simple_and_clean"
    warm_and_natural = "warm_and_natural"
    preserve_current_style = "preserve_current_style"


class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class AnalyzeConstraints(StrictModel):
    main_goal: MainGoal
    style: Style
    allow_moving_large_furniture: bool = False
    allow_purchases: bool = False
    preserve_items: Annotated[str | None, Field(max_length=1000)] = None
    additional_constraints: Annotated[str | None, Field(max_length=1500)] = None
    consent: bool


class InputSuitability(StrictModel):
    suitable: bool
    explanation: Annotated[str, Field(min_length=1, max_length=1000)]


class BoundingBox(StrictModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @model_validator(mode="after")
    def valid_normalized_box(self) -> "BoundingBox":
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError("邊界框座標必須介於 0.0 到 1.0。")
        if self.x_min >= self.x_max or self.y_min >= self.y_max:
            raise ValueError("邊界框的最小座標必須小於最大座標。")
        return self


class Observation(StrictModel):
    observation_id: Annotated[str, Field(pattern=r"^obs_[1-9][0-9]*$")]
    visible_item_or_area: Annotated[str, Field(min_length=1, max_length=300)]
    position_description: Annotated[str, Field(min_length=1, max_length=500)]
    visible_evidence: Annotated[str, Field(min_length=1, max_length=1000)]
    uncertain: bool
    approximate_bbox: BoundingBox | None = None


class Recommendation(StrictModel):
    recommendation_id: Annotated[str, Field(pattern=r"^rec_[1-9][0-9]*$")]
    priority: Priority
    supporting_observation_ids: list[str]
    target_item_or_area: Annotated[str, Field(min_length=1, max_length=300)]
    action: Annotated[str, Field(min_length=1, max_length=1000)]
    destination_or_arrangement: Annotated[str | None, Field(max_length=1000)] = None
    practical_reason: Annotated[str, Field(min_length=1, max_length=1000)]
    aesthetic_rationale: Annotated[str | None, Field(max_length=1000)] = None
    requires_purchase: bool
    moves_large_furniture: bool
    requires_confirmation: bool
    confirmation_needed: Annotated[str | None, Field(max_length=1000)] = None
    destination_observation_id: Annotated[str | None, Field(pattern=r"^obs_[1-9][0-9]*$")] = None
    visual_action_available: bool = False
    visual_action_note: Annotated[str | None, Field(max_length=1000)] = None
    requires_existing_materials: bool = False
    no_purchase_alternative: Annotated[str | None, Field(max_length=1000)] = None

    @model_validator(mode="after")
    def confirmation_is_explained(self) -> "Recommendation":
        if self.requires_confirmation and not self.confirmation_needed:
            raise ValueError("需要確認時必須說明確認事項。")
        if self.requires_existing_materials and not self.no_purchase_alternative:
            raise ValueError("依賴現有材料時必須提供不使用材料的替代方案。")
        return self


class RoomAnalysis(StrictModel):
    input_suitability: InputSuitability
    room_summary: Annotated[str, Field(min_length=1, max_length=1500)]
    observations: list[Observation]
    recommendations: Annotated[list[Recommendation], Field(max_length=5)]
    uncertainties: list[Annotated[str, Field(min_length=1, max_length=800)]] = Field(default_factory=list)
    limitations: list[Annotated[str, Field(min_length=1, max_length=800)]] = Field(default_factory=list)

    @field_validator("uncertainties", "limitations", mode="before")
    @classmethod
    def normalize_optional_lists(cls, value):
        # Only absent/null auxiliary lists default to []; malformed values still fail.
        return [] if value is None else value


class ImageMetadata(StrictModel):
    width: int
    height: int
    mime_type: str
    resized_for_provider: bool


class AnalyzeResponse(StrictModel):
    analysis: RoomAnalysis
    image: ImageMetadata
    preview_data_url: str
    submitted_constraints: AnalyzeConstraints
    provider_model: str
    analysis_binding: str


class OrganizedPreviewResponse(StrictModel):
    label: str
    preview_data_url: str
    provider_model: str
    analysis_binding: str


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    error: ErrorDetail
