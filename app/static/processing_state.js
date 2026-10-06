"use strict";

(function exposeProcessingState(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.RoomStylerProcessing = api;
})(typeof window === "undefined" ? null : window, function createProcessingState() {
  function defaultScheduler() {
    return {
      now: () => performance.now(),
      setInterval: (callback, milliseconds) => window.setInterval(callback, milliseconds),
      clearInterval: (timerId) => window.clearInterval(timerId)
    };
  }

  function begin(elements, scheduler = defaultScheduler()) {
    const started = scheduler.now();
    elements.container.hidden = false;
    elements.container.dataset.state = "active";
    elements.spinner.hidden = false;
    elements.text.textContent = "正在分析照片… 0 秒";
    elements.analyzeButton.disabled = true;
    elements.fileInput.disabled = true;
    return scheduler.setInterval(() => {
      const seconds = Math.floor((scheduler.now() - started) / 1000);
      elements.text.textContent = `正在分析照片… ${seconds} 秒`;
    }, 250);
  }

  function finish(elements, timerId, outcome, canAnalyze, scheduler = defaultScheduler()) {
    if (timerId !== null && timerId !== undefined) scheduler.clearInterval(timerId);
    elements.spinner.hidden = true;
    elements.fileInput.disabled = false;
    elements.analyzeButton.disabled = !canAnalyze;
    elements.container.hidden = false;
    elements.container.dataset.state = outcome;
    elements.text.textContent = outcome === "success"
      ? "分析完成。"
      : "分析失敗，請查看錯誤訊息。";
  }

  function reset(elements) {
    elements.container.hidden = true;
    elements.container.dataset.state = "idle";
    elements.spinner.hidden = true;
    elements.text.textContent = "";
  }

  return {begin, finish, reset};
});
