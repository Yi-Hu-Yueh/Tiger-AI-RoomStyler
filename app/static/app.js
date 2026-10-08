"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("analysis-form");
const fileInput = byId("room-image");
const analyzeButton = byId("analyze-button");
const errorBox = byId("error-box");
const modelSelect = byId("provider-model");
const apiKeyInput = byId("api-key");
const NVIDIA_MODEL = "z-ai/glm-5.3-flash";
const OPENAI_MODEL = "gpt-image-2.5-sunburst";
const processingElements = {
  container: byId("processing-status"),
  spinner: byId("processing-spinner"),
  text: byId("processing-text"),
  analyzeButton,
  fileInput
};
let validatedFile = null;
let selectionVersion = 0;
let activeRequest = false;
let resultSnapshot = null;
let actionCompletionState = null;
let imageProviderConfigured = false;
let analysisProviderConfigured = false;
let activePreviewController = null;
let previewRequestVersion = 0;

function requestKeyHeaders() {
  const key = apiKeyInput.value.trim();
  if (!key) return {};
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
  if (window.location.protocol !== "https:" && !local) {
    throw new Error("為保護 API_KEY，請使用 HTTPS 網頁；本機 localhost 測試除外。");
  }
  return {"X-RoomStyler-API-Key": key};
}

function previewKeyAvailable() {
  return modelSelect.value === OPENAI_MODEL && (Boolean(apiKeyInput.value.trim()) || imageProviderConfigured);
}

function refreshModelControls() {
  const busy = activeRequest || Boolean(activePreviewController);
  modelSelect.disabled = busy;
  apiKeyInput.disabled = busy;
  analyzeButton.disabled = busy || !validatedFile || modelSelect.value !== NVIDIA_MODEL;
  byId("retry-button").disabled = analyzeButton.disabled;
  const status = byId("provider-status");
  const userKey = modelSelect.value === NVIDIA_MODEL && Boolean(apiKeyInput.value.trim());
  status.textContent = userKey ? "NVIDIA 將使用本次輸入金鑰（連線未驗證）"
    : (analysisProviderConfigured ? "NVIDIA 伺服器金鑰已設定（連線未驗證）" : "NVIDIA：可輸入 API_KEY，或設定伺服器金鑰");
  status.classList.toggle("ok", userKey || analysisProviderConfigured);
  status.classList.toggle("warn", !userKey && !analysisProviderConfigured);
  const imageStatus = byId("image-provider-status");
  const userImageKey = modelSelect.value === OPENAI_MODEL && Boolean(apiKeyInput.value.trim());
  imageStatus.textContent = userImageKey ? "OpenAI 將使用本次輸入金鑰（尚未實際測試）"
    : (imageProviderConfigured ? "OpenAI 伺服器金鑰已設定（尚未實際測試）" : "需要 OpenAI API_KEY");
  imageStatus.classList.toggle("ok", userImageKey || imageProviderConfigured);
  imageStatus.classList.toggle("warn", !userImageKey && !imageProviderConfigured);
  refreshPreviewAvailability();
}

modelSelect.addEventListener("change", () => {
  apiKeyInput.value = "";
  clearGeneratedPreview();
  errorBox.hidden = true;
});
apiKeyInput.addEventListener("input", refreshModelControls);
window.addEventListener("pagehide", () => {
  apiKeyInput.value = "";
  refreshModelControls();
});

