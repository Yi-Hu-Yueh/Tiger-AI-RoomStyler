from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image


def make_image(fmt: str = "PNG", size: tuple[int, int] = (80, 60), color=(80, 120, 160)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def valid_analysis_dict() -> dict:
    return {
        "input_suitability": {"suitable": True, "explanation": "照片可清楚看見室內區域。"},
        "room_summary": "照片顯示一個可分析的室內區域。",
        "observations": [
            {
                "observation_id": "obs_1",
                "visible_item_or_area": "桌面",
                "position_description": "照片中央偏左",
                "visible_evidence": "桌面上可見數件物品。",
                "uncertain": False,
                "approximate_bbox": {"x_min": 0.1, "y_min": 0.2, "x_max": 0.6, "y_max": 0.7},
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "rec_1",
                "priority": "high",
                "supporting_observation_ids": ["obs_1"],
                "target_item_or_area": "桌面物品",
                "action": "將同類物品集中在桌面同一側。",
                "destination_or_arrangement": "桌面右側的可見空區",
                "practical_reason": "讓中央工作區更容易使用。",
                "aesthetic_rationale": "集中擺放可減少視覺分散。",
                "requires_purchase": False,
                "moves_large_furniture": False,
                "requires_confirmation": True,
                "confirmation_needed": "確認右側空區不影響現有用途。",
                "destination_observation_id": None,
                "visual_action_available": True,
                "visual_action_note": "在照片上的桌面區域集中同類物品。",
                "requires_existing_materials": False,
                "no_purchase_alternative": None,
            }
        ],
        "uncertainties": ["照片外區域不可見。"],
        "limitations": ["無法由單張照片確認實際尺寸。"],
    }
