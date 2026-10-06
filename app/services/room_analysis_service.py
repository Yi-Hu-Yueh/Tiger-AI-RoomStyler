from __future__ import annotations

import re

from pydantic import ValidationError

from app.providers.nvidia_nim import NvidiaNimVisionProvider, ProviderError
from app.schemas import AnalyzeConstraints, RoomAnalysis
from app.services.image_service import ProcessedImage


class AnalysisValidationError(ValueError):
    pass


MATERIAL_TERMS = re.compile(r"束帶|固定夾|線夾|理線器|收納盒|整理盒|收納箱|置物盒|盒子|收納用品|整理用品")
OWNERSHIP_CONDITION = re.compile(r"(?:若|如果|僅限).{0,8}(?:已擁有|擁有|已有|現有|手邊|現場|原有)|使用(?:已有|現有|手邊|現場|原有)")
PURCHASE_TERMS = re.compile(r"購買|添購|新買|買入|取得新的|準備新的")


def _requires_new_purchase(text: str) -> bool:
    without_negations = re.sub(r"(?:不|無|毋)(?:需|需要|必須|必)購買|不必購買|不得購買", "", text)
    return bool(PURCHASE_TERMS.search(without_negations))


def validate_semantics(analysis: RoomAnalysis, constraints: AnalyzeConstraints) -> None:
    observation_ids = [item.observation_id for item in analysis.observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise AnalysisValidationError("AI 回應包含重複的觀察識別碼。")
    recommendation_ids = [item.recommendation_id for item in analysis.recommendations]
    if len(recommendation_ids) != len(set(recommendation_ids)):
        raise AnalysisValidationError("AI 回應包含重複的建議識別碼。")
    known = set(observation_ids)
    observations_by_id = {item.observation_id: item for item in analysis.observations}
    for recommendation in analysis.recommendations:
        unknown = set(recommendation.supporting_observation_ids) - known
        if unknown:
            raise AnalysisValidationError("AI 建議引用了不存在的照片觀察證據。")
        if not constraints.allow_purchases and recommendation.requires_purchase:
            raise AnalysisValidationError("AI 建議違反『不購買物品』限制。")
        recommendation_text = " ".join(
            value for value in (
                recommendation.action,
                recommendation.destination_or_arrangement,
                recommendation.visual_action_note,
                recommendation.no_purchase_alternative,
            ) if value
        )
        mentions_material = bool(MATERIAL_TERMS.search(recommendation_text))
        if not constraints.allow_purchases and _requires_new_purchase(recommendation_text):
            raise AnalysisValidationError("AI 建議在不購買模式要求取得新物品或材料。")
        if not constraints.allow_purchases and mentions_material:
            if not recommendation.requires_existing_materials:
                raise AnalysisValidationError("不購買模式提及整理材料時，必須標示僅使用現有材料。")
            if not OWNERSHIP_CONDITION.search(recommendation_text):
                raise AnalysisValidationError("不購買模式的材料建議必須明確以使用者已擁有為條件。")
            if not recommendation.no_purchase_alternative:
                raise AnalysisValidationError("不購買模式的材料建議必須提供無材料替代方案。")
        if not constraints.allow_moving_large_furniture and recommendation.moves_large_furniture:
            raise AnalysisValidationError("AI 建議違反『不移動大型家具』限制。")
        destination_id = recommendation.destination_observation_id
        if destination_id is not None:
            if destination_id not in known:
                raise AnalysisValidationError("AI 建議引用了不存在的目的地觀察。")
            if observations_by_id[destination_id].approximate_bbox is None:
                raise AnalysisValidationError("視覺目的地缺少可驗證的照片邊界框。")
            if not recommendation.visual_action_available:
                raise AnalysisValidationError("視覺目的地只能用於可顯示的視覺行動。")
        if recommendation.visual_action_available:
            has_source_box = any(
                observations_by_id[item_id].approximate_bbox is not None
                for item_id in recommendation.supporting_observation_ids
            )
            if not has_source_box:
                raise AnalysisValidationError("視覺行動缺少有邊界框的來源觀察。")
    if len(analysis.recommendations) > 5:
        raise AnalysisValidationError("AI 回應超過五項建議上限。")


async def analyze_room(
    provider: NvidiaNimVisionProvider,
    image: ProcessedImage,
    constraints: AnalyzeConstraints,
) -> RoomAnalysis:
    raw = await provider.analyze(image.data, image.mime_type, constraints)
    try:
        analysis = RoomAnalysis.model_validate_json(raw)
    except ValidationError as exc:
        raise AnalysisValidationError("AI 回應不符合必要的結構化格式。") from exc
    validate_semantics(analysis, constraints)
    return analysis


__all__ = ["AnalysisValidationError", "ProviderError", "analyze_room", "validate_semantics"]
