"""Only missing/null auxiliary lists are normalized; core/semantic checks still apply."""
import copy
import json

import pytest
from pydantic import ValidationError

from app.schemas import AnalyzeConstraints, RoomAnalysis
from app.services.room_analysis_service import AnalysisValidationError, validate_semantics


def parse(value):
    analysis = RoomAnalysis.model_validate_json(json.dumps(value))
    validate_semantics(analysis, AnalyzeConstraints(
        main_goal="both", style="preserve_current_style", consent=True,
    ))
    return analysis


@pytest.mark.parametrize("keys", [("limitations",), ("uncertainties",), ("limitations", "uncertainties")])
@pytest.mark.parametrize("null", [False, True])
def test_missing_or_null_optional_lists_become_empty(valid_analysis_dict, keys, null):
    for key in keys:
        if null:
            valid_analysis_dict[key] = None
        else:
            valid_analysis_dict.pop(key)
    analysis = parse(valid_analysis_dict)
    for key in keys:
        assert getattr(analysis, key) == []


def test_existing_optional_lists_are_not_discarded(valid_analysis_dict):
    analysis = parse(valid_analysis_dict)
    assert analysis.limitations == valid_analysis_dict["limitations"]
    assert analysis.uncertainties == valid_analysis_dict["uncertainties"]


@pytest.mark.parametrize("key", ["limitations", "uncertainties"])
@pytest.mark.parametrize("value", ["", {}, False, 0, [None], [""], ["x" * 801]])
def test_malformed_optional_lists_are_not_defaulted(valid_analysis_dict, key, value):
    valid_analysis_dict[key] = value
    with pytest.raises(ValidationError):
        parse(valid_analysis_dict)


@pytest.mark.parametrize("key", ["input_suitability", "room_summary", "observations", "recommendations"])
@pytest.mark.parametrize("null", [False, True])
def test_missing_or_null_core_fields_still_fail(valid_analysis_dict, key, null):
    valid_analysis_dict.pop("limitations")
    valid_analysis_dict["uncertainties"] = None
    if null:
        valid_analysis_dict[key] = None
    else:
        valid_analysis_dict.pop(key)
    with pytest.raises(ValidationError):
        parse(valid_analysis_dict)


@pytest.mark.parametrize("collection,key", [
    ("observations", "observation_id"),
    *[("recommendations", key) for key in (
        "recommendation_id", "priority", "supporting_observation_ids", "target_item_or_area",
        "action", "practical_reason", "requires_purchase", "moves_large_furniture", "requires_confirmation",
    )],
])
def test_required_ids_references_and_recommendation_fields_still_fail(valid_analysis_dict, collection, key):
    valid_analysis_dict.pop("limitations")
    valid_analysis_dict.pop("uncertainties")
    valid_analysis_dict[collection][0].pop(key)
    with pytest.raises(ValidationError):
        parse(valid_analysis_dict)


@pytest.mark.parametrize("kind", [
    "source_reference", "duplicate_observation", "duplicate_recommendation", "bbox",
    "purchase", "furniture", "count", "destination_reference", "destination_bbox", "material_advice",
])
def test_semantics_remain_enforced_after_list_normalization(valid_analysis_dict, kind):
    value = valid_analysis_dict
    value.pop("limitations")
    value["uncertainties"] = None
    recommendation = value["recommendations"][0]
    if kind == "source_reference":
        recommendation["supporting_observation_ids"] = ["obs_99"]
    elif kind == "duplicate_observation":
        value["observations"].append(copy.deepcopy(value["observations"][0]))
    elif kind == "duplicate_recommendation":
        value["recommendations"].append(copy.deepcopy(recommendation))
    elif kind == "bbox":
        value["observations"][0]["approximate_bbox"]["x_min"] = 0.9
    elif kind == "purchase":
        recommendation["requires_purchase"] = True
    elif kind == "furniture":
        recommendation["moves_large_furniture"] = True
    elif kind == "count":
        value["recommendations"] = [dict(recommendation, recommendation_id=f"rec_{i}") for i in range(1, 7)]
    elif kind == "destination_reference":
        recommendation["destination_observation_id"] = "obs_99"
    elif kind == "destination_bbox":
        recommendation["destination_observation_id"] = "obs_1"
        value["observations"][0]["approximate_bbox"] = None
    elif kind == "material_advice":
        recommendation["action"] = "使用束帶整理線材。"
    with pytest.raises((ValidationError, AnalysisValidationError)):
        parse(value)