function textElement(tag, text, className = "") {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function bboxToPercent(box) {
  return window.RoomStylerVisualPlan.bboxToPercent(box);
}

function clearResults() {
  resultSnapshot = null;
  clearGeneratedPreview();
  byId("results").hidden = true;
  byId("overlay-layer").replaceChildren();
  byId("action-marker-layer").replaceChildren();
  byId("action-arrows").replaceChildren();
  byId("action-checklist").replaceChildren();
  byId("action-progress").textContent = "0 / 0 已完成";
  byId("recommendations").replaceChildren();
  byId("observations").replaceChildren();
  actionCompletionState = null;
}

function currentPreviewConstraints() {
  const snapshot = formSnapshot();
  return {...snapshot, consent: form.elements.consent.checked};
}

function previewContextIsCurrent() {
  return Boolean(
    resultSnapshot && validatedFile &&
    resultSnapshot.selectionVersion === selectionVersion &&
    JSON.stringify(resultSnapshot.submittedConstraints) === JSON.stringify(currentPreviewConstraints())
  );
}

function refreshPreviewAvailability() {
  const button = byId("generate-preview-button");
  if (modelSelect.value !== OPENAI_MODEL) {
    button.disabled = true;
    byId("organized-preview-status").textContent = "產生預覽請選擇 OpenAI 模型；房間分析請選擇 NVIDIA 模型。";
    return;
  }
  if (!previewKeyAvailable()) {
    button.disabled = true;
    byId("organized-preview-status").textContent = "請輸入 OpenAI API_KEY，或設定伺服器 OPENAI_API_KEY；房間分析仍可正常使用。";
    return;
  }
  if (!resultSnapshot) {
    button.disabled = true;
    byId("organized-preview-status").textContent = "請先完成房間分析。";
    return;
  }
  if (!resultSnapshot.analysis?.input_suitability?.suitable || !resultSnapshot.analysis?.recommendations?.length) {
    button.disabled = true;
    byId("organized-preview-status").textContent = "本次分析沒有可供產生預覽的核准行動。";
    return;
  }
  if (!previewContextIsCurrent()) {
    button.disabled = true;
    byId("organized-preview-status").textContent = "照片或限制已變更，請重新分析後再產生預覽。";
    return;
  }
  button.disabled = activeRequest || Boolean(activePreviewController);
  byId("organized-preview-status").textContent = activePreviewController
    ? "正在產生 AI 整理預覽…"
    : (byId("organized-preview-result").hidden
      ? "已綁定目前照片、建議與限制，可產生一張預覽。"
      : "AI 整理預覽已產生；請對照原照片人工確認。");
}

function clearGeneratedPreview() {
  previewRequestVersion += 1;
  if (activePreviewController) activePreviewController.abort();
  activePreviewController = null;
  byId("organized-preview-result").hidden = true;
  byId("organized-preview-image").removeAttribute("src");
  byId("organized-preview-error").hidden = true;
  refreshModelControls();
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function resetProcessingStatus() {
  window.RoomStylerProcessing.reset(processingElements);
}

function apiError(payload, fallback) {
  return payload?.detail?.message || payload?.error?.message || fallback;
}

async function validatePreview(file, version) {
  const body = new FormData();
  body.append("image", file, file.name);
  const response = await fetch("/api/v1/preview", {method: "POST", body});
  const payload = await response.json().catch(() => ({}));
  if (version !== selectionVersion) return;
  if (!response.ok) throw new Error(apiError(payload, "照片驗證失敗。"));
  validatedFile = file;
  byId("room-preview").src = payload.preview_data_url;
  byId("image-meta").textContent = `分析版本：${payload.image.width} × ${payload.image.height}，${payload.image.mime_type}${payload.image.resized_for_provider ? "（已等比例縮小）" : ""}`;
  byId("preview-area").hidden = false;
  byId("empty-state").hidden = true;
  byId("preview-message").textContent = "照片已驗證；此預覽與送往 NVIDIA 雲端服務的方向、裁切範圍及比例相同。";
  refreshModelControls();
}

fileInput.addEventListener("change", async () => {
  selectionVersion += 1;
  const version = selectionVersion;
  validatedFile = null;
  analyzeButton.disabled = true;
  errorBox.hidden = true;
  resetProcessingStatus();
  clearResults();
  const file = fileInput.files?.[0];
  if (!file) {
    byId("preview-area").hidden = true;
    byId("empty-state").hidden = false;
    return;
  }
  byId("preview-message").textContent = "正在驗證並校正照片…";
  try { await validatePreview(file, version); }
  catch (error) { if (version === selectionVersion) showError(error.message); }
});

function formSnapshot() {
  const data = new FormData(form);
  return {
    main_goal: data.get("main_goal"), style: data.get("style"),
    allow_moving_large_furniture: data.has("allow_moving_large_furniture"),
    allow_purchases: data.has("allow_purchases"),
    preserve_items: data.get("preserve_items") || null,
    additional_constraints: data.get("additional_constraints") || null
  };
}

function renderList(id, values, emptyText) {
  const list = byId(id); list.replaceChildren();
  (values.length ? values : [emptyText]).forEach((value) => list.append(textElement("li", value)));
}

function svgElement(tag, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, String(value)));
  return element;
}

function updateActionProgress() {
  const progress = actionCompletionState?.progress() || {completed: 0, total: 0};
  byId("action-progress").textContent = `${progress.completed} / ${progress.total} 已完成`;
}

