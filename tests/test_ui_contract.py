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


def test_phase2a_preview_ui_and_unverified_notice_are_visible() -> None:
    assert 'id="generate-preview-button"' in INDEX
    assert '產生 AI 整理預覽' in INDEX
    assert 'id="organized-preview-result"' in INDEX
    assert '⚠ 此功能尚未實際測試' in INDEX
    assert 'AI 整理預覽為生成式模擬結果，不代表實際整理後一定會呈現相同效果。' in INDEX


def test_preview_requires_current_bound_analysis_and_rejects_stale_ui_results() -> None:
    assert 'previewContextIsCurrent' in SCRIPT
    assert 'analysis_binding' in SCRIPT
    assert 'payload.analysis_binding !== snapshot.binding' in SCRIPT
    assert 'snapshot.selectionVersion !== selectionVersion' in SCRIPT
    assert '/api/v1/organized-preview' in SCRIPT
