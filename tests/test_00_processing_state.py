import json
from pathlib import Path
import shutil
import subprocess


MODULE = Path(__file__).resolve().parents[1] / "app" / "static" / "processing_state.js"


def test_error_stops_timer_hides_spinner_and_reenables_analyze_button():
    node = shutil.which("node")
    assert node, "Node.js is required for the deterministic processing-state test"
    script = r"""
const state = require(process.argv[1]);
const elements = {
  container: {hidden: true, dataset: {}},
  spinner: {hidden: true},
  text: {textContent: ""},
  analyzeButton: {disabled: false},
  fileInput: {disabled: false}
};
let now = 1000;
let tick;
const cleared = [];
const scheduler = {
  now: () => now,
  setInterval: (callback) => { tick = callback; return 77; },
  clearInterval: (timerId) => cleared.push(timerId)
};
const timer = state.begin(elements, scheduler);
now = 4250;
tick();
state.finish(elements, timer, "error", true, scheduler);
process.stdout.write(JSON.stringify({
  cleared,
  spinnerHidden: elements.spinner.hidden,
  text: elements.text.textContent,
  buttonDisabled: elements.analyzeButton.disabled,
  fileDisabled: elements.fileInput.disabled,
  statusState: elements.container.dataset.state
}));
"""
    completed = subprocess.run(
        [node, "-e", script, str(MODULE)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    result = json.loads(completed.stdout)
    assert result == {
        "cleared": [77],
        "spinnerHidden": True,
        "text": "分析失敗，請查看錯誤訊息。",
        "buttonDisabled": False,
        "fileDisabled": False,
        "statusState": "error",
    }
    assert "正在分析照片" not in result["text"]


def test_success_stops_timer_and_shows_final_non_active_state():
    node = shutil.which("node")
    assert node, "Node.js is required for the deterministic processing-state test"
    script = r"""
const state = require(process.argv[1]);
const elements = {
  container: {hidden: true, dataset: {}}, spinner: {hidden: true},
  text: {textContent: ""}, analyzeButton: {disabled: false}, fileInput: {disabled: false}
};
const cleared = [];
const scheduler = {now: () => 1, setInterval: () => 12, clearInterval: (id) => cleared.push(id)};
const timer = state.begin(elements, scheduler);
state.finish(elements, timer, "success", true, scheduler);
process.stdout.write(JSON.stringify({cleared, hidden: elements.spinner.hidden,
  text: elements.text.textContent, state: elements.container.dataset.state}));
"""
    completed = subprocess.run(
        [node, "-e", script, str(MODULE)], check=True, capture_output=True, text=True,
        encoding="utf-8", timeout=15
    )
    assert json.loads(completed.stdout) == {
        "cleared": [12], "hidden": True, "text": "分析完成。", "state": "success"
    }
