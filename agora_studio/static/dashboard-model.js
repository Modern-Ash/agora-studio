"use strict";

(function exposeDashboardModel(root) {
  function workKey(work) {
    return `${work.swarm_id}/${work.id}`;
  }

  function attentionKeys(overview, name) {
    const values = overview?.status?.attention?.[name];
    return new Set(Array.isArray(values) ? values : []);
  }

  function isWorkInProgress(work, overview) {
    return attentionKeys(overview, "active-work").has(workKey(work));
  }

  function isBlocked(work, overview) {
    return attentionKeys(overview, "blocked-work").has(workKey(work));
  }

  function swarmAssignments(work, swarms) {
    const swarm = (swarms || []).find((candidate) => candidate.id === work?.swarm_id);
    return Object.entries(swarm?.assignments || {}).map(([role, actor]) => ({ role, actor }));
  }

  function decisionProjection(detail) {
    return detail?.control?.gate_decision_options || null;
  }

  function decisionOptions(detail) {
    const options = decisionProjection(detail)?.options;
    return Array.isArray(options) ? options : [];
  }

  function optionKey(option) {
    return [
      option.transition_source,
      option.transition_target,
      option.gate_id,
      option.decision,
      option.role_id,
      option.actor_id || "unassigned",
    ].join("/");
  }

  function findOption(detail, key) {
    return decisionOptions(detail).find((option) => optionKey(option) === key) || null;
  }

  function gateCount(detail) {
    return new Set(decisionOptions(detail).map((option) => option.gate_id)).size;
  }

  function hasEvidenceBlocker(detail) {
    return decisionOptions(detail).some((option) =>
      (option.blockers || []).some((blocker) => blocker?.category === "evidence"));
  }

  function stateOrder(work, details) {
    const ordered = [];
    const seen = new Set();
    (work || []).forEach((item) => {
      const lifecycle = details?.[workKey(item)]?.control?.lifecycle;
      (lifecycle?.states || []).forEach((state) => {
        if (!seen.has(state.id)) {
          seen.add(state.id);
          ordered.push(state.id);
        }
      });
    });
    (work || []).forEach((item) => {
      if (!seen.has(item.state)) {
        seen.add(item.state);
        ordered.push(item.state);
      }
    });
    return ordered;
  }

  function boardColumns(work, details) {
    const items = work || [];
    return stateOrder(items, details).map((state) => ({
      state,
      items: items.filter((item) => item.state === state),
    }));
  }

  function metrics(overview, details) {
    const detailValues = Object.values(details || {});
    const readyApprovals = detailValues.flatMap(decisionOptions).filter(
      (option) => option.decision === "approved" && option.allowed === true,
    ).length;
    return {
      activeSwarms: overview?.status?.swarm_statuses?.active || 0,
      workInProgress: attentionKeys(overview, "active-work").size,
      blockedWork: attentionKeys(overview, "blocked-work").size,
      pendingApprovals: readyApprovals,
      missingEvidence: detailValues.filter(hasEvidenceBlocker).length,
      failedSessions: attentionKeys(overview, "failed-sessions").size,
    };
  }

  function recentActivity(events, limit = 8) {
    return [...(events || [])]
      .sort((left, right) => String(right.timestamp).localeCompare(String(left.timestamp)))
      .slice(0, limit);
  }

  root.DashboardModel = {
    boardColumns,
    decisionOptions,
    decisionProjection,
    findOption,
    gateCount,
    hasEvidenceBlocker,
    isBlocked,
    isWorkInProgress,
    metrics,
    optionKey,
    recentActivity,
    swarmAssignments,
    workKey,
  };
}(globalThis));