function applyCompletionState(recommendationId, state) {
  if (!actionCompletionState?.set(recommendationId, state)) return;
  const checklistItem = byId(`checklist-${recommendationId}`);
  const card = byId(`recommendation-${recommendationId}`);
  [checklistItem, card].forEach((element) => {
    if (!element) return;
    element.classList.toggle("is-completed", state === "completed");
    element.classList.toggle("is-skipped", state === "skipped");
  });
  updateActionProgress();
}

function focusRecommendation(recommendationId) {
  const card = byId(`recommendation-${recommendationId}`);
  if (!card) return;
  card.scrollIntoView({behavior: "smooth", block: "center"});
  card.focus({preventScroll: true});
  card.classList.add("is-linked");
  window.setTimeout(() => card.classList.remove("is-linked"), 1200);
}

function renderArrow(arrow, actionNumber, recommendationId) {
  const svg = byId("action-arrows");
  const line = svgElement("line", {
    x1: arrow.from.x,
    y1: arrow.from.y,
    x2: arrow.to.x,
    y2: arrow.to.y,
    class: "action-arrow-line",
    "data-action-number": actionNumber,
    "data-recommendation-id": recommendationId
  });
  svg.append(line);
}

function initializeArrowLayer() {
  const svg = byId("action-arrows");
  const definitions = svgElement("defs");
  const marker = svgElement("marker", {
    id: "visual-action-arrowhead",
    markerWidth: 8,
    markerHeight: 8,
    refX: 7,
    refY: 4,
    orient: "auto",
    markerUnits: "strokeWidth"
  });
  marker.append(svgElement("path", {d: "M 0 0 L 8 4 L 0 8 z", fill: "#e95f37"}));
  definitions.append(marker);
  svg.append(definitions);
}

function renderVisualMarker(rec, actionNumber, visual) {
  if (!visual.source) return;
  const sourceBox = bboxToPercent(visual.source.approximate_bbox);
  const highlight = textElement("div", "", "visual-source-highlight");
  Object.assign(highlight.style, {
    left: `${sourceBox.left}%`, top: `${sourceBox.top}%`,
    width: `${sourceBox.width}%`, height: `${sourceBox.height}%`
  });
  highlight.setAttribute("aria-hidden", "true");
  byId("action-marker-layer").append(highlight);

  const center = window.RoomStylerVisualPlan.boxCenterPercent(visual.source.approximate_bbox);
  const marker = textElement("button", String(actionNumber), "action-marker");
  marker.type = "button";
  marker.style.left = `${center.x}%`;
  marker.style.top = `${center.y}%`;
  marker.setAttribute("aria-label", `行動 ${actionNumber}：前往${rec.target_item_or_area}建議`);
  marker.setAttribute("aria-controls", `recommendation-${rec.recommendation_id}`);
  marker.addEventListener("click", () => focusRecommendation(rec.recommendation_id));
  byId("action-marker-layer").append(marker);

  if (visual.destination) {
    const destinationBox = bboxToPercent(visual.destination.approximate_bbox);
    const destination = textElement("div", "", "visual-destination-highlight");
    Object.assign(destination.style, {
      left: `${destinationBox.left}%`, top: `${destinationBox.top}%`,
      width: `${destinationBox.width}%`, height: `${destinationBox.height}%`
    });
    destination.setAttribute("aria-hidden", "true");
    byId("action-marker-layer").append(destination);
  }
  if (visual.arrow) renderArrow(visual.arrow, actionNumber, rec.recommendation_id);
}

function makeCompletionControl(rec) {
  const label = textElement("label", "處理狀態", "completion-label");
  const select = document.createElement("select");
  select.setAttribute("aria-label", `${rec.target_item_or_area}處理狀態`);
  [
    ["pending", "未處理"],
    ["completed", "已完成"],
    ["skipped", "暫不處理"]
  ].forEach(([value, text]) => {
    const option = textElement("option", text);
    option.value = value;
    select.append(option);
  });
  select.addEventListener("change", () => applyCompletionState(rec.recommendation_id, select.value));
  label.append(select);
  return label;
}

