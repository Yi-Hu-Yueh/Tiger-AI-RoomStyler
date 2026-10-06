from pathlib import Path


SCRIPT = (Path(__file__).parents[1] / "app" / "static" / "app.js").read_text(encoding="utf-8")
INDEX = (Path(__file__).parents[1] / "app" / "static" / "index.html").read_text(encoding="utf-8")


def test_safe_text_rendering_contract() -> None:
    assert ".textContent = text" in SCRIPT
    assert "innerHTML" not in SCRIPT


def test_stale_result_reset_and_request_association_contract() -> None:
    assert "selectionVersion += 1" in SCRIPT
    assert "clearResults();" in SCRIPT
    assert "snapshot.selectionVersion !== selectionVersion" in SCRIPT


def test_overlay_normalized_coordinate_conversion_contract() -> None:
    visual_plan = (Path(__file__).parents[1] / "app" / "static" / "visual_plan.js").read_text(encoding="utf-8")
    assert "box.x_min * 100" in visual_plan
    assert "(box.x_max - box.x_min) * 100" in visual_plan
    assert "(box.y_max - box.y_min) * 100" in visual_plan


def test_visual_plan_controls_and_safe_linking_contract() -> None:
    assert 'id="visual-action-plan"' in INDEX
    assert 'id="action-checklist"' in INDEX
    assert 'id="action-progress"' in INDEX
    assert "createCompletionState" in SCRIPT
    assert "focusRecommendation" in SCRIPT
    assert "innerHTML" not in SCRIPT
