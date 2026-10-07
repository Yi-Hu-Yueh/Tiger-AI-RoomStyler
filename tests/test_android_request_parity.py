"""Keep the offline Android golden request tied to the actual Web builder."""
import json
from pathlib import Path

from app.providers.nvidia_nim import DEFAULT_MODEL, NvidiaNimVisionProvider
from app.schemas import AnalyzeConstraints


def test_android_golden_request_matches_actual_web_builder():
    path = Path(__file__).parents[1] / "android/app/src/test/resources/web_request.json"
    expected = json.loads(path.read_text(encoding="utf-8"))
    provider = NvidiaNimVisionProvider(None, DEFAULT_MODEL, 180, 16384)
    actual = provider.build_request(
        bytes([0, 255, 1, 2, 3, 127]), "image/jpeg",
        AnalyzeConstraints(main_goal="both", style="preserve_current_style", consent=True),
    )
    assert actual == expected