function renderResults(payload, snapshot) {
  clearGeneratedPreview();
  const analysis = payload.analysis;
  const observationsById = Object.fromEntries(analysis.observations.map((observation) => [observation.observation_id, observation]));
  const orderedRecommendations = window.RoomStylerVisualPlan.orderRecommendations(analysis.recommendations);
  actionCompletionState = window.RoomStylerVisualPlan.createCompletionState(
    orderedRecommendations.map((recommendation) => recommendation.recommendation_id)
  );
  byId("room-preview").src = payload.preview_data_url;
  byId("room-summary").textContent = analysis.room_summary;
  const recommendations = byId("recommendations"); recommendations.replaceChildren();
  const checklist = byId("action-checklist"); checklist.replaceChildren();
  byId("action-marker-layer").replaceChildren();
  byId("action-arrows").replaceChildren();
  initializeArrowLayer();
  orderedRecommendations.forEach((rec, index) => {
    const actionNumber = index + 1;
    const visual = window.RoomStylerVisualPlan.visualAction(rec, observationsById);
    const card = textElement("article", "", "card");
    card.id = `recommendation-${rec.recommendation_id}`;
    card.tabIndex = -1;
    const title = textElement("h4", rec.target_item_or_area);
    title.prepend(textElement("span", String(actionNumber), "action-number"));
    title.prepend(textElement("span", ({high:"高優先",medium:"中優先",low:"低優先"})[rec.priority], `badge ${rec.priority}`));
    card.append(title, textElement("p", rec.action), textElement("p", `實際理由：${rec.practical_reason}`));
    if (rec.destination_or_arrangement) card.append(textElement("p", `位置／安排：${rec.destination_or_arrangement}`));
    if (rec.aesthetic_rationale) card.append(textElement("p", `視覺考量：${rec.aesthetic_rationale}`));
    if (rec.requires_confirmation) card.append(textElement("p", `執行前確認：${rec.confirmation_needed}`));
    if (rec.no_purchase_alternative) card.append(textElement("p", `免購買替代：${rec.no_purchase_alternative}`));
    const visualMessage = visual.source
      ? (visual.arrow ? "照片已標示來源與可見目的地。" : (rec.visual_action_note || "照片已標示來源；目的地需由屋主確認。"))
      : (rec.visual_action_note || rec.confirmation_needed || "缺少足夠的照片座標，保留為文字建議。 ");
    card.append(textElement("p", `視覺行動：${visualMessage}`, visual.source ? "visual-note" : "visual-note unavailable"));
    card.append(textElement("div", `證據：${rec.supporting_observation_ids.join("、") || "無直接觀察引用"}`, "hint"));
    recommendations.append(card);

    const item = document.createElement("li");
    item.id = `checklist-${rec.recommendation_id}`;
    item.className = "checklist-item";
    const link = textElement("button", `${actionNumber}. ${rec.action}`, "checklist-link");
    link.type = "button";
    link.addEventListener("click", () => focusRecommendation(rec.recommendation_id));
    item.append(link, makeCompletionControl(rec));
    if (!visual.arrow) item.append(textElement("span", visualMessage, "checklist-note"));
    checklist.append(item);
    renderVisualMarker(rec, actionNumber, visual);
  });
  if (!analysis.recommendations.length) recommendations.append(textElement("p", "目前沒有足夠證據支持具體建議。", "hint"));
  if (!analysis.recommendations.length) checklist.append(textElement("li", "目前沒有可執行的行動。", "hint"));
  updateActionProgress();

  const observations = byId("observations"); observations.replaceChildren();
  const overlay = byId("overlay-layer"); overlay.replaceChildren();
  analysis.observations.forEach((obs, index) => {
    const card = textElement("article", "", "card");
    const title = textElement("h4", obs.visible_item_or_area);
    title.prepend(textElement("span", String(index + 1), "evidence-number"));
    card.append(title, textElement("p", obs.position_description), textElement("p", `可見證據：${obs.visible_evidence}`));
    if (obs.uncertain) card.append(textElement("span", "此觀察有不確定性", "badge"));
    observations.append(card);
    if (obs.approximate_bbox) {
      const rect = textElement("div", "", "overlay");
      const p = bboxToPercent(obs.approximate_bbox);
      Object.assign(rect.style, {left:`${p.left}%`, top:`${p.top}%`, width:`${p.width}%`, height:`${p.height}%`});
      rect.append(textElement("span", String(index + 1)));
      rect.setAttribute("aria-label", `照片觀察證據 ${index + 1}`);
      overlay.append(rect);
    }
  });
  renderList("uncertainties", analysis.uncertainties, "未列出其他不確定事項。");
  renderList("limitations", analysis.limitations, "未列出其他分析限制。");
  byId("result-context").textContent = `結果綁定：${snapshot.fileName}（${snapshot.fileSize} 位元組）｜目標 ${snapshot.constraints.main_goal}｜風格 ${snapshot.constraints.style}｜購買 ${snapshot.constraints.allow_purchases ? "允許" : "不允許"}｜移動大型家具 ${snapshot.constraints.allow_moving_large_furniture ? "允許" : "不允許"}`;
  byId("results").hidden = false;
  refreshPreviewAvailability();
}

