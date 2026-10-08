import json
from pathlib import Path
import shutil
import subprocess


def test_browser_memory_keys_model_switch_requests_and_error_cleanup():
    node = shutil.which("node")
    assert node, "Node.js is required for the offline Web behavior test"
    script = r"""
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    value: '', hidden: true, disabled: false, textContent: '', handlers: {},
    classList: {toggle() {}}, dataset: {},
    addEventListener(type, callback) { this.handlers[type] = callback; },
    removeAttribute(name) { delete this[name]; }, replaceChildren() {}
  });
  return elements.get(id);
}
element('provider-model').value = 'z-ai/glm-5.3-flash';
const form = element('analysis-form');
form.elements = {
  consent: {checked: true}, allow_purchases: {checked: false},
  allow_moving_large_furniture: {checked: false}
};
class FormData {
  constructor(source) {
    this.values = new Map(source ? [['main_goal', 'declutter'], ['style', 'preserve_current']] : []);
  }
  get(key) { return this.values.get(key); }
  has(key) { return this.values.has(key); }
  set(key, value) { this.values.set(key, value); }
  append(key, value) { this.set(key, value); }
}
const requests = [];
const pageHandlers = {};
let finishes = 0;
let deferPreview = false;
let resolvePreview;
const response = (ok, payload) => ({ok, json: async () => payload});
const context = vm.createContext({
  document: {getElementById: element}, FormData, AbortController,
  window: {
    location: {protocol: 'https:', hostname: 'roomstyler.example'},
    addEventListener(type, fn) { pageHandlers[type] = fn; },
    RoomStylerProcessing: {
      begin(e) { e.analyzeButton.disabled = true; e.spinner.hidden = false; return 1; },
      finish(e) { finishes++; e.spinner.hidden = true; e.analyzeButton.disabled = false; },
      reset() {}
    }
  },
  fetch: async (url, options) => {
    if (url === '/health') return response(true, {provider: {configured: false}, image_provider: {configured: false}});
    requests.push({url, options});
    if (url === '/api/v1/analyze') return response(false, {detail: {message: '測試拒絕'}});
    if (deferPreview) return new Promise(resolve => { resolvePreview = resolve; });
    return response(true, {analysis_binding: 'binding', preview_data_url: 'data:image/png;base64,mock'});
  }
});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
const run = code => vm.runInContext(code, context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  run('validatedFile = {name: "room.jpg", size: 10}; refreshModelControls();');
  element('api-key').value = ' owner-nvidia-test-key ';
  await run('submitAnalysis()');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.headers['X-RoomStyler-API-Key'], 'owner-nvidia-test-key');
  assert(!JSON.stringify([...requests[0].options.body.values]).includes('test-key'));
  assert(!run('JSON.stringify(formSnapshot())').includes('test-key'));
  assert.equal(element('analyze-button').disabled, false);
  assert.equal(element('processing-spinner').hidden, true);
  assert.equal(element('api-key').disabled, false);
  assert.equal(run('activeRequest'), false);
  element('api-key').value = '';
  await run('submitAnalysis()');
  assert.equal(Object.keys(requests[1].options.headers).length, 0);

  run(`resultSnapshot = {selectionVersion, binding: 'binding',
    submittedConstraints: currentPreviewConstraints(),
    analysis: {input_suitability: {suitable: true}, recommendations: [{action: '整理'}]}};`);
  element('api-key').value = 'nvidia-old-key';
  element('provider-model').value = 'gpt-image-2.5-sunburst';
  element('provider-model').handlers.change();
  assert.equal(element('api-key').value, '');
  assert.equal(run('resultSnapshot.binding'), 'binding');
  assert.equal(element('analyze-button').disabled, true);
  assert.equal(element('generate-preview-button').disabled, true);
  element('api-key').value = 'owner-openai-test-key';
  element('api-key').handlers.input();
  assert.equal(element('generate-preview-button').disabled, false);
  await run('submitAnalysis()');
  assert.equal(requests.length, 2); // OpenAI cannot invoke NVIDIA analysis.
  await run('submitOrganizedPreview()');
  assert.equal(requests[2].options.headers['X-RoomStyler-API-Key'], 'owner-openai-test-key');
  assert(!JSON.stringify([...requests[2].options.body.values]).includes('test-key'));
  assert.equal(element('organized-preview-result').hidden, false);
  assert.equal(element('provider-model').disabled, false);

  deferPreview = true;
  const pending = run('submitOrganizedPreview()');
  assert.equal(element('api-key').disabled, true);
  run('selectionVersion += 1; clearResults();');
  resolvePreview(response(true, {analysis_binding: 'binding', preview_data_url: 'stale'}));
  await pending;
  assert.equal(element('organized-preview-result').hidden, true);
  assert.equal(element('generate-preview-button').disabled, true);
  pageHandlers.pagehide();
  assert.equal(element('api-key').value, '');

  element('provider-model').value = 'z-ai/glm-5.3-flash';
  element('provider-model').handlers.change();
  element('api-key').value = 'owner-nvidia-test-key';
  context.window.location.protocol = 'http:';
  const count = requests.length;
  await run('submitAnalysis()');
  assert.equal(requests.length, count); // Never send the entered secret over public HTTP.
  assert(element('error-box').textContent.includes('HTTPS'));
  assert.equal(element('analyze-button').disabled, false);
  assert.equal(element('processing-spinner').hidden, true);
  assert.equal(finishes, 3);
  context.window.location.hostname = '127.0.0.1';
  assert.equal(run('requestKeyHeaders()["X-RoomStyler-API-Key"]'), 'owner-nvidia-test-key');
  process.stdout.write(JSON.stringify({passed: true}));
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
"""
    completed = subprocess.run(
        [node, "-e", script, str(Path(__file__).parents[1] / "app/static/app.js")],
        check=True, capture_output=True, text=True, encoding="utf-8", timeout=15,
    )
    assert json.loads(completed.stdout) == {"passed": True}
