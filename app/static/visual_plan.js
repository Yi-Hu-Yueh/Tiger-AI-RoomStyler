"use strict";

(function exposeVisualPlan(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.RoomStylerVisualPlan = api;
})(typeof window === "undefined" ? null : window, function createVisualPlan() {
  const priorityRank = {high: 0, medium: 1, low: 2};
  const allowedStates = new Set(["pending", "completed", "skipped"]);

  function bboxToPercent(box) {
    return {
      left: box.x_min * 100,
      top: box.y_min * 100,
      width: (box.x_max - box.x_min) * 100,
      height: (box.y_max - box.y_min) * 100
    };
  }

  function boxCenterPercent(box) {
    return {
      x: ((box.x_min + box.x_max) / 2) * 100,
      y: ((box.y_min + box.y_max) / 2) * 100
    };
  }

  function orderRecommendations(recommendations) {
    return recommendations
      .map((recommendation, index) => ({recommendation, index}))
      .sort((left, right) =>
        (priorityRank[left.recommendation.priority] ?? 3)
        - (priorityRank[right.recommendation.priority] ?? 3)
        || left.index - right.index
      )
      .map((item) => item.recommendation);
  }

  function visualAction(recommendation, observationsById) {
    if (!recommendation.visual_action_available) {
      return {source: null, destination: null, arrow: null};
    }
    const source = recommendation.supporting_observation_ids
      .map((id) => observationsById[id])
      .find((observation) => observation && observation.approximate_bbox) || null;
    const destination = recommendation.destination_observation_id
      ? observationsById[recommendation.destination_observation_id] || null
      : null;
    const groundedDestination = destination && destination.approximate_bbox ? destination : null;
    return {
      source,
      destination: groundedDestination,
      arrow: source && groundedDestination
        ? {from: boxCenterPercent(source.approximate_bbox), to: boxCenterPercent(groundedDestination.approximate_bbox)}
        : null
    };
  }

  function createCompletionState(recommendationIds) {
    const states = new Map(recommendationIds.map((id) => [id, "pending"]));
    return {
      get: (id) => states.get(id),
      set(id, state) {
        if (!states.has(id) || !allowedStates.has(state)) return false;
        states.set(id, state);
        return true;
      },
      progress() {
        return {
          completed: [...states.values()].filter((state) => state === "completed").length,
          total: states.size
        };
      },
      snapshot: () => Object.fromEntries(states)
    };
  }

  return {bboxToPercent, boxCenterPercent, orderRecommendations, visualAction, createCompletionState};
});