async function submitAnalysis() {
  if (activeRequest || activePreviewController || !validatedFile || modelSelect.value !== NVIDIA_MODEL) return;
  if (!form.elements.consent.checked) { showError("請先閱讀並勾選雲端處理同意聲明。"); return; }
  activeRequest = true; errorBox.hidden = true;
  const timer = window.RoomStylerProcessing.begin(processingElements);
  refreshModelControls();
  let outcome = "error";
  const snapshot = {fileName: validatedFile.name, fileSize: validatedFile.size, selectionVersion, constraints: formSnapshot()};
  const body = new FormData(form); body.set("image", validatedFile, validatedFile.name);
  for (const name of ["allow_moving_large_furniture", "allow_purchases", "consent"]) body.set(name, form.elements[name].checked ? "true" : "false");
  try {
    const response = await fetch("/api/v1/analyze", {method:"POST", body, headers: requestKeyHeaders()});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiError(payload, "分析失敗，請稍後重試。"));
    if (snapshot.selectionVersion !== selectionVersion) return;
    resultSnapshot = {
      ...snapshot,
      analysis: payload.analysis,
      submittedConstraints: payload.submitted_constraints,
      binding: payload.analysis_binding
    };
    renderResults(payload, resultSnapshot); outcome = "success";
  } catch (error) { showError(error.message); }
  finally {
    activeRequest = false;
    window.RoomStylerProcessing.finish(processingElements, timer, outcome, Boolean(validatedFile));
    refreshModelControls();
  }
}

form.addEventListener("submit", (event) => { event.preventDefault(); submitAnalysis(); });
form.addEventListener("input", () => {
  if (resultSnapshot && !previewContextIsCurrent()) clearGeneratedPreview();
  else refreshModelControls();
});
byId("retry-button").addEventListener("click", submitAnalysis);

async function submitOrganizedPreview() {
  if (activeRequest || activePreviewController || !previewKeyAvailable() || !previewContextIsCurrent()) {
    refreshPreviewAvailability();
    return;
  }
  const requestVersion = ++previewRequestVersion;
  const snapshot = {
    selectionVersion,
    binding: resultSnapshot.binding,
    analysis: resultSnapshot.analysis,
    constraints: resultSnapshot.submittedConstraints,
    file: validatedFile
  };
  const controller = new AbortController();
  activePreviewController = controller;
  byId("organized-preview-error").hidden = true;
  byId("organized-preview-result").hidden = true;
  refreshModelControls();
  const body = new FormData();
  body.append("image", snapshot.file, snapshot.file.name);
  body.append("analysis_json", JSON.stringify(snapshot.analysis));
  body.append("constraints_json", JSON.stringify(snapshot.constraints));
  body.append("analysis_binding", snapshot.binding);
  try {
    const response = await fetch("/api/v1/organized-preview", {
      method: "POST", body, signal: controller.signal, headers: requestKeyHeaders()
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(apiError(payload, "無法產生 AI 整理預覽。"));
    if (
      requestVersion !== previewRequestVersion ||
      snapshot.selectionVersion !== selectionVersion ||
      snapshot.binding !== resultSnapshot?.binding ||
      payload.analysis_binding !== snapshot.binding
    ) return;
    byId("organized-preview-image").src = payload.preview_data_url;
    byId("organized-preview-result").hidden = false;
    byId("organized-preview-status").textContent = "AI 整理預覽已產生；請對照原照片人工確認。";
  } catch (error) {
    if (error.name !== "AbortError" && requestVersion === previewRequestVersion) {
      byId("organized-preview-error").textContent = error.message;
      byId("organized-preview-error").hidden = false;
      byId("organized-preview-status").textContent = "AI 整理預覽產生失敗。";
    }
  } finally {
    if (requestVersion === previewRequestVersion) {
      activePreviewController = null;
      refreshModelControls();
    }
  }
}

byId("generate-preview-button").addEventListener("click", submitOrganizedPreview);

fetch("/health").then((r) => r.json()).then((health) => {
  analysisProviderConfigured = Boolean(health.provider?.configured);
  imageProviderConfigured = Boolean(health.image_provider?.configured);
  refreshModelControls();
}).catch(() => { byId("provider-status").textContent = "無法取得服務狀態"; });

refreshModelControls();

window.RoomStylerHelpers = {bboxToPercent, textElement, clearResults};
