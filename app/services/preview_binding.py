from __future__ import annotations

import hashlib
import hmac

from app.schemas import AnalyzeConstraints, RoomAnalysis


def create_analysis_binding(
    image_bytes: bytes,
    analysis: RoomAnalysis,
    constraints: AnalyzeConstraints,
) -> str:
    """Bind an analysis to its processed image and exact constraints."""
    digest = hashlib.sha256()
    digest.update(image_bytes)
    digest.update(b"\0analysis\0")
    digest.update(analysis.model_dump_json().encode("utf-8"))
    digest.update(b"\0constraints\0")
    digest.update(constraints.model_dump_json().encode("utf-8"))
    return digest.hexdigest()


def binding_matches(
    supplied: str,
    image_bytes: bytes,
    analysis: RoomAnalysis,
    constraints: AnalyzeConstraints,
) -> bool:
    expected = create_analysis_binding(image_bytes, analysis, constraints)
    return hmac.compare_digest(supplied, expected)
