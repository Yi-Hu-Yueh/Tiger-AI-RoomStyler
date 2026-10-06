import json
from pathlib import Path
import shutil
import subprocess


MODULE = Path(__file__).resolve().parents[1] / "app" / "static" / "visual_plan.js"


def run_visual_plan_scenario() -> dict:
    node = shutil.which("node")
    assert node, "Node.js is required for the deterministic visual-plan test"
    script = r"""
const plan = require(process.argv[1]);
const observations = {
  obs_1: {observation_id: "obs_1", approximate_bbox: {x_min: .1, y_min: .2, x_max: .3, y_max: .6}},
  obs_2: {observation_id: "obs_2", approximate_bbox: {x_min: .6, y_min: .25, x_max: .9, y_max: .75}},
  obs_3: {observation_id: "obs_3", approximate_bbox: null}
};
const grounded = plan.visualAction({
  visual_action_available: true,
  supporting_observation_ids: ["obs_1"],
  destination_observation_id: "obs_2"
}, observations);
const unknownDestination = plan.visualAction({
  visual_action_available: true,
  supporting_observation_ids: ["obs_1"],
  destination_observation_id: "obs_99"
}, observations);
const unboxedDestination = plan.visualAction({
  visual_action_available: true,
  supporting_observation_ids: ["obs_1"],
  destination_observation_id: "obs_3"
}, observations);
const unavailable = plan.visualAction({
  visual_action_available: false,
  supporting_observation_ids: ["obs_1"],
  destination_observation_id: "obs_2"
}, observations);
const ordered = plan.orderRecommendations([
  {recommendation_id: "rec_low", priority: "low"},
  {recommendation_id: "rec_high_1", priority: "high"},
  {recommendation_id: "rec_medium", priority: "medium"},
  {recommendation_id: "rec_high_2", priority: "high"}
]).map((item) => item.recommendation_id);
const completion = plan.createCompletionState(["rec_1", "rec_2", "rec_3"]);
const invalidStateAccepted = completion.set("rec_1", "invented");
completion.set("rec_1", "completed");
completion.set("rec_2", "skipped");
process.stdout.write(JSON.stringify({
  box: plan.bboxToPercent(observations.obs_1.approximate_bbox),
  grounded,
  unknownDestination,
  unboxedDestination,
  unavailable,
  ordered,
  invalidStateAccepted,
  completion: completion.snapshot(),
  progress: completion.progress()
}));
"""
    completed = subprocess.run(
        [node, "-e", script, str(MODULE)], check=True, capture_output=True,
        text=True, encoding="utf-8", timeout=15
    )
    return json.loads(completed.stdout)


def test_responsive_source_and_destination_overlay_conversion() -> None:
    result = run_visual_plan_scenario()
    assert result["box"] == {"left": 10, "top": 20, "width": 20, "height": 40}
    assert result["grounded"]["arrow"] == {
        "from": {"x": 20, "y": 40},
        "to": {"x": 75, "y": 50},
    }


def test_no_fabricated_destination_arrows() -> None:
    result = run_visual_plan_scenario()
    assert result["unknownDestination"]["arrow"] is None
    assert result["unboxedDestination"]["arrow"] is None
    assert result["unavailable"] == {"source": None, "destination": None, "arrow": None}


def test_checklist_priority_order_and_local_completion_state() -> None:
    result = run_visual_plan_scenario()
    assert result["ordered"] == ["rec_high_1", "rec_high_2", "rec_medium", "rec_low"]
    assert result["invalidStateAccepted"] is False
    assert result["completion"] == {"rec_1": "completed", "rec_2": "skipped", "rec_3": "pending"}
    assert result["progress"] == {"completed": 1, "total": 3}
