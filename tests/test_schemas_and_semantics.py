from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from app.schemas import AnalyzeConstraints, RoomAnalysis
from app.services.room_analysis_service import AnalysisValidationError, validate_semantics


def constraints(**overrides) -> AnalyzeConstraints:
    values = {
        "main_goal": "both",
        "style": "preserve_current_style",
        "allow_moving_large_furniture": False,
        "allow_purchases": False,
        "consent": True,
    }
    values.update(overrides)
    return AnalyzeConstraints.model_validate(values)


def test_valid_constraints() -> None:
    assert constraints().main_goal.value == "both"


def test_invalid_enum() -> None:
    with pytest.raises(ValidationError):
        constraints(main_goal="invented")


def test_invalid_observation_reference(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["recommendations"][0]["supporting_observation_ids"] = ["obs_99"]
    with pytest.raises(AnalysisValidationError, match="不存在"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


def test_valid_destination_observation_reference(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["observations"].append(
        {
            "observation_id": "obs_2",
            "visible_item_or_area": "桌面右側空區",
            "position_description": "照片中央偏右",
            "visible_evidence": "可見未被物品占用的桌面區域。",
            "uncertain": False,
            "approximate_bbox": {"x_min": 0.65, "y_min": 0.25, "x_max": 0.9, "y_max": 0.65},
        }
    )
    valid_analysis_dict["recommendations"][0]["destination_observation_id"] = "obs_2"
    analysis = RoomAnalysis.model_validate(valid_analysis_dict)
    validate_semantics(analysis, constraints())
    assert analysis.recommendations[0].destination_observation_id == "obs_2"


def test_invalid_destination_observation_reference(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["recommendations"][0]["destination_observation_id"] = "obs_99"
    with pytest.raises(AnalysisValidationError, match="目的地觀察"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


def test_destination_without_bbox_is_rejected(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["observations"].append(
        {
            "observation_id": "obs_2",
            "visible_item_or_area": "可能的空區",
            "position_description": "照片右側",
            "visible_evidence": "位置可描述但沒有可靠框線。",
            "uncertain": True,
            "approximate_bbox": None,
        }
    )
    valid_analysis_dict["recommendations"][0]["destination_observation_id"] = "obs_2"
    with pytest.raises(AnalysisValidationError, match="目的地缺少"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


@pytest.mark.parametrize("kind", ["observation", "recommendation"])
def test_duplicate_ids(valid_analysis_dict: dict, kind: str) -> None:
    if kind == "observation":
        valid_analysis_dict["observations"].append(copy.deepcopy(valid_analysis_dict["observations"][0]))
    else:
        valid_analysis_dict["recommendations"].append(copy.deepcopy(valid_analysis_dict["recommendations"][0]))
    with pytest.raises(AnalysisValidationError, match="重複"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


@pytest.mark.parametrize(
    "box",
    [
        {"x_min": -0.1, "y_min": 0.1, "x_max": 0.5, "y_max": 0.5},
        {"x_min": 0.5, "y_min": 0.1, "x_max": 0.5, "y_max": 0.5},
        {"x_min": 0.1, "y_min": 0.8, "x_max": 0.5, "y_max": 0.2},
    ],
)
def test_invalid_bbox_coordinates(valid_analysis_dict: dict, box: dict) -> None:
    valid_analysis_dict["observations"][0]["approximate_bbox"] = box
    with pytest.raises(ValidationError):
        RoomAnalysis.model_validate(valid_analysis_dict)


def test_purchase_constraint_violation(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["recommendations"][0]["requires_purchase"] = True
    with pytest.raises(AnalysisValidationError, match="不購買"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


def test_no_purchase_material_advice_requires_owned_condition_and_alternative(valid_analysis_dict: dict) -> None:
    recommendation = valid_analysis_dict["recommendations"][0]
    recommendation["action"] = "使用束帶整理線材。"
    recommendation["requires_existing_materials"] = True
    recommendation["no_purchase_alternative"] = "沒有材料時，將線材沿桌緣平行整理。"
    with pytest.raises(AnalysisValidationError, match="已擁有"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


def test_no_purchase_material_advice_accepts_owned_condition_and_alternative(valid_analysis_dict: dict) -> None:
    recommendation = valid_analysis_dict["recommendations"][0]
    recommendation["action"] = "若使用者已擁有束帶，可用現有束帶整理線材。"
    recommendation["requires_existing_materials"] = True
    recommendation["no_purchase_alternative"] = "若沒有材料，將線材沿桌緣平行排列並移開走道。"
    analysis = RoomAnalysis.model_validate(valid_analysis_dict)
    validate_semantics(analysis, constraints())


def test_no_purchase_mode_rejects_new_item_wording(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["recommendations"][0]["action"] = "添購新層架放置物品。"
    with pytest.raises(AnalysisValidationError, match="取得新物品"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


def test_large_furniture_constraint_violation(valid_analysis_dict: dict) -> None:
    valid_analysis_dict["recommendations"][0]["moves_large_furniture"] = True
    with pytest.raises(AnalysisValidationError, match="不移動"):
        validate_semantics(RoomAnalysis.model_validate(valid_analysis_dict), constraints())


def test_more_than_five_recommendations(valid_analysis_dict: dict) -> None:
    recommendation = valid_analysis_dict["recommendations"][0]
    valid_analysis_dict["recommendations"] = [
        {**copy.deepcopy(recommendation), "recommendation_id": f"rec_{index}"}
        for index in range(1, 7)
    ]
    with pytest.raises(ValidationError):
        RoomAnalysis.model_validate(valid_analysis_dict)


def test_unsuitable_non_room_can_have_no_plan() -> None:
    result = RoomAnalysis.model_validate(
        {
            "input_suitability": {"suitable": False, "explanation": "影像不是可辨識的室內房間。"},
            "room_summary": "無法形成可靠的房間摘要。",
            "observations": [],
            "recommendations": [],
            "uncertainties": ["無法確認影像主體。"],
            "limitations": ["影像不足以提供房間建議。"],
        }
    )
    validate_semantics(result, constraints())
    assert result.recommendations == []
